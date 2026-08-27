"""Security boundary tests for the read-only GitHub Repository Tool."""

import inspect
import unittest

import tools.github.errors as github_errors
import tools.github.ports as github_ports
import tools.github.snapshot as github_snapshot
from tools.github import (
    ApprovedRepository,
    GitHubToolError,
    RepositoryNotApprovedError,
    build_iac_snapshot,
)

_COMMIT = "c" * 40
_APPROVED = ApprovedRepository(
    repository_id="repo-001",
    owner="customer",
    name="company-infra",
    default_branch="main",
)
_WRITE_TERMS = ("apply", "merge", "push", "commit", "create_branch", "create_pull")


class RejectingApprovals:
    def __init__(self) -> None:
        self.lookups: list[str] = []

    def find(self, repository_id: str) -> ApprovedRepository | None:
        self.lookups.append(repository_id)
        return None


class RecordingContents:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def list_paths(self, repository: ApprovedRepository, commit_sha: str) -> tuple[str, ...]:
        self.calls.append("list_paths")
        return ("main.tf",)

    def read_text(self, repository: ApprovedRepository, commit_sha: str, path: str) -> str:
        self.calls.append("read_text")
        return "resource {}"


class RecordingArtifacts:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def put_snapshot(self, content: bytes) -> str:
        self.calls.append("put_snapshot")
        return "snapshot-ref-001"


class ReadOnlyToolBoundaryTest(unittest.TestCase):
    def test_content_ports_expose_no_write_operations(self) -> None:
        for protocol in (github_ports.RepositoryContentSource, github_ports.ApprovalRegistry):
            operations = [name for name in vars(protocol) if not name.startswith("_")]
            with self.subTest(protocol=protocol.__name__):
                for operation in operations:
                    for term in _WRITE_TERMS:
                        self.assertNotIn(term, operation.lower())

    def test_snapshot_module_does_not_reference_apply_or_merge(self) -> None:
        source = inspect.getsource(github_snapshot).lower()

        for term in ("terraform apply", "git push", "merge_pull_request"):
            with self.subTest(term=term):
                self.assertNotIn(term, source)

    def test_unapproved_repository_never_reaches_content_or_storage(self) -> None:
        approvals = RejectingApprovals()
        contents = RecordingContents()
        artifacts = RecordingArtifacts()

        with self.assertRaises(RepositoryNotApprovedError):
            build_iac_snapshot(
                repository_id="repo-999",
                commit_sha=_COMMIT,
                approvals=approvals,
                contents=contents,
                artifacts=artifacts,
            )

        self.assertEqual(approvals.lookups, ["repo-999"])
        self.assertEqual(contents.calls, [])
        self.assertEqual(artifacts.calls, [])

    def test_every_tool_failure_stays_inside_the_tool_error_hierarchy(self) -> None:
        failures = [
            value
            for value in vars(github_errors).values()
            if inspect.isclass(value) and issubclass(value, BaseException)
        ]

        self.assertGreater(len(failures), 1)
        for failure in failures:
            with self.subTest(failure=failure.__name__):
                self.assertTrue(issubclass(failure, GitHubToolError))
                self.assertNotIn("fail", failure.__name__.lower())

    def test_tool_failures_are_not_governance_results(self) -> None:
        for failure in (
            github_errors.CommitNotFoundError,
            github_errors.InstallationAccessError,
            github_errors.NoTerraformFilesError,
            github_errors.RepositoryNotApprovedError,
            github_errors.SnapshotStorageError,
        ):
            with self.subTest(failure=failure.__name__):
                self.assertFalse(hasattr(failure, "evaluation_status"))
                self.assertFalse(hasattr(failure, "severity"))


if __name__ == "__main__":
    unittest.main()
