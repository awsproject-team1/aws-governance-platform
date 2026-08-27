"""Contract tests for the Initial Assessment start and progress boundary."""

import json
import unittest
from pathlib import Path

from packages.contracts import (
    AssessmentAcceptedResponse,
    AssessmentLinkageConfirmation,
    AssessmentPhase,
    AssessmentProgressAcknowledgement,
    AssessmentProgressUpdate,
    AssessmentStartAcknowledgement,
    AssessmentStartCommand,
    AssessmentStartStatus,
    InitialAssessmentStartRequest,
    JobCurrentStep,
    JobStatus,
)
from packages.contracts.governance import EffectiveRuleSet

REPO = Path(__file__).resolve().parents[2]


class AssessmentContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (REPO / "fixtures" / "assessments" / "initial-start-protocol.json").read_text(
                encoding="utf-8"
            )
        )

    def test_phase_enum_matches_the_documented_contract(self) -> None:
        self.assertEqual(
            {phase.value for phase in AssessmentPhase},
            {"INITIAL", "PRE_DEPLOY", "POST_DEPLOY"},
        )

    def test_public_start_request_is_explicit_and_profile_versioned(self) -> None:
        request = InitialAssessmentStartRequest.from_dict(self.fixture["public_start_request"])

        self.assertEqual(request.to_dict(), self.fixture["public_start_request"])
        self.assertIs(request.phase, AssessmentPhase.INITIAL)
        self.assertEqual(request.policy_profile_version, 1)

    def test_public_start_request_rejects_defaults_unknown_fields_and_non_initial_phase(
        self,
    ) -> None:
        base = self.fixture["public_start_request"]
        cases = (
            (
                {key: value for key, value in base.items() if key != "policy_profile_id"},
                "missing field",
            ),
            ({**base, "scope": {}}, "unknown field"),
            ({**base, "admin_settings_snapshot_hash": "sha256:" + "a" * 64}, "unknown field"),
            ({**base, "scoring_version": "1"}, "unknown field"),
            ({**base, "phase": "PRE_DEPLOY"}, "phase must be INITIAL"),
            ({**base, "policy_profile_version": True}, "policy_profile_version must be an integer"),
            (
                {**base, "policy_profile_version": 0},
                "policy_profile_version must be a positive integer",
            ),
        )

        for payload, message in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex((TypeError, ValueError), message):
                    InitialAssessmentStartRequest.from_dict(payload)

    def test_start_command_delivers_server_pinned_effective_rules_and_scoring(self) -> None:
        command = AssessmentStartCommand.from_dict(self.fixture["assessment_start_command"])

        self.assertEqual(command.to_dict(), self.fixture["assessment_start_command"])
        self.assertEqual(command.effective_rule_set.policy_profile_id, "profile-001")
        self.assertEqual(
            command.effective_rule_set.admin_settings_snapshot_hash, "sha256:" + "a" * 64
        )
        self.assertEqual(command.scoring_version, "1")

        mismatched_set = EffectiveRuleSet.from_dict(
            {
                **self.fixture["assessment_start_command"]["effective_rule_set"],
                "phase": "PRE_DEPLOY",
            }
        )
        with self.assertRaisesRegex(ValueError, "effective_rule_set phase must match phase"):
            AssessmentStartCommand(
                job_id="job-001",
                phase=AssessmentPhase.INITIAL,
                repository_id="repo-001",
                effective_rule_set=mismatched_set,
                scoring_version="1",
            )

    def test_linkage_protocol_fixes_the_revision_one_activation_boundary(self) -> None:
        acknowledgement = AssessmentStartAcknowledgement.from_dict(
            self.fixture["start_acknowledgement"]
        )
        confirmation = AssessmentLinkageConfirmation.from_dict(self.fixture["linkage_confirmation"])

        self.assertEqual(acknowledgement.to_dict(), self.fixture["start_acknowledgement"])
        self.assertIs(acknowledgement.status, AssessmentStartStatus.ACCEPTED)
        self.assertEqual(confirmation.to_dict(), self.fixture["linkage_confirmation"])
        self.assertEqual(confirmation.revision, 1)
        self.assertIs(confirmation.status, JobStatus.RUNNING)
        self.assertIs(confirmation.current_step, JobCurrentStep.LOAD_IAC)

        invalid_status = {**self.fixture["linkage_confirmation"], "status": "QUEUED"}
        with self.assertRaisesRegex(ValueError, "status must be RUNNING"):
            AssessmentLinkageConfirmation.from_dict(invalid_status)

        invalid_revisions = (
            (0, ValueError, "revision must be a positive integer"),
            (2, ValueError, "revision must be 1"),
            (True, TypeError, "revision must be an integer"),
        )
        for revision, error_type, message in invalid_revisions:
            with self.subTest(revision=revision):
                with self.assertRaisesRegex(error_type, message):
                    AssessmentLinkageConfirmation.from_dict(
                        {**self.fixture["linkage_confirmation"], "revision": revision}
                    )

    def test_progress_update_has_a_separate_update_id_and_returns_applied_revision(self) -> None:
        update = AssessmentProgressUpdate.from_dict(self.fixture["progress_update"])
        acknowledgement = AssessmentProgressAcknowledgement.from_dict(
            self.fixture["progress_acknowledgement"]
        )

        self.assertEqual(update.to_dict(), self.fixture["progress_update"])
        self.assertEqual(acknowledgement.to_dict(), self.fixture["progress_acknowledgement"])
        self.assertEqual(update.update_id, "update-001")
        self.assertEqual(update.expected_revision, 1)
        self.assertEqual(acknowledgement.revision, 2)

    def test_progress_acknowledgement_rejects_invalid_wire_payloads(self) -> None:
        base = self.fixture["progress_acknowledgement"]
        cases = (
            (
                {key: value for key, value in base.items() if key != "update_id"},
                ValueError,
                "assessment_progress_acknowledgement is missing field\\(s\\): update_id",
            ),
            (
                {**base, "unexpected": "value"},
                ValueError,
                "assessment_progress_acknowledgement has unknown field\\(s\\): unexpected",
            ),
            (
                {**base, "revision": 0},
                ValueError,
                "revision must be a positive integer",
            ),
            ({**base, "revision": True}, TypeError, "revision must be an integer"),
        )

        for payload, error_type, message in cases:
            with self.subTest(payload=payload):
                with self.assertRaisesRegex(error_type, message):
                    AssessmentProgressAcknowledgement.from_dict(payload)

    def test_progress_requires_sanitized_error_only_for_failed_status(self) -> None:
        base = self.fixture["progress_update"]
        with self.assertRaisesRegex(ValueError, "FAILED progress updates require an ApiError"):
            AssessmentProgressUpdate.from_dict({**base, "status": "FAILED", "error": None})
        with self.assertRaisesRegex(
            ValueError, "only FAILED progress updates may receive an error"
        ):
            AssessmentProgressUpdate.from_dict(
                {
                    **base,
                    "error": {"code": "INTERNAL_ERROR", "message": "Assessment failed"},
                }
            )

    def test_accepted_response_is_always_queued(self) -> None:
        response = AssessmentAcceptedResponse(job_id="job-001")

        self.assertIs(response.status, JobStatus.QUEUED)
        self.assertEqual(response.to_dict(), {"job_id": "job-001", "status": "QUEUED"})

        with self.assertRaisesRegex(TypeError, "unexpected keyword argument 'status'"):
            AssessmentAcceptedResponse(**{"job_id": "job-001", "status": JobStatus.RUNNING})

    def test_accepted_response_requires_an_opaque_job_identifier(self) -> None:
        with self.assertRaisesRegex(ValueError, "job_id must be a non-empty string"):
            AssessmentAcceptedResponse(job_id="")


if __name__ == "__main__":
    unittest.main()
