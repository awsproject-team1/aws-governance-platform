"""Contract tests for the initial Assessment transport boundary."""

import unittest

from packages.contracts import AssessmentAcceptedResponse, AssessmentPhase, JobStatus


class AssessmentContractTest(unittest.TestCase):
    def test_phase_enum_matches_the_documented_contract(self) -> None:
        self.assertEqual(
            {phase.value for phase in AssessmentPhase},
            {"INITIAL", "PRE_DEPLOY", "POST_DEPLOY"},
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
