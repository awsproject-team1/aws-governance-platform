"""Security tests for API Gateway HTTP API v2 transport boundaries."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from apps.backend.auth import InvalidIdentityClaims
from apps.backend.handlers.http_transport import (
    InvalidHttpApiEvent,
    job_polling_proxy_response,
    principal_from_http_api_v2_event,
)
from apps.backend.jobs.models import Job
from packages.contracts import JobCurrentStep, JobStatus

REPO = Path(__file__).resolve().parents[2]


class HttpTransportSecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (REPO / "fixtures" / "http" / "api-gateway-v2-contract.json").read_text(
                encoding="utf-8"
            )
        )

    def test_only_the_authorizer_claim_path_can_create_a_principal(self) -> None:
        event = copy.deepcopy(self.fixture["post_assessment_event"])
        event["requestContext"]["authorizer"] = {"claims": {"role": "Admin"}}

        with self.assertRaisesRegex(
            InvalidHttpApiEvent, "requestContext.authorizer.jwt.claims must be an object"
        ):
            principal_from_http_api_v2_event(event)

    def test_body_roles_cannot_upgrade_the_authorizer_principal(self) -> None:
        event = copy.deepcopy(self.fixture["post_assessment_event"])
        payload = json.loads(event["body"])
        payload["roles"] = ["Admin"]
        event["body"] = json.dumps(payload)

        principal = principal_from_http_api_v2_event(event)

        self.assertEqual({role.value for role in principal.roles}, {"User"})

    def test_flattened_or_malformed_group_claims_fail_closed(self) -> None:
        event = copy.deepcopy(self.fixture["post_assessment_event"])
        event["requestContext"]["authorizer"]["jwt"]["claims"]["cognito:groups"] = "User"

        with self.assertRaisesRegex(InvalidIdentityClaims, "cognito:groups must be an array"):
            principal_from_http_api_v2_event(event)

    def test_missing_and_non_owned_jobs_use_an_identical_response(self) -> None:
        principal = principal_from_http_api_v2_event(self.fixture["get_job_user_event"])
        non_owned_job = Job(
            job_id="job-001",
            job_type="ASSESSMENT",
            status=JobStatus.QUEUED,
            current_step=JobCurrentStep.LOAD_IAC,
            requested_by="another-subject",
            revision=0,
        )

        self.assertEqual(
            job_polling_proxy_response(principal, None),
            job_polling_proxy_response(principal, non_owned_job),
        )
        self.assertEqual(
            job_polling_proxy_response(principal, None),
            self.fixture["expected_proxy_responses"]["job_not_found"],
        )

    def test_admin_receives_public_job_projection_without_internal_fields(self) -> None:
        admin = principal_from_http_api_v2_event(self.fixture["get_job_admin_event"])
        job = Job(
            job_id="job-001",
            job_type="ASSESSMENT",
            status=JobStatus.QUEUED,
            current_step=JobCurrentStep.LOAD_IAC,
            requested_by="subject-001",
            revision=7,
        )

        response = job_polling_proxy_response(admin, job)

        self.assertEqual(response["statusCode"], 200)
        self.assertNotIn("requested_by", response["body"])
        self.assertNotIn("revision", response["body"])


if __name__ == "__main__":
    unittest.main()
