# Cognito JWT and Backend RBAC Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #21](https://github.com/awsproject-team1/aws-governance-platform/issues/21)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

모든 Browser endpoint는 인증을 요구하며, Frontend control을 숨기는 것은 authorization 경계가 아니다. 플랫폼은 JWT cryptographic validation과 product action authorization을 지속적으로 분리해야 하되, Cognito resource 식별자, API Gateway payload 추출, 아직 승인되지 않은 전체 endpoint matrix를 추측해서는 안 된다.

## Decision

- 하나의 Amazon Cognito User Pool과 정확한 product group 이름 `Admin`, `User`를 사용한다.
- Backend API authorization에는 Cognito access token을 사용한다. 이 경계에서 ID token은 허용하지 않는다.
- API Gateway HTTP API JWT Authorizer가 Backend product handler를 호출하기 전에 token signature, issuer, 시간 유효성, 구성된 audience/client binding을 검증하도록 구성한다. 구체 User Pool, App Client, issuer, audience, route, scope, 배포 구성은 infrastructure 결정으로 남는다.
- Backend auth 모듈은 API Gateway event shape와 독립으로 유지한다. 이후 handler adapter가 authorizer-verified claim을 추출해 원래 JWT claim 의미를 `Principal.from_verified_claims`에 전달해야 한다.
- `token_use`는 `access`여야 하고, opaque `sub`와 `client_id`는 비어 있지 않은 문자열이어야 한다. `sub`에 UUID 형식을 강제하지 않는다.
- role은 `cognito:groups`에서만 읽는다. Cognito JWT 표현이 비어 있지 않은 문자열의 배열이어야 한다. 정확한 `Admin`, `User` 값만 매핑하며 대소문자를 구분한다.
- 알 수 없지만 형식이 올바른 Cognito group은 알려진 product role이 최소 하나 남아 있을 때만 무시한다. 없거나, 형식이 잘못됐거나, 전부 알 수 없는 group은 fail closed 한다.
- request body, query, path, header, 임의 custom claim에서 identity나 role 값을 받지 않는다.
- 정규화된 identity를 immutable `Principal`로 표현하고, 보호되는 각 연산마다 Backend에서 명시적 `Action`을 인가한다.
- `Admin`은 User 기능을 포함한다. 현재 승인된 action matrix는 의도적으로 `START_ASSESSMENT`와 `READ_JOB`로 제한하며 둘 다 `Admin`과 `User`에 허용한다. 등록되지 않았거나 typed되지 않은 모든 action은 거부한다.
- Backend 모듈에서 JWKS를 다운로드하거나 signature 검증을 반복하지 않는다. 이 경계를 위해 PyJWT, boto3, HTTP framework, AWS Lambda Powertools를 추가하지 않는다.
- 이 변경에서는 product Lambda handler나 환경변수를 추가하지 않는다. API Gateway event 추출과 HTTP error mapping은 승인된 handler contract에 속한다.

## Consequences

- API Gateway는 호출 전에 잘못된 token을 거부하고, Backend는 잘못된 token 용도, 불완전한 identity, 미지원 role, 인가되지 않은 action을 독립적으로 거부한다.
- authorization 결정은 작은 immutable identity만 사용하고 Frontend 표시나 request가 제공한 role 데이터를 신뢰하지 않는다.
- Cognito infrastructure 값과 secret 자료는 source와 fixture에 없다.
- 이후 action은 기본으로 접근을 상속하지 않고 명시적 policy 추가와 test를 요구한다.
- 첫 handler 작업은 실제 HTTP API authorizer event 표현을 fixture로 검증하고, 이 ADR의 claim 규칙을 약화하지 않으면서 adapt해야 한다.
- 사용자 초대, MFA, token revocation 동작, scope, 전체 endpoint-role matrix는 Open Decision으로 남는다.

## Alternatives considered

- **모든 Backend handler 안에서 JWT signature 검증·JWKS 조회:** API Gateway가 이미 선택된 cryptographic 신뢰 경계를 제공하는데, 두 번째 verifier는 설계되지 않은 의존성·cache·networking·key-rotation 동작을 추가하므로 기각.
- **API authorization에 Cognito ID token 사용:** access token이 API authorization 의미와 `client_id` claim을 담으므로 기각.
- **Frontend route나 menu 표시를 신뢰:** client가 presentation control을 우회할 수 있으므로 기각.
- **request 데이터나 custom claim에서 role 필드 수용:** 그런 contract가 없고 Cognito group 밖의 privilege-escalation 경로를 만들므로 기각.
- **모든 Cognito group을 product role로 취급:** 무관하거나 이후의 group이 암묵적으로 권한을 얻어서는 안 되므로 기각.
- **지금 전체 Admin/User endpoint matrix 정의:** 이 slice에서는 Assessment start와 Job read action만 승인됐으므로 기각.

## References

- [API Gateway HTTP API JWT authorizers](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html)
- [Amazon Cognito access tokens](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-using-the-access-token.html)
- [Backend Lambda bootstrap ADR](0003-backend-lambda-bootstrap.md)
- [System design](../DESIGN.md)
- [API interface](../API.md)
