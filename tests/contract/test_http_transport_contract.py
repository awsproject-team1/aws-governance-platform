"""Contract tests for the approved API Gateway HTTP API v2 adapter boundary."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from apps.backend.handlers.http_transport import (
    InvalidHttpApiEvent,
    assessment_accepted_proxy_response,
    extract_job_id,
    invalid_request_proxy_response,
    parse_initial_assessment_start_request,
    principal_from_http_api_v2_event,
    unauthorized_proxy_response,
    validation_error_proxy_response,
)
from packages.contracts import AssessmentAcceptedResponse

REPO = Path(__file__).resolve().parents[2]


class HttpTransportContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(
            (REPO / "fixtures" / "http" / "api-gateway-v2-contract.json").read_text(
                encoding="utf-8"
            )
        )

    def test_post_event_normalizes_only_the_authorizer_claims_and_strict_body(self) -> None:
        event = self.fixture["post_assessment_event"]

        principal = principal_from_http_api_v2_event(event)
        request = parse_initial_assessment_start_request(event)

        self.assertEqual(principal.subject, "subject-001")
        self.assertEqual(request.to_dict(), json.loads(event["body"]))

    def test_get_event_extracts_the_opaque_path_parameter(self) -> None:
        self.assertEqual(extract_job_id(self.fixture["get_job_user_event"]), "job-001")

    def test_assessment_accepted_response_uses_the_fixed_v2_proxy_shape(self) -> None:
        response = assessment_accepted_proxy_response(AssessmentAcceptedResponse(job_id="job-001"))

        self.assertEqual(response, self.fixture["expected_proxy_responses"]["assessment_accepted"])

    def test_public_transport_errors_use_fixed_proxy_envelopes(self) -> None:
        expected = self.fixture["expected_proxy_responses"]

        self.assertEqual(invalid_request_proxy_response(), expected["invalid_request"])
        self.assertEqual(validation_error_proxy_response(), expected["validation_error"])
        self.assertEqual(unauthorized_proxy_response(), expected["unauthorized"])

    def test_event_version_route_method_and_body_encoding_are_not_guessed(self) -> None:
        base = self.fixture["post_assessment_event"]
        invalid_events = (
            ({**base, "version": "1.0"}, "event version must be '2.0'"),
            ({**base, "routeKey": "POST /jobs"}, "routeKey must be 'POST /assessments'"),
            (
                {
                    **base,
                    "requestContext": {
                        **base["requestContext"],
                        "http": {"method": "GET"},
                    },
                },
                "requestContext.http.method must be 'POST'",
            ),
            ({**base, "isBase64Encoded": True}, "isBase64Encoded must be false"),
            ({**base, "body": "not-json"}, "body must contain valid JSON"),
        )

        for event, message in invalid_events:
            with self.subTest(event=event):
                with self.assertRaisesRegex(InvalidHttpApiEvent, message):
                    parse_initial_assessment_start_request(event)

    def test_well_formed_json_still_uses_the_strict_assessment_request_contract(self) -> None:
        event = copy.deepcopy(self.fixture["post_assessment_event"])
        payload = json.loads(event["body"])
        payload["unapproved_field"] = True
        event["body"] = json.dumps(payload)

        with self.assertRaisesRegex(ValueError, "unknown field"):
            parse_initial_assessment_start_request(event)


if __name__ == "__main__":
    unittest.main()
