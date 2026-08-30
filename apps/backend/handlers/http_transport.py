"""Pure API Gateway HTTP API v2 transport helpers for approved Backend routes."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Final

from apps.backend.auth import (
    Action,
    AuthorizationDenied,
    Principal,
    authorize,
)
from apps.backend.jobs.access import authorize_job_read
from apps.backend.jobs.models import Job
from packages.contracts import (
    ApiError,
    ApiErrorResponse,
    AssessmentAcceptedResponse,
    InitialAssessmentStartRequest,
)

HTTP_API_V2: Final = "2.0"
JSON_CONTENT_TYPE: Final = "application/json; charset=utf-8"


class InvalidHttpApiEvent(ValueError):
    """Raised when an API Gateway HTTP API v2 event breaks the approved transport shape."""


def principal_from_http_api_v2_event(event: object) -> Principal:
    """Normalize only authorizer-provided claims into a fail-closed Principal."""
    claims = _require_mapping_path(
        event,
        ("requestContext", "authorizer", "jwt", "claims"),
        "requestContext.authorizer.jwt.claims",
    )
    return Principal.from_verified_claims(claims)


def parse_initial_assessment_start_request(event: object) -> InitialAssessmentStartRequest:
    """Parse the approved POST /assessments HTTP API v2 request body."""
    _require_route(event, method="POST", route_key="POST /assessments")
    payload = _parse_json_body(event)
    return InitialAssessmentStartRequest.from_dict(payload)


def extract_job_id(event: object) -> str:
    """Return the opaque job_id from an approved GET /jobs/{job_id} event."""
    _require_route(event, method="GET", route_key="GET /jobs/{job_id}")
    parameters = _require_mapping_path(event, ("pathParameters",), "pathParameters")
    job_id = parameters.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise InvalidHttpApiEvent("pathParameters.job_id must be a non-empty string")
    return job_id


def assessment_accepted_proxy_response(
    response: AssessmentAcceptedResponse,
) -> dict[str, object]:
    """Serialize a future start use case's accepted response without starting it here."""
    if not isinstance(response, AssessmentAcceptedResponse):
        raise TypeError("response must be an AssessmentAcceptedResponse")
    return json_proxy_response(202, response.to_dict())


def job_polling_proxy_response(principal: Principal, job: Job | None) -> dict[str, object]:
    """Serialize a public Job projection without revealing ownership or existence details."""
    authorize(principal, Action.READ_JOB)
    if job is None:
        return job_not_found_proxy_response()

    try:
        authorize_job_read(principal, job)
    except AuthorizationDenied:
        return job_not_found_proxy_response()

    return json_proxy_response(200, job.to_response().to_dict())


def invalid_request_proxy_response() -> dict[str, object]:
    """Return the stable public response for malformed HTTP transport input."""
    return error_proxy_response(
        400,
        code="INVALID_REQUEST",
        message="Request does not match the HTTP API contract",
    )


def validation_error_proxy_response() -> dict[str, object]:
    """Return the stable public response for a well-formed but invalid request body."""
    return error_proxy_response(
        422,
        code="VALIDATION_ERROR",
        message="Request body does not match the required schema",
    )


def unauthorized_proxy_response() -> dict[str, object]:
    """Return the stable public response for absent or malformed verified identity claims."""
    return error_proxy_response(
        401,
        code="UNAUTHORIZED",
        message="Authentication credentials are invalid",
    )


def job_not_found_proxy_response() -> dict[str, object]:
    """Return the shared missing/non-owned Job response."""
    return error_proxy_response(404, code="NOT_FOUND", message="Job not found")


def error_proxy_response(status_code: int, *, code: str, message: str) -> dict[str, object]:
    """Serialize one approved public API error envelope as an HTTP API proxy response."""
    return json_proxy_response(
        status_code,
        ApiErrorResponse(error=ApiError(code=code, message=message)).to_dict(),
    )


def json_proxy_response(status_code: int, payload: Mapping[str, object]) -> dict[str, object]:
    """Return the deterministic JSON proxy response consumed by HTTP API v2."""
    if isinstance(status_code, bool) or not isinstance(status_code, int):
        raise TypeError("status_code must be an integer")
    if status_code < 100 or status_code > 599:
        raise ValueError("status_code must be between 100 and 599")
    if not isinstance(payload, Mapping):
        raise TypeError("payload must be a mapping")

    return {
        "statusCode": status_code,
        "headers": {"content-type": JSON_CONTENT_TYPE},
        "body": json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
        "isBase64Encoded": False,
    }


def _require_route(event: object, *, method: str, route_key: str) -> Mapping[str, object]:
    root = _require_http_api_v2_event(event)
    actual_route = root.get("routeKey")
    if actual_route != route_key:
        raise InvalidHttpApiEvent(f"routeKey must be {route_key!r}")

    http = _require_mapping_path(root, ("requestContext", "http"), "requestContext.http")
    if http.get("method") != method:
        raise InvalidHttpApiEvent(f"requestContext.http.method must be {method!r}")
    return root


def _parse_json_body(event: object) -> Mapping[str, object]:
    root = _require_http_api_v2_event(event)
    if root.get("isBase64Encoded") is not False:
        raise InvalidHttpApiEvent("isBase64Encoded must be false")

    body = root.get("body")
    if not isinstance(body, str) or not body.strip():
        raise InvalidHttpApiEvent("body must be a non-empty JSON string")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise InvalidHttpApiEvent("body must contain valid JSON") from error
    if not isinstance(payload, Mapping):
        raise InvalidHttpApiEvent("body must contain a JSON object")
    return payload


def _require_http_api_v2_event(event: object) -> Mapping[str, object]:
    if not isinstance(event, Mapping):
        raise InvalidHttpApiEvent("event must be an object")
    if event.get("version") != HTTP_API_V2:
        raise InvalidHttpApiEvent("event version must be '2.0'")
    return event


def _require_mapping_path(
    value: object,
    path: tuple[str, ...],
    label: str,
) -> Mapping[str, object]:
    current = _require_http_api_v2_event(value)
    for key in path:
        candidate = current.get(key)
        if not isinstance(candidate, Mapping):
            raise InvalidHttpApiEvent(f"{label} must be an object")
        current = candidate
    return current


__all__ = [
    "HTTP_API_V2",
    "InvalidHttpApiEvent",
    "assessment_accepted_proxy_response",
    "error_proxy_response",
    "extract_job_id",
    "invalid_request_proxy_response",
    "job_not_found_proxy_response",
    "job_polling_proxy_response",
    "json_proxy_response",
    "parse_initial_assessment_start_request",
    "principal_from_http_api_v2_event",
    "unauthorized_proxy_response",
    "validation_error_proxy_response",
]
