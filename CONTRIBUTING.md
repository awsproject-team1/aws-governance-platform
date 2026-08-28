# Contributing

이 문서는 사람 개발자를 위한 Repository 협업 규칙이다. 제품과 기술 설계는 `docs/`를 참조한다.

## 개발 흐름

```text
.ai/task/taskN.md (현재 기능 정의)
  → feature/fix/docs/refactor/test/chore branch
  → 구현
  → 관련 Test / Lint / Validation
  → Pull Request to dev
  → Required CI
  → 다른 팀원 최소 1명 Review
  → Merge Commit to dev
  → PROGRESS.md Completed 갱신
```

모든 기능이 완료되어 최종 통합·E2E/Release 검증이 가능한 시점에만 다음 흐름을 사람이 1회 수행합니다.

```text
dev → Pull Request → Required CI / Review → Merge Commit → main
```

`main`과 `dev`에 직접 Push하지 않습니다. `dev`에서도 직접 작업하지 않고 short-lived branch를 사용합니다.

## 작업 관리 (GitHub Issue 미사용)

- **GitHub Issue / Project는 사용하지 않습니다.** 개발 기간이 짧아 Issue/Project 운영 비용보다 최소한의 공용 진행관리를 우선합니다.
- **팀 공용 진행·마일스톤·의존성**은 Repository 루트 `PROGRESS.md`에서 관리합니다. Current / Completed / Next / Blocked / Milestone과 주요 Validation 상태만 짧게 유지합니다.
- **개인/Agent 세부 작업**은 `.ai/task/taskN.md`로 관리합니다. 기능마다 새 파일을 만들어 누적하며 이전 파일을 덮어쓰지 않습니다. `.ai/`는 Git 추적 대상이 아니며 공통 형식은 `templates/`로 공유합니다.
- 하나의 기능(하위 작업)은 새 Session에서 진행해 Context 오염을 막습니다. 각 `taskN.md`는 Goal / Scope / Acceptance Criteria / Out of Scope / 검증 결과를 담습니다.
- 개별 기능의 구현과 PR은 해당 `taskN.md`의 Scope, Acceptance Criteria, Test / Validation을 완료 기준으로 사용합니다.
- 본인 파트를 이어가다 과거 task를 다시 볼 때는 전체를 로드하지 않고 필요한 `taskN.md` 하나만 골라 읽습니다.
- 기능 완료 시 핵심 결정·결과 한 줄을 `PROGRESS.md`의 Completed에 올려 과거 기록의 진입점을 남깁니다.
- 아키텍처·계약에 지속 영향을 주는 결정은 `taskN.md`에만 두지 않고 `docs/decisions/` ADR로 옮깁니다. `.ai/`는 Git 추적 대상이 아니므로 task에만 남기면 머신을 바꿀 때 유실될 수 있습니다.
- 다른 Owner 영역이나 공통 Contract에 영향을 주면 구현 전에 관련 Owner와 합의하고 `PROGRESS.md`에 의존성을 명시합니다.
- 구현과 로컬 검증을 마친 뒤 Platform Repository PR을 `dev` 대상으로 생성합니다. Required CI는 PR 이후 Gate로 수행합니다.
- Review와 Merge는 사람이 수행합니다. `dev` Merge 후 담당자가 `PROGRESS.md`의 Completed를 갱신하고 다음 기능을 새 Session에서 시작합니다.

### 역할과 작업 조정

- A/B/C/D 영역 Owner는 자신의 기술 범위와 기능을 `.ai/task/`로 정의하고 관리합니다.
- 각 Owner는 `PROGRESS.md`에서 자기 항목의 상태와 직접적인 의존 관계만 갱신합니다.
- 사람이 `PROGRESS.md`에서 전체 일정과 병목을 확인하고, 전체 범위·Owner 간 우선순위·담당 재배치와 공통 Contract 변경을 종합 판단합니다.
- 공통 Contract는 Producer와 Consumer가 함께 검토합니다.
- 선행 작업이 필요한 경우 `PROGRESS.md`의 Blocked에 의존 대상과 사유를 적고, 순환 의존을 만들지 않으며 선행 작업이 끝난 기능부터 착수합니다.

## Branch Naming

기본 형식은 `type/kebab-case`입니다. Issue를 사용하지 않으므로 branch 이름에 Issue 번호를 넣지 않고 기능을 설명하는 이름을 사용합니다.

```text
feature/assessment-api
fix/policy-profile-validation
docs/update-contracts
chore/bootstrap-repository
```

일반 branch는 `dev`에서 만들고 `dev`로 PR합니다. `dev → main` 통합 PR은 주기적으로 만들지 않고, 모든 기능이 완료되어 최종 통합·E2E/Release 검증이 가능한 시점에 사람이 1회만 만듭니다.

허용되는 Platform Repository PR 경로는 아래 두 가지뿐입니다.

| Head | Base | 허용 목적 |
| --- | --- | --- |
| `feature/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, `chore/*` | `dev` | 일반 작업 |
| `dev` | `main` | 안정화 통합 |

다음 행위는 명시적으로 금지합니다.

- 작업 branch에서 `main`으로 직접 PR 생성 또는 Merge
- `main`이나 `dev`에 직접 Push 또는 force push
- Required Check, Review, Ruleset을 admin/bypass 권한으로 우회
- 자동 검사 실패 또는 대기 상태에서 Merge

잘못된 base로 PR을 만들었다면 Merge하지 말고 닫은 뒤 `dev` 대상으로 다시 생성합니다.

## Commit

Conventional Commits를 사용합니다.

- `feat`: 기능 추가
- `fix`: 결함 수정
- `docs`: 문서 변경
- `refactor`: 동작 변경 없는 구조 개선
- `test`: 테스트 추가·수정
- `chore`: 도구, CI, Repository 유지보수

예: `feat(agent): add assessment subgraph`. Scope는 선택사항이며 하나의 Commit은 이해 가능한 변경 단위를 담습니다.

## Pull Request

PR에는 다음을 포함합니다.

- What과 Why
- Scope (Included / Out of scope)
- 주요 변경 내용과 영역
- Validation과 Test 결과
- Architecture / Contract 영향 (Producer / Consumer)
- 갱신한 문서
- Security / Secret 확인
- 다른 Owner 확인 필요 여부

**GitHub Issue를 사용하지 않으므로 PR에 `Closes`/`Refs` 같은 Issue 연결 키워드를 쓰지 않습니다.** 목표 협업 정책상 Merge 조건은 해당 PR의 Required CI 통과와 다른 팀원 최소 1명 승인입니다. CI 실패 상태에서는 Merge하지 않고 Merge Commit만 사용합니다. 실제 강제 조건과의 차이는 아래 `GitHub Repository 보호 규칙`의 blocker를 따릅니다. Merge 후 더 이상 필요 없는 feature branch는 삭제할 수 있습니다. Merge 후 담당자가 `PROGRESS.md`의 Completed를 갱신합니다.

## GitHub Repository 보호 규칙

다음은 `main`과 `dev`에 적용할 목표 GitHub Ruleset입니다.

- Pull Request와 다른 팀원 최소 1명의 승인을 요구합니다.
- 최신 Push에 대한 승인과 Review 대화 해결을 요구합니다.
- 적용되는 Required CI가 성공해야 Merge할 수 있습니다.
- Force Push와 branch 삭제를 차단하고 Merge Commit만 허용합니다.
- 관리자 Bypass는 긴급 복구에 필요한 최소 인원으로 제한합니다.
- 일반 `main` 통합 PR은 `dev`에서만 생성합니다.

Path Filter로 실행되지 않을 수 있는 Workflow를 그대로 Required Check로 등록하지 않습니다. 모든 PR에서 완료 상태를 보고하는 공통 PR Gate를 두고 변경 영역별 검사를 연결하는 것이 목표입니다. 목표 규칙은 이 문서가 정본이며, 실제 강제 상태와 Bypass 대상은 GitHub Repository Settings가 정본입니다.

> **TODO / Merge protection blocker:** 현재 활성 Ruleset에는 Required Status Check가 등록되어 있지 않습니다. 모든 PR에서 항상 완료 상태를 보고하는 Workflow는 아래 `validate-pr-source`가 유일하며, 변경 영역별 검사를 연결하는 공통 PR Gate는 아직 없습니다. 따라서 Required CI 통과는 현재 절차상 Merge 조건일 뿐 GitHub이 기술적으로 강제하지 않습니다. 공통 PR Gate를 구현하고 `main`과 `dev` Ruleset의 Required Status Check로 등록하기 전에는 이 차이를 해소한 것으로 간주하지 않습니다.
>
> 현재 Ruleset은 2명 승인을 요구하고 Repository Settings는 Merge Commit, Squash Merge, Rebase Merge를 모두 허용하여, 이 문서의 목표인 최소 1명 승인과 Merge Commit만 허용하는 정책을 기술적으로 강제하지 못합니다. 목표 정책에 맞게 Repository Settings에서 Squash Merge와 Rebase Merge를 비활성화할 때까지 PR 운영에서는 Merge Commit만 선택합니다.

### `validate-pr-source` Required Check

문서 규칙만으로는 GitHub UI/API의 Merge를 차단할 수 없습니다. 위 표의 허용 경로는 `.github/workflows/validate-pr-source.yml`이 만드는 `validate-pr-source` check로 강제합니다.

판정 기준은 다음과 같습니다.

| base | 통과 조건 | 실패 예 |
| --- | --- | --- |
| `main` | head repository가 이 Repository이고 head branch가 `dev` | 작업 branch → `main`, Fork의 `dev` → `main` |
| `dev` | head branch가 `main`/`dev`가 아니고 `feature/`, `fix/`, `docs/`, `refactor/`, `test/`, `chore/` 중 하나로 시작 | `main` → `dev`, prefix 없는 branch → `dev` |
| 그 외 | 보호 대상이 아니므로 검사하지 않고 성공 | — |

- Trigger는 `pull_request`가 아니라 `pull_request_target`입니다. `pull_request`는 PR merge commit의 workflow 정의를 실행하므로, 금지된 branch가 같은 job 이름을 유지한 채 이 파일을 항상 성공하도록 고쳐 Required Check를 통과할 수 있습니다. `pull_request_target`은 base branch의 신뢰된 정의를 실행합니다.
- `pull_request_target`의 일반적인 위험은 PR 코드를 checkout해 실행하는 것입니다. 이 job은 checkout 없이 Event Metadata만 읽고 `contents: read` 권한만 가지므로 그 위험에 해당하지 않습니다.
- `pull_request_target`은 **base branch에 workflow 파일이 있을 때만** 실행됩니다. 따라서 이 파일이 `dev`에 Merge되기 전의 PR에는 check가 나타나지 않습니다.
- Path Filter와 branch filter를 두지 않아 **모든 PR에서 항상 완료 상태를 보고**합니다. 따라서 위 "Path Filter로 실행되지 않을 수 있는 Workflow를 Required Check로 등록하지 않는다"는 조건을 충족하며, Required Check로 등록해도 Merge가 대기 상태로 막히지 않습니다.

Required Check는 PR 템플릿의 체크박스가 아니라 GitHub가 기록하는 status check입니다. Workflow가 check를 생성하고 Ruleset이 그 check를 필수로 지정해야 실패·대기 상태의 Merge가 차단됩니다. GitHub는 허용되지 않은 PR의 **생성 자체**를 기본 Ruleset만으로 차단하지 않으므로, 생성 금지는 협업 규칙으로 지키고 Merge는 이 check로 자동 차단합니다.

현재 상태는 다음과 같습니다.

- Workflow: `validate-pr-source` check를 생성합니다. **완료**
- Ruleset: `main`의 Required Status Check로 등록해야 합니다. **미완료 — 저장소 관리자 작업**

Ruleset 등록 전까지 이 check는 실패해도 Merge를 막지 못합니다. check 이름을 바꾸면 Ruleset이 참조를 잃고 영원히 대기 상태가 되므로 workflow의 job name을 그대로 유지합니다.

## Test와 CI

GitHub Actions는 Path Filter로 변경 영역에 필요한 검사를 자동 선택하는 것을 원칙으로 합니다. 현재 실행 가능한 Workflow는 모든 PR의 Secret Scan, Python 변경 경로의 Python Checks, Frontend 변경 경로의 Frontend Checks입니다.

- 모든 PR: `validate-pr-source` (`main`/`dev` 대상 PR의 head/base 조합 검증)
- 모든 PR: Secret Scan
- Python 변경: Unit Test, Contract Test, Integration Test, Security Test, Ruff Lint/Format
- Frontend 변경: Frontend Model Test
- Terraform 변경(목표, 아직 Workflow 미구현): `terraform fmt -check`, `terraform validate`, TFLint, Checkov
- Frontend Build(목표, 아직 Workflow 미구현)
- E2E와 외부 의존 Integration: 모든 PR에 강제하지 않고 주요 Domain 연결, 주요 Merge, Demo/Release 전에 수행

`tests/integration`은 고정 Fixture만 사용하고 in-process로 끝나는 Domain 간 연결 Test를 담습니다. 이 범위는 빠르고 결정론적이므로 모든 Python PR에서 실행합니다. Agent/LLM 호출, 실제 AWS/GitHub API, 배포된 환경이 필요한 Test는 이 디렉터리에 넣지 않습니다. 그런 Test를 필수 Gate에 두면 외부 장애나 Credential 만료가 코드와 무관하게 Merge를 막습니다. 해당 Test는 별도 Suite와 Workflow로 분리하고 위 원칙대로 주요 Merge와 Demo/Release 전에 수행합니다.

현재 Python Checks는 `python -m ruff check .`, `python -m ruff format --check .`와 `tests/unit`, `tests/contract`, `tests/security`, `tests/integration`의 `unittest` discovery를 실행합니다. Frontend Checks는 `node --test`로 Frontend Model Test를 실행합니다. 두 Workflow 모두 Path Filter를 사용하므로 **어느 쪽도 그대로 Required Check로 등록하지 않습니다**. 둘 다 등록하면 Python만 바꾼 PR에서 Frontend Checks가, Frontend만 바꾼 PR에서 Python Checks가 영구히 대기 상태로 남아 Merge가 막힙니다. 위 `GitHub Repository 보호 규칙`의 공통 PR Gate가 구현되면 그 Gate 하나를 Required로 등록하고 두 Workflow를 그 아래에 연결합니다. 테스트 커버리지 수치는 MVP의 일률적 Gate로 두지 않으며 핵심 기능과 Contract Test의 존재를 우선합니다. 아직 manifest나 Workflow가 없는 영역의 구체 명령은 해당 기술 Bootstrap과 CI 구현 시 확정합니다.

### 로컬 실행

개발 도구는 `requirements-dev.txt`에, 배포 단위별 Runtime 의존성은 각 `requirements.txt`에 version이 고정되어 있습니다. Governance Domain의 `pypdf`가 개발 도구가 아니라 Runtime 의존성인 근거는 [ADR 0007](docs/decisions/0007-governance-document-ingestion-boundary.md)을 확인합니다.

```bash
python -m pip install --requirement requirements-dev.txt --requirement apps/backend/requirements.txt --requirement packages/governance/requirements.txt

node --test tests/unit/test_policy_frontend.mjs
```

`unittest`는 `packages.*`를 절대 import로 사용하므로 Repository Root에서 실행합니다.

## 문서와 Contract

- 제품 범위 변경: `docs/PRD.md`
- Architecture/Workflow 변경: `docs/DESIGN.md`
- API 변경: `docs/API.md`
- Data/Domain Contract 변경: `packages/contracts/`와 `docs/CONTRACTS.md`를 같은 PR에서 변경
- Naming 변경: `docs/NAMING.md`
- 장기 기술 결정: `docs/decisions/` ADR

제품 방향·구현 세부 모두 Repository 문서(`docs/`)가 정본입니다. **Notion 최종 계획서를 정본으로 참조하거나 함께 갱신하는 규칙은 사용하지 않습니다.** 확정되지 않은 설계를 구현 편의만으로 고정하지 않습니다.

## AWS 공동 개발환경

- 일상 개발: Local + Mock/Fixture
- 실제 AWS 검증: 팀 Shared Development AWS Account
- Integration/E2E/Demo: 필요한 실제 AWS Resource 사용 가능
- 공통 기준: 동일 AWS Account, 팀원별 IAM User, 동일 개발 권한, `us-east-1`, `dev`
- 개인 AWS Credential이나 공동 Access Key를 Repository에 저장·공유하지 않습니다.
- GitHub Actions와 Runtime은 개인 IAM User가 아닌 별도 Role을 사용하며 AWS 인증에는 OIDC를 사용합니다.

모든 로컬 개발이나 PR마다 AWS Resource를 만들 필요는 없습니다. 공유 Resource 충돌과 비용을 고려해 Fixture를 우선합니다.

## Secret 관리

- `.env`와 실제 Credential 파일은 commit하지 않습니다.
- `.env.example`에는 확정된 변수 이름과 비밀이 아닌 예시만 둡니다.
- GitHub, AWS, Cognito, 외부 서비스 Token을 코드·문서·로그에 붙이지 않습니다.
- 의심되는 값이 노출되면 commit 기록을 정리하는 것만으로 끝내지 말고 즉시 폐기·재발급 절차를 따릅니다.

## AI Coding Agent와 Worktree

AI가 생성한 변경에도 동일한 Branch, Commit, PR, Test, Review, CI 규칙을 적용합니다. 하위 작업(기능)마다 새 Session에서 진행하고 현재 작업은 `.ai/task/taskN.md`로 정의합니다. 복잡한 변경은 Research → Plan → Implement → Test → Review를 권장합니다. Git Worktree는 여러 branch 또는 Agent 작업을 병렬로 진행할 때 선택적으로 사용하며 필수는 아닙니다.

## Definition of Done

- Acceptance Criteria 충족
- 관련 구현 및 필요한 Fixture 완료
- 필요한 Unit/Contract Test 통과
- 변경 영역의 Lint/Build/Validation과 Required CI 통과
- Secret/민감정보 미포함
- 다른 팀원 최소 1명 승인
- 일반 작업은 `dev`에 Merge
- Architecture/Workflow/Contract 변경 시 관련 문서 갱신

문서 전용 작업과 E2E/배포가 필요한 작업의 추가 기준은 해당 `.ai/task/taskN.md`에서 명시합니다.
