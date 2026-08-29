# Python Bootstrap Toolchain

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #10](https://github.com/awsproject-team1/aws-governance-platform/issues/10)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

저장소는 Python linting·testing 요구사항은 정의했지만 Python 버전, 의존성 설치 방법, test runner, 실행 가능한 검증 명령, CI workflow는 아직 정의하지 않았다. Product API, domain contract, frontend tooling, AWS resource는 여전히 Open Decision이며 tooling bootstrap에서 추론해서는 안 된다.

## Decision

- 초기 Python toolchain에는 Python 3.14를 사용한다. 승인된 로컬 환경과 일치하고 AWS Lambda 지원 runtime이다.
- 초기 bootstrap에는 표준 `pip`와 `requirements-dev.txt`의 정확한 직접 의존성 pin을 사용한다.
- third-party 의존성이 필요한 test framework가 정당화되기 전까지 표준 라이브러리 `unittest` runner를 사용한다.
- Python linting·formatting에는 Ruff를 사용하고 root `pyproject.toml`에 구성한다.
- Python lint, format 검사, unit test는 path-filter된 GitHub Actions workflow에서 실행한다.
- `dev` 또는 `main`을 대상으로 하는 모든 pull request에 Gitleaks CLI 8.30.1을 실행한다. 다운로드한 Linux archive는 실행 전에 게시된 SHA-256 checksum으로 검증한다.
- pull request에서는 정확한 base-to-head 범위가 도입한 모든 commit을 scan해 무관한 remote branch가 결과를 오염시키지 못하게 한다. `workflow_dispatch`는 명시적 full-history audit으로 유지한다.
- Python package는 정확한 버전으로, GitHub Actions는 immutable commit SHA로, 다운로드하는 CI 도구는 버전과 checksum으로 pin한다.

## Consequences

- 로컬 개발과 CI는 Python 3.14를 요구한다.
- 첫 검증 경로의 외부 Python 개발 의존성은 Ruff 하나다.
- 이 결정은 저장소 tooling만 정한다. backend framework, domain schema 라이브러리, frontend package manager, LangGraph runtime, AWS resource, public API endpoint를 선택하지 않는다.
- Application 의존성과 transitive lock 전략은 첫 실행 가능한 application slice가 승인될 때 재검토한다.
- secret-scan workflow는 pin된 Gitleaks CLI release를 GitHub에서 다운로드하고 SHA-256 checksum이 허용값과 다르면 archive를 거부한다.

## Alternatives considered

- **Python 3.13:** AWS Lambda가 지원하지만 이미 승인된 로컬 Python 3.14 환경과 달라진다.
- **uv, Poetry, pip-tools:** 저장소가 아직 multi-package lock 전략을 필요로 하지 않으므로 보류.
- **pytest:** 초기 import smoke test에 third-party test framework가 필요 없으므로 보류.
- **Frontend와 Python bootstrap을 함께:** 같은 변경에서 무관한 Node, bundler, frontend test 결정을 고정하는 것을 피하려 기각.

## References

- [AWS Lambda runtimes](https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html)
- [Repository agent guide](../../AGENTS.md)
- [Contributing guide](../../CONTRIBUTING.md)
