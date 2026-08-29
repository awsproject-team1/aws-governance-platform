# Backend Lambda Bootstrap

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #12](https://github.com/awsproject-team1/aws-governance-platform/issues/12)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

Architecture는 API Gateway와 AWS Lambda를 선택했지만, 저장소에는 승인된 Backend framework, Python package 경계, runtime 의존성 manifest, 배포 package layout, 실행 가능한 smoke 검증이 없다. 지금 HTTP framework나 임시 product handler를 선택하면 아직 확정되지 않은 API Gateway payload, routing, response, error, authentication contract까지 함께 선택하게 된다.

## Decision

- 초기 Backend Lambda 경계에는 Python 3.14와 표준 라이브러리를 사용한다.
- 이 bootstrap에서는 FastAPI/Mangum, Chalice, AWS Lambda Powertools 또는 다른 framework를 도입하지 않는다.
- first-party Backend package는 `apps.backend`, product-handler namespace는 `apps.backend.handlers`를 사용한다.
- 이 변경에서는 product `lambda_handler`, API Gateway event parser, HTTP response, endpoint, 환경변수, IAM 권한, AWS resource를 추가하지 않는다.
- `_bootstrap_probe.invoke`는 private·non-deployable로 유지한다. opaque event/context 객체를 받고 product response를 반환하지 않으며, import·invocation 동작만 검증하기 위해 존재한다.
- 저장소 개발 도구는 root `requirements-dev.txt`에 둔다. Backend runtime의 직접 의존성 pin은 `apps/backend/requirements.txt`에 두며, 이 bootstrap에서는 의도적으로 의존성이 없는 상태로 둔다.
- ZIP-root staging 모델을 사용한다. stage root는 `apps` namespace를 노출하고 `apps/backend`를 포함하며, third-party runtime 의존성은 stage root에 설치한다. 전체 monorepo가 아니라 승인된 first-party import closure만 포함한다.
- 이 slice에서는 Lambda Layer, Python build backend, wheel/sdist packaging, 배포 script를 도입하지 않는다.
- layout 검증은 `apps/backend`를 격리된 임시 stage root로 복사하고 `PYTHONPATH` 없이 subprocess에서 private probe를 import·invoke해서 수행한다.
- framework, event/response adapter, 구체 handler 문자열, transitive lock 전략, 재현 가능한 ZIP 자동화는 첫 product API handler contract가 승인될 때 재검토한다.

## Consequences

- Backend 코드는 product API가 실행 가능하다고 주장하지 않으면서 import·packaging 경계를 세울 수 있다.
- runtime package는 현재 third-party 의존성과 AWS SDK 사용이 없다.
- 이후 각 product handler는 승인된 API event/response/error/auth contract에 묶이고 각자 Unit/Contract test를 가져야 한다.
- Lambda function resource, handler 구성, architecture, memory, timeout, 환경, IAM, logging, 배포 artifact 저장은 Open Decision으로 남는다.
- 현재 staged-layout smoke test는 Python package 배치를 검증할 뿐 Lambda artifact를 생성하거나 배포하지 않는다.

## Alternatives considered

- **FastAPI with Mangum:** 첫 API contract를 구현하기 전에 routing과 ASGI adapter 관례를 추가하게 되므로 보류.
- **AWS Lambda Powertools:** 구체적인 logging, tracing, idempotency, event-source 요구가 runtime 의존성과 관례를 정당화할 때까지 보류.
- **임시 health 또는 501 handler:** 임시 proxy response라도 문서화되지 않은 endpoint와 API Gateway response contract를 만들게 되므로 기각.
- **설치 가능한 root project 또는 wheel:** 저장소에 승인된 build backend나 monorepo package-discovery 전략이 없으므로 기각.
- **전체 monorepo를 모든 Lambda ZIP에 복사:** 의존성 소유를 흐리고 test, docs, frontend, 무관한 domain을 불필요하게 포함하므로 기각.

## References

- [AWS Lambda Python ZIP deployment packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Python bootstrap ADR](0001-python-bootstrap.md)
- [System design](../DESIGN.md)
