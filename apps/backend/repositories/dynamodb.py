"""Injected DynamoDB adapter for revision-checked Job persistence."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from apps.backend.jobs.lifecycle import (
    InvalidJobTransition,
    StaleJobRevision,
    transition_job,
)
from apps.backend.jobs.models import Job
from apps.backend.repositories.ports import (
    DuplicateJobError,
    InvalidJobMutationError,
    RepositoryError,
    RevisionConflictError,
    StoredDataError,
)
from packages.contracts import ApiError, JobCurrentStep, JobStatus


class DynamoTable(Protocol):
    """Minimum table operations used by the adapter."""

    def put_item(self, **kwargs: object) -> object: ...

    def get_item(self, **kwargs: object) -> Mapping[str, object]: ...


class DynamoDbJobRepository:
    """Persist Job models through an injected DynamoDB table resource."""

    def __init__(self, table: DynamoTable) -> None:
        if table is None:
            raise TypeError("table is required")
        self._table = table

    def create_job(self, job: Job) -> None:
        """Create a revision-zero Job without replacing an existing item."""
        _require_job(job)
        if (
            job.revision != 0
            or job.status is not JobStatus.QUEUED
            or job.assessment_id is not None
            or job.remediation_id is not None
            or job.deployment_id is not None
        ):
            raise InvalidJobMutationError("new job must be an unlinked QUEUED revision")
        try:
            self._table.put_item(
                Item=_item_from_job(job),
                ConditionExpression="attribute_not_exists(#job_id)",
                ExpressionAttributeNames={"#job_id": "job_id"},
            )
        except Exception as error:
            if _provider_error_code(error) == "ConditionalCheckFailedException":
                raise DuplicateJobError("job already exists") from None
            raise RepositoryError("job create failed") from None

    def get_job(self, job_id: str) -> Job | None:
        """Read one Job with strong consistency and validate stored data."""
        _require_non_empty_string(job_id, "job_id")
        try:
            response = self._table.get_item(
                Key={"job_id": job_id},
                ConsistentRead=True,
            )
        except Exception:
            raise RepositoryError("job read failed") from None

        item = response.get("Item")
        if item is None:
            return None
        if not isinstance(item, Mapping):
            raise StoredDataError("stored job item is invalid")
        return _job_from_item(item)

    def update_job(self, job: Job, *, expected_revision: int) -> None:
        """Replace one Job only when the persisted revision still matches."""
        _require_job(job)
        _require_revision(expected_revision)
        if job.revision != expected_revision + 1:
            raise InvalidJobMutationError("job revision must equal expected_revision + 1")

        current = self.get_job(job.job_id)
        if current is None or current.revision != expected_revision:
            raise RevisionConflictError("job revision conflict")
        try:
            lifecycle_candidate = transition_job(
                current,
                expected_revision=expected_revision,
                status=job.status,
                current_step=job.current_step,
                assessment_id=job.assessment_id,
                remediation_id=job.remediation_id,
                deployment_id=job.deployment_id,
                error=job.error,
            )
        except InvalidJobTransition, StaleJobRevision, TypeError, ValueError:
            raise InvalidJobMutationError("job update violates lifecycle") from None
        if lifecycle_candidate != job:
            raise InvalidJobMutationError("job update changes immutable fields")

        try:
            self._table.put_item(
                Item=_item_from_job(job),
                ConditionExpression="#revision = :expected_revision",
                ExpressionAttributeNames={"#revision": "revision"},
                ExpressionAttributeValues={":expected_revision": expected_revision},
            )
        except Exception as error:
            if _provider_error_code(error) == "ConditionalCheckFailedException":
                raise RevisionConflictError("job revision conflict") from None
            raise RepositoryError("job update failed") from None


def _item_from_job(job: Job) -> dict[str, object]:
    item: dict[str, object] = {
        "job_id": job.job_id,
        "job_type": job.job_type,
        "status": job.status.value,
        "current_step": job.current_step.value,
        "requested_by": job.requested_by,
        "revision": job.revision,
    }
    for name in ("assessment_id", "remediation_id", "deployment_id"):
        value = getattr(job, name)
        if value is not None:
            item[name] = value
    if job.error is not None:
        item["error"] = job.error.to_dict()
    return item


def _job_from_item(item: Mapping[str, object]) -> Job:
    try:
        error_value = item.get("error")
        error = None
        if error_value is not None:
            if not isinstance(error_value, Mapping):
                raise TypeError
            error = ApiError(
                code=error_value["code"],
                message=error_value["message"],
            )
        return Job(
            job_id=item["job_id"],
            job_type=item["job_type"],
            status=JobStatus(item["status"]),
            current_step=JobCurrentStep(item["current_step"]),
            requested_by=item["requested_by"],
            revision=_stored_revision(item["revision"]),
            assessment_id=item.get("assessment_id"),
            remediation_id=item.get("remediation_id"),
            deployment_id=item.get("deployment_id"),
            error=error,
        )
    except KeyError, TypeError, ValueError:
        raise StoredDataError("stored job item is invalid") from None


def _stored_revision(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError
    if isinstance(value, int):
        return value
    if isinstance(value, Decimal) and value == value.to_integral_value():
        return int(value)
    raise TypeError


def _provider_error_code(error: Exception) -> str | None:
    response = getattr(error, "response", None)
    if not isinstance(response, Mapping):
        return None
    detail = response.get("Error")
    if not isinstance(detail, Mapping):
        return None
    code = detail.get("Code")
    return code if isinstance(code, str) else None


def _require_job(job: object) -> None:
    if not isinstance(job, Job):
        raise TypeError("job must be a Job")


def _require_revision(value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("expected_revision must be an integer")
    if value < 0:
        raise ValueError("expected_revision must be non-negative")


def _require_non_empty_string(value: object, field_name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
