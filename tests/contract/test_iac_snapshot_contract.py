"""Contract tests for the customer IaCSnapshot reproducibility projection."""

import unittest

from packages.contracts import IaCSnapshot

_COMMIT = "a" * 40


class IaCSnapshotContractTest(unittest.TestCase):
    def test_snapshot_serializes_the_documented_required_fields(self) -> None:
        snapshot = IaCSnapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            files=("main.tf", "modules/s3/main.tf"),
            snapshot_ref="snapshot-ref-001",
        )

        self.assertEqual(
            snapshot.to_dict(),
            {
                "repository_id": "repo-001",
                "commit_sha": _COMMIT,
                "files": ["main.tf", "modules/s3/main.tf"],
                "snapshot_ref": "snapshot-ref-001",
            },
        )

    def test_commit_sha_must_be_a_full_lowercase_hex_digest(self) -> None:
        for invalid in ("A" * 40, "abc123", _COMMIT + "a"):
            with self.subTest(commit_sha=invalid):
                with self.assertRaisesRegex(ValueError, "commit_sha must be 40 lowercase"):
                    IaCSnapshot(
                        repository_id="repo-001",
                        commit_sha=invalid,
                        files=("main.tf",),
                        snapshot_ref="snapshot-ref-001",
                    )

    def test_files_must_be_a_sorted_unique_non_empty_tuple(self) -> None:
        with self.assertRaisesRegex(ValueError, "files must contain at least one path"):
            IaCSnapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                files=(),
                snapshot_ref="snapshot-ref-001",
            )

        with self.assertRaisesRegex(ValueError, "files must not repeat a path"):
            IaCSnapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                files=("main.tf", "main.tf"),
                snapshot_ref="snapshot-ref-001",
            )

        with self.assertRaisesRegex(ValueError, "files must be sorted for reproducibility"):
            IaCSnapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                files=("main.tf", "a.tf"),
                snapshot_ref="snapshot-ref-001",
            )

        with self.assertRaisesRegex(TypeError, "files must be a tuple"):
            IaCSnapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                files=["main.tf"],
                snapshot_ref="snapshot-ref-001",
            )

    def test_opaque_identifiers_must_be_non_empty(self) -> None:
        with self.assertRaisesRegex(ValueError, "repository_id must be a non-empty string"):
            IaCSnapshot(
                repository_id=" ",
                commit_sha=_COMMIT,
                files=("main.tf",),
                snapshot_ref="snapshot-ref-001",
            )

        with self.assertRaisesRegex(ValueError, "snapshot_ref must be a non-empty string"):
            IaCSnapshot(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                files=("main.tf",),
                snapshot_ref="",
            )

    def test_snapshot_does_not_expose_terraform_source_text(self) -> None:
        snapshot = IaCSnapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            files=("main.tf",),
            snapshot_ref="snapshot-ref-001",
        )

        self.assertEqual(
            set(snapshot.to_dict()), {"repository_id", "commit_sha", "files", "snapshot_ref"}
        )


if __name__ == "__main__":
    unittest.main()
