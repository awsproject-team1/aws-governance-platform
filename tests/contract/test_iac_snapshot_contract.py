"""Contract tests for the customer IaCSnapshot reproducibility projection."""

import unittest

from packages.contracts import (
    IaCSnapshot,
    IaCSnapshotPayloadError,
    IaCSnapshotSources,
    decode_iac_snapshot_sources,
)

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

    def test_files_reject_paths_that_escape_a_work_tree(self) -> None:
        escaping_paths = (
            "../../../../home/user/.ssh/id_rsa.tf",
            "/etc/terraform/main.tf",
            "..\\..\\windows\\system.tf",
            "C:/terraform/main.tf",
            "modules/../../main.tf",
            "modules//main.tf",
            "./main.tf",
            "main.tf\x00.txt",
            " main.tf",
            "main.tf ",
        )

        for path in escaping_paths:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    IaCSnapshot(
                        repository_id="repo-001",
                        commit_sha=_COMMIT,
                        files=(path,),
                        snapshot_ref="snapshot-ref-001",
                    )

    def test_files_accept_normalized_repository_relative_paths(self) -> None:
        snapshot = IaCSnapshot(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            files=("environments/prod/main.tf", "main.tf", "modules/s3/main.tf.json"),
            snapshot_ref="snapshot-ref-001",
        )

        self.assertEqual(len(snapshot.files), 3)

    def test_snapshot_ref_must_not_expose_a_storage_location(self) -> None:
        exposing_refs = (
            "s3://prod-governance-artifacts/customers/acme/snap.json",
            "customers/acme/snapshots/001",
            "https://bucket.s3.amazonaws.com/key",
            "snapshot ref 001",
            "snapshot\\ref",
            "-leading-hyphen",
            "a" * 256,
        )

        for snapshot_ref in exposing_refs:
            with self.subTest(snapshot_ref=snapshot_ref):
                with self.assertRaisesRegex(ValueError, "snapshot_ref must be an opaque token"):
                    IaCSnapshot(
                        repository_id="repo-001",
                        commit_sha=_COMMIT,
                        files=("main.tf",),
                        snapshot_ref=snapshot_ref,
                    )

    def test_snapshot_ref_accepts_opaque_tokens(self) -> None:
        for snapshot_ref in (
            "snapshot-ref-001",
            "sha256:" + "a" * 64,
            "01JBX9Z0M7QFTK8W2N4V6Y.snapshot",
            "a" * 255,
        ):
            with self.subTest(snapshot_ref=snapshot_ref):
                snapshot = IaCSnapshot(
                    repository_id="repo-001",
                    commit_sha=_COMMIT,
                    files=("main.tf",),
                    snapshot_ref=snapshot_ref,
                )
                self.assertEqual(snapshot.snapshot_ref, snapshot_ref)

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


class IaCSnapshotSourcesContractTest(unittest.TestCase):
    def test_payload_round_trip_preserves_captured_terraform_text(self) -> None:
        captured = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources={"main.tf": "resource {}", "modules/s3/main.tf": "module {}"},
        )

        decoded = decode_iac_snapshot_sources(captured.to_payload_bytes())

        self.assertEqual(decoded.repository_id, "repo-001")
        self.assertEqual(decoded.commit_sha, _COMMIT)
        self.assertEqual(dict(decoded.sources), dict(captured.sources))
        self.assertEqual(decoded.paths, ("main.tf", "modules/s3/main.tf"))

    def test_payload_encoding_is_deterministic_for_identical_input(self) -> None:
        first = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources={"modules/s3/main.tf": "module {}", "main.tf": "resource {}"},
        )
        second = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources={"main.tf": "resource {}", "modules/s3/main.tf": "module {}"},
        )

        self.assertEqual(first.to_payload_bytes(), second.to_payload_bytes())

    def test_captured_sources_are_read_only(self) -> None:
        captured = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources={"main.tf": "resource {}"},
        )

        with self.assertRaises(TypeError):
            captured.sources["main.tf"] = "tampered"  # type: ignore[index]

    def test_mutating_the_input_mapping_does_not_change_captured_sources(self) -> None:
        mutable = {"main.tf": "resource {}"}
        captured = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources=mutable,
        )

        mutable["main.tf"] = "tampered"

        self.assertEqual(captured.sources["main.tf"], "resource {}")

    def test_sources_require_a_non_empty_mapping_of_text(self) -> None:
        with self.assertRaisesRegex(ValueError, "sources must contain at least one file"):
            IaCSnapshotSources(repository_id="repo-001", commit_sha=_COMMIT, sources={})

        with self.assertRaisesRegex(TypeError, "sources must be a mapping"):
            IaCSnapshotSources(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                sources=[("main.tf", "resource {}")],
            )

        with self.assertRaisesRegex(TypeError, "sources text must be a string"):
            IaCSnapshotSources(
                repository_id="repo-001",
                commit_sha=_COMMIT,
                sources={"main.tf": 1},
            )

    def test_unusable_payloads_raise_the_contract_failure(self) -> None:
        for payload, expected in (
            ("not bytes", "payload must be bytes"),
            (b"\xff\xfe", "payload is not valid UTF-8 JSON"),
            (b"[]", "payload must decode to an object"),
            (b'{"repository_id": "repo-001"}', "payload must contain exactly"),
        ):
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(IaCSnapshotPayloadError, expected):
                    decode_iac_snapshot_sources(payload)

    def test_payload_violating_the_sources_contract_is_rejected(self) -> None:
        with self.assertRaisesRegex(IaCSnapshotPayloadError, "does not satisfy the sources"):
            decode_iac_snapshot_sources(
                b'{"repository_id": "repo-001", "commit_sha": "nope", "sources": {"main.tf": "x"}}'
            )

    def test_sources_reject_paths_that_escape_a_work_tree(self) -> None:
        for path in ("../secrets.tf", "/etc/main.tf", "..\\main.tf", "./main.tf"):
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    IaCSnapshotSources(
                        repository_id="repo-001",
                        commit_sha=_COMMIT,
                        sources={path: "resource {}"},
                    )

    def test_stored_payload_with_an_escaping_path_is_rejected_on_decode(self) -> None:
        payload = (
            b'{"repository_id": "repo-001", "commit_sha": "'
            + (b"a" * 40)
            + b'", "sources": {"../../../.ssh/id_rsa.tf": "resource {}"}}'
        )

        with self.assertRaisesRegex(IaCSnapshotPayloadError, "does not satisfy the sources"):
            decode_iac_snapshot_sources(payload)

    def test_empty_terraform_files_remain_valid(self) -> None:
        captured = IaCSnapshotSources(
            repository_id="repo-001",
            commit_sha=_COMMIT,
            sources={"empty.tf": ""},
        )

        self.assertEqual(captured.sources["empty.tf"], "")


if __name__ == "__main__":
    unittest.main()
