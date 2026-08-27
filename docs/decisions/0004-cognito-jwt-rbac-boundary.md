# Cognito JWT and Backend RBAC Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #21](https://github.com/awsproject-team1/aws-governance-platform/issues/21)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

Every Browser endpoint requires authentication, and hiding Frontend controls is not an authorization boundary. The platform needs a durable split between JWT cryptographic validation and product action authorization without guessing Cognito resource identifiers, API Gateway payload extraction, or a complete endpoint matrix that has not been approved.

## Decision

- Use one Amazon Cognito User Pool and the exact product group names `Admin` and `User`.
- Use Cognito access tokens for Backend API authorization. ID tokens are not accepted for this boundary.
- Configure an API Gateway HTTP API JWT Authorizer to validate token signature, issuer, time validity, and configured audience/client binding before invoking a Backend product handler. Concrete User Pool, App Client, issuer, audience, route, scope, and deployment configuration remain infrastructure decisions.
- Keep the Backend auth module independent of API Gateway event shape. A future handler adapter must extract authorizer-verified claims and pass their original JWT claim meanings to `Principal.from_verified_claims`.
- Require `token_use` to equal `access`, and require non-empty opaque `sub` and `client_id` strings. Do not impose a UUID format on `sub`.
- Read roles only from `cognito:groups`. Require its Cognito JWT representation to be an array of non-empty strings. Map only exact `Admin` and `User` values; matching is case-sensitive.
- Ignore an unknown but well-formed Cognito group only when at least one known product role remains. Missing, malformed, or entirely unknown groups fail closed.
- Do not accept identity or role values from the request body, query, path, headers, or arbitrary custom claims.
- Represent the normalized identity as an immutable `Principal` and authorize an explicit `Action` in the Backend for each protected operation.
- `Admin` includes User capabilities. The currently approved action matrix is intentionally limited to `START_ASSESSMENT` and `READ_JOB`, both allowed to `Admin` and `User`. Every unregistered or untyped action is denied.
- Do not download JWKS or repeat signature verification in the Backend module. Do not add PyJWT, boto3, an HTTP framework, or AWS Lambda Powertools for this boundary.
- Do not add a product Lambda handler or environment variables in this change. API Gateway event extraction and HTTP error mapping belong to the approved handler contract.

## Consequences

- API Gateway rejects invalid tokens before invocation, while the Backend independently rejects the wrong token purpose, incomplete identities, unsupported roles, and unauthorized actions.
- Authorization decisions use only a small immutable identity and do not trust Frontend visibility or request-supplied role data.
- Cognito infrastructure values and secret material are absent from source and fixtures.
- A future action requires an explicit policy addition and tests rather than inheriting access by default.
- The first handler work must validate the real HTTP API authorizer event representation with a fixture and adapt it without weakening the claim rules in this ADR.
- User invitation, MFA, token revocation behavior, scopes, and the complete endpoint-role matrix remain open decisions.

## Alternatives considered

- **Verify JWT signatures and fetch JWKS inside every Backend handler:** Rejected because API Gateway already provides the selected cryptographic trust boundary, while a second verifier would add dependency, cache, networking, and key-rotation behavior that has not been designed.
- **Use Cognito ID tokens for API authorization:** Rejected because the access token carries API authorization semantics and a `client_id` claim.
- **Trust Frontend route or menu visibility:** Rejected because clients can bypass presentation controls.
- **Accept role fields from request data or a custom claim:** Rejected because no such contract exists and it would create a privilege-escalation path outside Cognito groups.
- **Treat every Cognito group as a product role:** Rejected because unrelated or future groups must not gain permissions implicitly.
- **Define the complete Admin/User endpoint matrix now:** Rejected because only Assessment start and Job read actions are approved in this slice.

## References

- [API Gateway HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
- [Amazon Cognito access tokens](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html)
- [Backend Lambda bootstrap ADR](0003-backend-lambda-bootstrap.md)
- [System design](../DESIGN.md)
- [API interface](../API.md)
