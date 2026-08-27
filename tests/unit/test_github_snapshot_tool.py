"""Unit tests for the read-only GitHub IaCSnapshot Tool."""

import json
import unittest

from tools.github import (
    ApprovedRepository,
    CommitNotFoundError,
    InstallationAccessError,
    NoTerraformFilesError,
    RepositoryNotApprovedError,
    SnapshotStorageError,
    build_iac_snapshot,
    is_terraform_path,
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


if __name__ == "__main__":
    unittest.main()
