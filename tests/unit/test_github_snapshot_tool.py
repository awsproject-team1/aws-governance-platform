"""Unit tests for the read-only GitHub IaCSnapshot Tool."""

import json
import unittest

from packages.contracts import IaCSnapshot, IaCSnapshotSources
from tools.github import (
    MAX_SNAPSHOT_PAYLOAD_BYTES,
    MAX_TERRAFORM_FILE_BYTES,
    MAX_TERRAFORM_FILES,
    ApprovedRepository,
    CommitNotFoundError,
    InstallationAccessError,
    NoTerraformFilesError,
    RepositoryNotApprovedError,
    SnapshotMismatchError,
    SnapshotNotFoundError,
    SnapshotStorageError,
    SnapshotTooLargeError,
    build_iac_snapshot,
    is_terraform_path,
    read_iac_snapshot_sources,
)

_COMMIT = "b" * 40
_APPROVED = ApprovedRepository(
    repository_id="repo-001",
    owner="customer",
    name="company-infra",
    default_branch="main",
)


class StubApprovals:
    def __init__(self, *repositories: ApprovedRepository) -> None:
        self._by_id = {repository.repository_id: repository for repository in repositories}
        self.lookups: list[str] = []

    def find(self, repository_id: str) -> ApprovedRepository | None:
        self.lookups.append(repository_id)
        return self._by_id.get(repository_id)


class StubContents:
    def __init__(
        self,
        *,
        paths: tuple[str, ...] = (),
        sources: dict[str, str] | None = None,
        list_error: Exception | None = None,
        read_error: Exception | None = None,
    ) -> None:
        self._paths = paths
        self._sources = sources or {}
        self._list_error = list_error
        self._read_error = read_error
        self.list_calls = 0
        self.read_paths: list[str] = []

    def list_paths(self, repository: ApprovedRepository, commit_sha: str) -> tuple[str, ...]:
        self.list_calls += 1
        if self._list_error is not None:
            raise self._list_error
        return self._paths

    def read_text(self, repository: ApprovedRepository, commit_sha: str, path: str) -> str:
        self.read_paths.append(path)
        if self._read_error is not None:
            raise self._read_error
        return self._sources[path]


class StubArtifacts:
    def __init__(
        self, *, reference: str = "snapshot-ref-001", error: Exception | None = None
    ) -> None:
        self._reference = reference
        self._error = error
        self.stored: list[bytes] = []

    def put_snapshot(self, content: bytes) -> str:
        if self._error is not None:
            raise self._error
        self.stored.append(content)
        return self._reference


class TerraformPathTest(unittest.TestCase):
    def test_only_terraform_source_suffixes_are_collected(self) -> None:
        self.assertTrue(is_terraform_path("main.tf"))
        self.assertTrue(is_terraform_path("modules/s3/main.tf.json"))
        self.assertFalse(is_terraform_path("README.md"))
        self.assertFalse(is_terraform_path("terraform.tfstate"))
        self.assertFalse(is_terraform_path("main.tfvars"))


class BuildIaCSnapshotTest(unittest.TestCase):
    def test_snapshot_captures_sorted_terraform_paths_at_the_requested_commit(self) -> None:
        contents = StubContents(
            paths=("modules/s3/main.tf", "README.md", "main.tf"),
            sources={"main.tf": "resource {}", "modules/s3/main.tf": "module {}"},
        )
        artifacts = StubArtifacts()

        snapshot = build_iac_snapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            approvals=StubApprovals(_APPROVED),
            contents=contents,
            artifacts=artifacts,
        )

        self.assertEqual(snapshot.repository_id, "repo-001")
        self.assertEqual(snapshot.commit_sha, _COMMIT)
        self.assertEqual(snapshot.files, ("main.tf", "modules/s3/main.tf"))
        self.assertEqual(snapshot.snapshot_ref, "snapshot-ref-001")

    def test_terraform_source_text_is_preserved_only_in_the_artifact(self) -> None:
        contents = StubContents(paths=("main.tf",), sources={"main.tf": "resource {}"})
        artifacts = StubArtifacts()

        snapshot = build_iac_snapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            approvals=StubApprovals(_APPROVED),
            contents=contents,
            artifacts=artifacts,
        )

        stored = json.loads(artifacts.stored[0].decode("utf-8"))
        self.assertEqual(stored["sources"], {"main.tf": "resource {}"})
        self.assertNotIn("resource {}", json.dumps(snapshot.to_dict()))

    def test_unapproved_repository_is_rejected_before_any_content_request(self) -> None:
        contents = StubContents(paths=("main.tf",))

        with self.assertRaisesRegex(RepositoryNotApprovedError, "not approved"):
            build_iac_snapshot(
                repository_id="repo-999",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=contents,
                artifacts=StubArtifacts(),
            )

        self.assertEqual(contents.list_calls, 0)

    def test_invalid_commit_sha_is_rejected_before_any_approval_lookup(self) -> None:
        approvals = StubApprovals(_APPROVED)
        contents = StubContents(paths=("main.tf",))

        with self.assertRaisesRegex(CommitNotFoundError, "commit_sha must be 40 lowercase"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha="not-a-sha",
                approvals=approvals,
                contents=contents,
                artifacts=StubArtifacts(),
            )

        self.assertEqual(approvals.lookups, [])
        self.assertEqual(contents.list_calls, 0)

    def test_commit_without_terraform_files_raises_a_tool_error(self) -> None:
        with self.assertRaisesRegex(NoTerraformFilesError, "no Terraform files"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=("README.md",)),
                artifacts=StubArtifacts(),
            )

    def test_content_failures_surface_as_tool_errors(self) -> None:
        with self.assertRaisesRegex(InstallationAccessError, "listing failed"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(list_error=TimeoutError("upstream timeout")),
                artifacts=StubArtifacts(),
            )

        with self.assertRaisesRegex(InstallationAccessError, "read failed"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=("main.tf",), read_error=TimeoutError("upstream")),
                artifacts=StubArtifacts(),
            )

    def test_storage_failures_surface_as_tool_errors(self) -> None:
        contents = StubContents(paths=("main.tf",), sources={"main.tf": "resource {}"})

        with self.assertRaisesRegex(SnapshotStorageError, "could not be preserved"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=contents,
                artifacts=StubArtifacts(error=OSError("bucket unavailable")),
            )

        with self.assertRaisesRegex(SnapshotStorageError, "empty snapshot reference"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=("main.tf",), sources={"main.tf": "resource {}"}),
                artifacts=StubArtifacts(reference="  "),
            )

    def test_identical_input_produces_a_reproducible_artifact_payload(self) -> None:
        first = StubArtifacts()
        second = StubArtifacts()
        sources = {"main.tf": "resource {}", "modules/s3/main.tf": "module {}"}

        for artifacts in (first, second):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(
                    paths=("modules/s3/main.tf", "main.tf"),
                    sources=sources,
                ),
                artifacts=artifacts,
            )

        self.assertEqual(first.stored, second.stored)


class CaptureLimitTest(unittest.TestCase):
    def test_too_many_terraform_files_are_rejected_before_reading(self) -> None:
        paths = tuple(f"module{index:04d}/main.tf" for index in range(MAX_TERRAFORM_FILES + 1))
        contents = StubContents(paths=paths)

        with self.assertRaisesRegex(SnapshotTooLargeError, "Terraform files"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=contents,
                artifacts=StubArtifacts(),
            )

        self.assertEqual(contents.read_paths, [])

    def test_capture_accepts_the_maximum_terraform_file_count(self) -> None:
        paths = tuple(f"module{index:04d}/main.tf" for index in range(MAX_TERRAFORM_FILES))
        artifacts = StubArtifacts()

        snapshot = build_iac_snapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            approvals=StubApprovals(_APPROVED),
            contents=StubContents(paths=paths, sources=dict.fromkeys(paths, "resource {}")),
            artifacts=artifacts,
        )

        self.assertEqual(len(snapshot.files), MAX_TERRAFORM_FILES)

    def test_one_oversized_terraform_file_is_rejected(self) -> None:
        oversized = "a" * (MAX_TERRAFORM_FILE_BYTES + 1)

        with self.assertRaisesRegex(SnapshotTooLargeError, "one Terraform file exceeds"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=("main.tf",), sources={"main.tf": oversized}),
                artifacts=StubArtifacts(),
            )

    def test_accumulated_terraform_text_is_bounded(self) -> None:
        per_file = MAX_TERRAFORM_FILE_BYTES
        file_count = MAX_SNAPSHOT_PAYLOAD_BYTES // per_file + 1
        paths = tuple(f"module{index:04d}/main.tf" for index in range(file_count))
        artifacts = StubArtifacts()

        with self.assertRaisesRegex(SnapshotTooLargeError, "captured Terraform text exceeds"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=paths, sources=dict.fromkeys(paths, "a" * per_file)),
                artifacts=artifacts,
            )

        self.assertEqual(artifacts.stored, [])

    def test_multibyte_text_is_measured_in_bytes(self) -> None:
        multibyte = "가" * (MAX_TERRAFORM_FILE_BYTES // 3 + 1)

        self.assertLess(len(multibyte), MAX_TERRAFORM_FILE_BYTES)
        with self.assertRaisesRegex(SnapshotTooLargeError, "one Terraform file exceeds"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=StubContents(paths=("main.tf",), sources={"main.tf": multibyte}),
                artifacts=StubArtifacts(),
            )

    def test_non_text_content_surfaces_as_a_tool_error(self) -> None:
        class BytesContents(StubContents):
            def read_text(self, repository: ApprovedRepository, commit_sha: str, path: str) -> str:
                return b"resource {}"  # type: ignore[return-value]

        with self.assertRaisesRegex(InstallationAccessError, "non-text"):
            build_iac_snapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                approvals=StubApprovals(_APPROVED),
                contents=BytesContents(paths=("main.tf",)),
                artifacts=StubArtifacts(),
            )


class StubReader:
    def __init__(self, *, payload: bytes = b"", error: Exception | None = None) -> None:
        self._payload = payload
        self._error = error
        self.requested: list[str] = []

    def get_snapshot(self, snapshot_ref: str) -> bytes:
        self.requested.append(snapshot_ref)
        if self._error is not None:
            raise self._error
        return self._payload


def _snapshot(*, files: tuple[str, ...] = ("main.tf",)) -> IaCSnapshot:
    return IaCSnapshot(
        repository_id="repo-001",
        commit_sha=_COMMIT,
        files=files,
        snapshot_ref="snapshot-ref-001",
    )


def _payload(
    *,
    repository_id: str = "repo-001",
    commit_sha: str = _COMMIT,
    sources: dict[str, str] | None = None,
) -> bytes:
    return IaCSnapshotSources(
        repository_id=repository_id,
        commit_sha=commit_sha,
        sources=sources or {"main.tf": "resource {}"},
    ).to_payload_bytes()


class ReadIaCSnapshotSourcesTest(unittest.TestCase):
    def test_consumer_loads_captured_terraform_text_for_a_snapshot(self) -> None:
        reader = StubReader(payload=_payload(sources={"main.tf": "resource {}"}))

        captured = read_iac_snapshot_sources(snapshot=_snapshot(), reader=reader)

        self.assertEqual(reader.requested, ["snapshot-ref-001"])
        self.assertEqual(dict(captured.sources), {"main.tf": "resource {}"})

    def test_build_output_can_be_read_back_by_a_consumer(self) -> None:
        artifacts = StubArtifacts()
        snapshot = build_iac_snapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            approvals=StubApprovals(_APPROVED),
            contents=StubContents(
                paths=("modules/s3/main.tf", "main.tf"),
                sources={"main.tf": "resource {}", "modules/s3/main.tf": "module {}"},
            ),
            artifacts=artifacts,
        )

        captured = read_iac_snapshot_sources(
            snapshot=snapshot,
            reader=StubReader(payload=artifacts.stored[0]),
        )

        self.assertEqual(captured.paths, snapshot.files)
        self.assertEqual(captured.commit_sha, snapshot.commit_sha)

    def test_missing_stored_snapshot_surfaces_as_a_tool_error(self) -> None:
        with self.assertRaisesRegex(SnapshotNotFoundError, "could not be read"):
            read_iac_snapshot_sources(
                snapshot=_snapshot(),
                reader=StubReader(error=KeyError("absent")),
            )

    def test_unusable_stored_payload_surfaces_as_a_tool_error(self) -> None:
        with self.assertRaisesRegex(SnapshotMismatchError, "not usable"):
            read_iac_snapshot_sources(
                snapshot=_snapshot(),
                reader=StubReader(payload=b"{"),
            )

    def test_payload_from_another_capture_is_rejected(self) -> None:
        cases = (
            (_payload(repository_id="repo-002"), "different Repository"),
            (_payload(commit_sha="d" * 40), "different commit"),
            (_payload(sources={"other.tf": "resource {}"}), "paths do not match"),
        )

        for payload, expected in cases:
            with self.subTest(expected=expected):
                with self.assertRaisesRegex(SnapshotMismatchError, expected):
                    read_iac_snapshot_sources(
                        snapshot=_snapshot(),
                        reader=StubReader(payload=payload),
                    )

    def test_snapshot_argument_must_be_a_contract_instance(self) -> None:
        with self.assertRaisesRegex(SnapshotMismatchError, "must be an IaCSnapshot"):
            read_iac_snapshot_sources(
                snapshot={"snapshot_ref": "snapshot-ref-001"},
                reader=StubReader(payload=_payload()),
            )

    def test_oversized_stored_payload_is_rejected_before_decoding(self) -> None:
        oversized = b"a" * (MAX_SNAPSHOT_PAYLOAD_BYTES + 1)

        with self.assertRaisesRegex(SnapshotTooLargeError, "stored snapshot payload exceeds"):
            read_iac_snapshot_sources(
                snapshot=_snapshot(),
                reader=StubReader(payload=oversized),
            )


if __name__ == "__main__":
    unittest.main()
