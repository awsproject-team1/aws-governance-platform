"""Unit tests for injected DynamoDB and immutable S3 adapters."""

import hashlib
import unittest
from decimal import Decimal

from apps.backend.jobs import Job, create_job, transition_job
from apps.backend.repositories import (
    ArtifactCollisionError,
    ArtifactIntegrityError,
    ArtifactNotFoundError,
    DuplicateJobError,
    DynamoDbJobRepository,
    InvalidJobMutationError,
    RevisionConflictError,
    S3ArtifactStore,
)
from packages.contracts import JobCurrentStep, JobStatus


class ProviderError(Exception):
    def __init__(self, code: str, message: str = "provider detail") -> None:
        super().__init__(message)
        self.response = {"Error": {"Code": code, "Message": message}}


class FakeDynamoTable:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self.put_error: Exception | None = None
        self.item: dict[str, object] | None = None

    def put_item(self, **kwargs: object) -> object:
        self.put_calls.append(kwargs)
        if self.put_error is not None:
            raise self.put_error
        self.item = kwargs["Item"]
        return {}

    def get_item(self, **kwargs: object) -> dict[str, object]:
        self.get_calls.append(kwargs)
        return {} if self.item is None else {"Item": self.item}


class Body:
    def __init__(self, content: bytes) -> None:
        self._content = content

    def read(self) -> bytes:
        return self._content


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, object]] = []
        self.get_calls: list[dict[str, object]] = []
        self.put_error: Exception | None = None
        self.objects: dict[str, bytes] = {}

    def put_object(self, **kwargs: object) -> object:
        self.put_calls.append(kwargs)
        if self.put_error is not None:
            raise self.put_error
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(self, **kwargs: object) -> dict[str, object]:
        self.get_calls.append(kwargs)
        key = kwargs["Key"]
        if key not in self.objects:
            raise ProviderError("NoSuchKey")
        return {"Body": Body(self.objects[key])}


def queued_job():
    return create_job(
        job_id="job-001",
        job_type="ASSESSMENT",
        initial_step=JobCurrentStep.LOAD_IAC,
        requested_by="subject-001",
    )


class DynamoDbJobRepositoryTest(unittest.TestCase):
    def test_create_uses_a_non_overwrite_condition(self) -> None:
        table = FakeDynamoTable()
        repository = DynamoDbJobRepository(table)

        repository.create_job(queued_job())

        call = table.put_calls[0]
        self.assertEqual(call["ConditionExpression"], "attribute_not_exists(#job_id)")
        self.assertEqual(call["ExpressionAttributeNames"], {"#job_id": "job_id"})
        self.assertEqual(call["Item"]["revision"], 0)

    def test_create_rejects_a_directly_constructed_non_initial_state(self) -> None:
        forged = Job(
            job_id="job-001",
            job_type="ASSESSMENT",
            status=JobStatus.COMPLETED,
            current_step=JobCurrentStep.POST_DEPLOY_VERIFICATION,
            requested_by="forged-owner",
            revision=0,
            deployment_id="dep-forged",
        )

        with self.assertRaises(InvalidJobMutationError):
            DynamoDbJobRepository(FakeDynamoTable()).create_job(forged)

    def test_duplicate_create_translates_the_provider_condition_failure(self) -> None:
        table = FakeDynamoTable()
        table.put_error = ProviderError("ConditionalCheckFailedException", "table secret")

        with self.assertRaises(DuplicateJobError) as caught:
            DynamoDbJobRepository(table).create_job(queued_job())

        self.assertNotIn("table secret", str(caught.exception))

    def test_get_uses_consistent_read_and_decodes_a_job(self) -> None:
        table = FakeDynamoTable()
        table.item = {
            "job_id": "job-001",
            "job_type": "ASSESSMENT",
            "status": "RUNNING",
            "current_step": "ASSESS",
            "requested_by": "subject-001",
            "revision": Decimal("1"),
            "assessment_id": "asm-001",
        }

        job = DynamoDbJobRepository(table).get_job("job-001")

        self.assertIsNotNone(job)
        self.assertEqual(job.revision, 1)
        self.assertEqual(job.assessment_id, "asm-001")
        self.assertEqual(
            table.get_calls,
            [{"Key": {"job_id": "job-001"}, "ConsistentRead": True}],
        )

    def test_update_requires_the_expected_revision_condition(self) -> None:
        table = FakeDynamoTable()
        repository = DynamoDbJobRepository(table)
        initial = queued_job()
        repository.create_job(initial)
        table.put_calls.clear()
        running = transition_job(
            initial,
            expected_revision=0,
            status=JobStatus.RUNNING,
            current_step=JobCurrentStep.ASSESS,
        )

        repository.update_job(running, expected_revision=0)

        call = table.put_calls[0]
        self.assertEqual(call["ConditionExpression"], "#revision = :expected_revision")
        self.assertEqual(call["ExpressionAttributeValues"], {":expected_revision": 0})
        self.assertEqual(call["Item"]["revision"], 1)

    def test_stale_persisted_revision_translates_to_a_conflict(self) -> None:
        table = FakeDynamoTable()
        repository = DynamoDbJobRepository(table)
        initial = queued_job()
        repository.create_job(initial)
        table.put_error = ProviderError("ConditionalCheckFailedException")
        running = transition_job(
            initial,
            expected_revision=0,
            status=JobStatus.RUNNING,
        )

        with self.assertRaises(RevisionConflictError):
            repository.update_job(running, expected_revision=0)

    def test_update_rejects_owner_changes_and_lifecycle_bypasses(self) -> None:
        table = FakeDynamoTable()
        repository = DynamoDbJobRepository(table)
        repository.create_job(queued_job())
        forged = Job(
            job_id="job-001",
            job_type="ASSESSMENT",
            status=JobStatus.RUNNING,
            current_step=JobCurrentStep.ASSESS,
            requested_by="forged-owner",
            revision=1,
            assessment_id="asm-forged",
        )

        with self.assertRaises(InvalidJobMutationError):
            repository.update_job(forged, expected_revision=0)

        table.item = {
            "job_id": "job-001",
            "job_type": "ASSESSMENT",
            "status": "COMPLETED",
            "current_step": "POST_DEPLOY_VERIFICATION",
            "requested_by": "subject-001",
            "revision": 2,
        }
        revived = Job(
            job_id="job-001",
            job_type="ASSESSMENT",
            status=JobStatus.RUNNING,
            current_step=JobCurrentStep.ASSESS,
            requested_by="subject-001",
            revision=3,
        )

        with self.assertRaises(InvalidJobMutationError):
            repository.update_job(revived, expected_revision=2)


class S3ArtifactStoreTest(unittest.TestCase):
    def test_put_uses_sha256_key_and_if_none_match(self) -> None:
        client = FakeS3Client()
        store = S3ArtifactStore(client, bucket_name="injected-bucket")
        content = b"immutable artifact"
        digest = hashlib.sha256(content).hexdigest()

        reference = store.put(content)

        self.assertEqual(reference.content_digest, f"sha256:{digest}")
        self.assertEqual(
            client.put_calls,
            [
                {
                    "Bucket": "injected-bucket",
                    "Key": f"sha256/{digest}",
                    "Body": content,
                    "IfNoneMatch": "*",
                    "Metadata": {"sha256": digest},
                }
            ],
        )

    def test_duplicate_identical_content_is_idempotent(self) -> None:
        client = FakeS3Client()
        content = b"same bytes"
        digest = hashlib.sha256(content).hexdigest()
        client.objects[f"sha256/{digest}"] = content
        client.put_error = ProviderError("PreconditionFailed")
        store = S3ArtifactStore(client, bucket_name="injected-bucket")

        reference = store.put(content)

        self.assertEqual(reference.content_digest, f"sha256:{digest}")
        self.assertEqual(len(client.get_calls), 1)

    def test_existing_different_content_is_never_overwritten(self) -> None:
        client = FakeS3Client()
        content = b"requested bytes"
        digest = hashlib.sha256(content).hexdigest()
        key = f"sha256/{digest}"
        client.objects[key] = b"different bytes"
        client.put_error = ProviderError("PreconditionFailed")

        with self.assertRaises(ArtifactCollisionError):
            S3ArtifactStore(client, bucket_name="injected-bucket").put(content)

        self.assertEqual(client.objects[key], b"different bytes")

    def test_get_rejects_missing_or_digest_mismatched_content(self) -> None:
        client = FakeS3Client()
        store = S3ArtifactStore(client, bucket_name="injected-bucket")
        reference = store.put(b"expected bytes")
        key = f"sha256/{reference.hex_digest}"
        client.objects[key] = b"tampered bytes"

        with self.assertRaises(ArtifactIntegrityError):
            store.get(reference)

        del client.objects[key]
        with self.assertRaises(ArtifactNotFoundError):
            store.get(reference)


if __name__ == "__main__":
    unittest.main()
