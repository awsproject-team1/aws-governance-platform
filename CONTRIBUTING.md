# Contributing

이 문서는 사람 개발자를 위한 Repository 협업 규칙이다. 제품과 기술 설계는 `docs/`를 참조한다.

## 개발 흐름

```text
Issue
  → feature/fix/docs/refactor/test/chore branch
  → 구현
  → 관련 Test / Lint / Validation
  → Pull Request to dev
  → Required CI
  → 다른 팀원 최소 1명 Review
  → Merge Commit to dev
```

안정화 시에는 다음 흐름을 사용한다.

```text
dev → Pull Request → Required CI / Review → Merge Commit → main
```

`main`에 직접 Push하지 않습니다. `dev`에서도 직접 작업하지 않고 Issue에 연결된 short-lived branch를 사용합니다.

## Issue와 작업 단위

- 개발 시작 시 A/B/C/D Parent Issue를 만들고 Owner와 Scope를 고정합니다.
- 실제 구현은 Parent 아래 GitHub Native Sub-issue 또는 Bug 단위로 진행합니다.
- Parent 본문의 중복 체크리스트가 아니라 Native Sub-issue progress를 진행률 정본으로 사용합니다.
- Sub-issue 생성 시 Parent의 **Add sub-issue** 기능을 사용하거나 생성 직후 Native 관계를 연결합니다. 본문의 `Parent Issue: #123` 텍스트만으로는 Native 관계가 생기지 않습니다.
- Parent 전용 branch나 PR은 만들지 않습니다.
- Sub-issue는 Review와 Merge가 가능한 크기로 유지하되 억지로 지나치게 작게 나누지 않습니다.
- 개별 Sub-issue의 구현과 PR은 해당 Sub-issue의 Scope, Acceptance Criteria, Test / Validation을 완료 기준으로 사용합니다.
- Sub-issue 착수 시 Parent Issue의 Goal, Scope(제외 범위 포함), 직접 의존 관계를 한 번 확인합니다. 구현 중에는 Sub-issue만으로 범위를 판단할 수 없거나 Parent 변경 알림을 받은 경우에만 Parent 전체를 다시 확인합니다.
- Parent Issue의 전체 Acceptance Criteria와 주요 산출물은 모든 소속 Sub-issue가 완료된 뒤 Parent를 종료하는 단계에서 종합적으로 검증합니다.
- 다른 Owner 영역이나 공통 Contract에 영향을 주면 구현 전에 관련 Owner와 합의합니다.
- Sub-issue 구현과 로컬 검증을 마친 뒤 Platform Repository PR을 `dev` 대상으로 생성합니다. Required CI는 PR 이후 Gate로 수행합니다.
- PR은 Sub-issue를 `Refs`하고 자동 종료용 `Closes`를 사용하지 않습니다.
- Review와 Merge는 사람이 수행합니다. `dev` Merge를 확인한 뒤 사람이 Sub-issue를 닫고 다음 Sub-issue를 시작합니다.
- Parent 통합 검증도 마지막 Native Sub-issue로 생성해 같은 구현·검증·Review·Merge·수동 종료 절차를 적용합니다.
- 통합 검증 Sub-issue를 포함한 모든 Native Sub-issue가 종료되어 progress가 100%가 되면 Parent Issue를 닫습니다.

### 역할과 작업 조정

- A/B/C/D 영역 Owner는 공통 Issue Template에 따라 자신의 기술 범위와 최초·추가 Sub-issue를 정의하고 관리합니다.
- Parent Owner는 Parent의 목표, Scope, 의존 관계와 최종 완료 여부를 관리합니다.
- 각 Owner는 공유 Milestone과 Project에서 자기 Sub-issue의 Assignee, 상태와 직접적인 의존 관계를 갱신합니다. 이를 위해 모든 영역의 Issue 본문을 반복해서 읽는 별도 Milestone 관리 Agent를 두지 않습니다.
- 구현 중 발견한 Sub-issue가 기존 Parent Scope 안에서 현재 목표를 막는다면 해당 Owner가 현재 Milestone에 배치할 수 있습니다. 선택 기능과 후속 개선은 Backlog로 보냅니다.
- 사람이 공유 Project에서 전체 일정과 병목을 확인하고, Milestone 기간·전체 범위·Owner 간 우선순위·담당 재배치와 공통 Contract 변경을 종합 판단합니다.
- 공통 Contract는 Producer와 Consumer가 함께 검토하며, 실제 담당자는 Issue Assignee와 Project에서 관리합니다.

### Milestone과 Project

- Milestone은 Sprint 또는 통합 결과물처럼 마감일이 있는 작업 묶음으로 사용합니다.
- 같은 Sprint 또는 통합 결과물을 수행하는 A/B/C/D는 Owner별 Milestone을 따로 만들지 않고 하나의 공유 Milestone을 사용합니다.
- Parent Issue와 PR에는 Milestone을 지정하지 않고, 실제 완료 가능한 Sub-issue와 Bug에 지정합니다.
- 같은 작업을 Parent, Sub-issue, PR에 중복 배정하지 않으며 Milestone 진행률은 Sub-issue와 Bug의 종료 상태로 판단합니다.
- 현재 목표를 막는 새 작업만 진행 중인 Milestone에 추가하고, 선택 기능과 후속 개선은 다음 Milestone 또는 Backlog로 이동합니다.
- 실제 일정과 진행 상태는 Repository 문서가 아니라 GitHub Milestone과 Project를 정본으로 사용합니다.
- 전체 일정은 공유 Project의 Owner, Status, Priority, Planned Day와 Blocked 상태로 확인하며, 각 Owner는 자기 항목만 갱신합니다.

Project 상태는 다음 순서로 관리합니다.

```text
Proposed → Ready → In Progress → Review → Done
```

- `Proposed`: 새로 제안되어 범위와 일정이 아직 검토되지 않은 상태
- `Ready`: Scope, Acceptance Criteria, Test / Validation, Owner와 의존 관계가 확인된 상태
- `In Progress`: 구현 중인 상태
- `Review`: PR 검토 중인 상태
- `Done`: 필요한 검증과 `dev` Merge가 끝나고 Issue가 종료된 상태

### Parent와 의존 관계

- Sub-issue는 GitHub의 실제 Parent/Sub-issue 관계로 연결하며, Issue 본문의 Parent 번호만으로 연결됐다고 간주하지 않습니다.
- 선행 작업이 필요한 경우 GitHub의 `Blocked by` / `Blocking` 관계와 Issue의 `Depends on` / `Blocks`를 일치시킵니다.
- 공통 Contract, Repository Snapshot, Approval처럼 다른 영역을 막는 작업은 구현 시작 전에 의존 관계를 연결합니다.
- 순환 의존 관계를 만들지 않으며, 구현자는 `Ready` 상태이고 선행 작업이 끝난 Issue부터 착수합니다.

## Branch Naming

기본 형식은 `type/kebab-case`입니다.

```text
feature/11-assessment-api
fix/42-policy-profile-validation
docs/update-contracts
chore/bootstrap-repository
```

일반 branch는 `dev`에서 만들고 `dev`로 PR합니다. 안정화 통합 PR만 `dev`에서 `main`으로 보냅니다.

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
- Related Issue (`Refs` 또는 적절한 `Closes`)
- 주요 변경 내용과 영역
- Validation과 Test 결과
- Architecture / Contract 영향
- 갱신한 문서
- Security / Secret 확인
- 다른 Owner 확인 필요 여부

목표 협업 정책상 Merge 조건은 해당 PR의 Required CI 통과와 다른 팀원 최소 1명 승인입니다. CI 실패 상태에서는 Merge하지 않고 Merge Commit만 사용합니다. 실제 강제 조건과의 차이는 아래 `GitHub Repository 보호 규칙`의 blocker를 따릅니다. Merge 후 더 이상 필요 없는 feature branch는 삭제할 수 있습니다.

일반 PR은 `dev`를 대상으로 하므로 Related Issue에는 `Refs #번호`를 사용하고, Merge 후 해당 Sub-issue를 종료합니다. GitHub의 closing keyword는 기본 branch 대상 PR에서만 동작하므로 `Closes`는 실제 자동 종료 조건을 충족할 때만 사용합니다.

## GitHub Repository 보호 규칙

다음은 `main`과 `dev`에 적용할 목표 GitHub Ruleset입니다.

- Pull Request와 다른 팀원 최소 1명의 승인을 요구합니다.
- 최신 Push에 대한 승인과 Review 대화 해결을 요구합니다.
- 적용되는 Required CI가 성공해야 Merge할 수 있습니다.
- Force Push와 branch 삭제를 차단하고 Merge Commit만 허용합니다.
- 관리자 Bypass는 긴급 복구에 필요한 최소 인원으로 제한합니다.
- 일반 `main` 통합 PR은 `dev`에서만 생성합니다.

Path Filter로 실행되지 않을 수 있는 Workflow를 그대로 Required Check로 등록하지 않습니다. 모든 PR에서 완료 상태를 보고하는 공통 PR Gate를 두고 변경 영역별 검사를 연결하는 것이 목표입니다. 목표 규칙은 이 문서가 정본이며, 실제 강제 상태와 Bypass 대상은 GitHub Repository Settings가 정본입니다.

> **TODO / Merge protection blocker:** 현재 활성 Ruleset에는 Required Status Check가 등록되어 있지 않고, 모든 PR에서 항상 완료 상태를 보고하는 공통 PR Gate Workflow도 없습니다. 따라서 Required CI 통과는 현재 절차상 Merge 조건일 뿐 GitHub이 기술적으로 강제하지 않습니다. 공통 PR Gate를 구현하고 `main`과 `dev` Ruleset의 Required Status Check로 등록하기 전에는 이 차이를 해소한 것으로 간주하지 않습니다.
>
> 현재 Ruleset은 2명 승인을 요구하고 Repository Settings는 Merge Commit, Squash Merge, Rebase Merge를 모두 허용하여, 이 문서의 목표인 최소 1명 승인과 Merge Commit만 허용하는 정책을 기술적으로 강제하지 못합니다. 목표 정책에 맞게 Repository Settings에서 Squash Merge와 Rebase Merge를 비활성화할 때까지 PR 운영에서는 Merge Commit만 선택합니다.

## Test와 CI

GitHub Actions는 Path Filter로 변경 영역에 필요한 검사를 자동 선택하는 것을 원칙으로 합니다. 현재 실행 가능한 Workflow는 모든 PR의 Secret Scan, Python 변경 경로의 Python Checks, Frontend 변경 경로의 Frontend Checks입니다.

- 모든 PR: Secret Scan
- Python 변경: Unit Test, Contract Test, Integration Test, Ruff Lint/Format
- Frontend 변경: Frontend Model Test
- Terraform 변경(목표, 아직 Workflow 미구현): `terraform fmt -check`, `terraform validate`, TFLint, Checkov
- Frontend Build(목표, 아직 Workflow 미구현)
- Integration/E2E: 모든 PR에 강제하지 않고 주요 Domain 연결, 주요 Merge, Demo/Release 전에 수행

현재 Python Checks는 `python -m ruff check .`, `python -m ruff format --check .`와 `tests/unit`, `tests/contract`, `tests/security`, `tests/integration`의 `unittest` discovery를 실행합니다. Frontend Checks는 `node --test`로 Frontend Model Test를 실행합니다. 두 Workflow는 서로 다른 Path Filter를 사용하므로 Required Check로 등록할 때 함께 등록해야 합니다. 테스트 커버리지 수치는 MVP의 일률적 Gate로 두지 않으며 핵심 기능과 Contract Test의 존재를 우선합니다. 아직 manifest나 Workflow가 없는 영역의 구체 명령은 해당 기술 Bootstrap과 CI 구현 시 확정합니다.

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

상위 제품 결정이 바뀌면 Notion `최종 계획서`도 함께 갱신합니다. 확정되지 않은 설계를 구현 편의만으로 고정하지 않습니다.

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
- GitHub, AWS, Cognito, 외부 서비스 Token을 코드·문서·Issue·로그에 붙이지 않습니다.
- 의심되는 값이 노출되면 commit 기록을 정리하는 것만으로 끝내지 말고 즉시 폐기·재발급 절차를 따릅니다.

## AI Coding Agent와 Worktree

AI가 생성한 변경에도 동일한 Issue, Branch, Commit, PR, Test, Review, CI 규칙을 적용합니다. 복잡한 변경은 Research → Plan → Implement → Test → Review를 권장합니다. Git Worktree는 여러 branch 또는 Agent 작업을 병렬로 진행할 때 선택적으로 사용하며 필수는 아닙니다.

## Definition of Done

- Acceptance Criteria 충족
- 관련 구현 및 필요한 Fixture 완료
- 필요한 Unit/Contract Test 통과
- 변경 영역의 Lint/Build/Validation과 Required CI 통과
- Secret/민감정보 미포함
- 다른 팀원 최소 1명 승인
- 일반 작업은 `dev`에 Merge
- Architecture/Workflow/Contract 변경 시 관련 문서 갱신

문서 전용 작업과 E2E/배포가 필요한 작업의 추가 기준은 해당 Issue에서 명시합니다.
