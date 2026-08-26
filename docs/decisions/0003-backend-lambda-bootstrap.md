# Backend Lambda Bootstrap

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #12](https://github.com/awsproject-team1/aws-governance-platform/issues/12)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The architecture selects API Gateway and AWS Lambda, but the repository has no approved Backend framework, Python package boundary, runtime dependency manifest, deployment-package layout, or executable smoke validation. Selecting an HTTP framework or temporary product handler now would also select unresolved API Gateway payload, routing, response, error, and authentication contracts.

## Decision

- Use Python 3.14 and the standard library for the initial Backend Lambda boundary.
- Do not adopt FastAPI/Mangum, Chalice, AWS Lambda Powertools, or another framework in this bootstrap.
- Use `apps.backend` as the first-party Backend package and `apps.backend.handlers` as the product-handler namespace.
- Do not add a product `lambda_handler`, API Gateway event parser, HTTP response, endpoint, environment variable, IAM permission, or AWS resource in this change.
- Keep `_bootstrap_probe.invoke` private and non-deployable. It accepts opaque event/context objects and returns no product response; it exists only to validate import and invocation mechanics.
- Keep repository development tools in root `requirements-dev.txt`. Keep exact direct Backend runtime pins in `apps/backend/requirements.txt`; the file is intentionally dependency-free for this bootstrap.
- Use a ZIP-root staging model. The stage root exposes the `apps` namespace and contains `apps/backend`; third-party runtime dependencies are installed at the stage root. Include only the approved first-party import closure, not the entire monorepo.
- Do not adopt Lambda Layers, a Python build backend, wheel/sdist packaging, or a deployment script in this slice.
- Validate the layout by copying `apps/backend` into an isolated temporary stage root and importing/invoking the private probe in a subprocess without `PYTHONPATH`.
- Reconsider framework, event/response adapter, concrete handler string, transitive lock strategy, and reproducible ZIP automation when the first product API handler contract is approved.

## Consequences

- Backend code can establish import and packaging boundaries without claiming that a product API is runnable.
- The runtime package currently has no third-party dependencies and no AWS SDK usage.
- Each future product handler must be tied to an approved API event/response/error/auth contract and receive its own Unit/Contract tests.
- Lambda function resources, handler configuration, architecture, memory, timeout, environment, IAM, logging, and deployment artifact storage remain open decisions.
- The current staged-layout smoke test validates Python package placement but does not produce or deploy a Lambda artifact.

## Alternatives considered

- **FastAPI with Mangum:** Deferred because it would add routing and ASGI adapter conventions before the first API contract is implemented.
- **AWS Lambda Powertools:** Deferred until concrete logging, tracing, idempotency, and event-source requirements justify its runtime dependency and conventions.
- **Temporary health or 501 handler:** Rejected because even a temporary proxy response would create an undocumented endpoint and API Gateway response contract.
- **Installable root project or wheel:** Rejected because the repository has no approved build backend or monorepo package-discovery strategy.
- **Copy the entire monorepo into every Lambda ZIP:** Rejected because it obscures dependency ownership and unnecessarily includes tests, docs, frontend, and unrelated domains.

## References

- [AWS Lambda Python ZIP deployment packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Python bootstrap ADR](0001-python-bootstrap.md)
- [System design](../DESIGN.md)
