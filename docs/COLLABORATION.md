# Collaboration Operating Guide

이 문서는 A/B/C/D 역할이 같은 Repository에서 병렬 개발할 때 따르는 협업 운영 정본이다. 제품 Architecture, API, Domain Contract를 복사하지 않는다. 그 내용은 관련 `docs/`, 실행 가능한 Contract, ADR을 따른다.

## 1. Source of Truth와 우선순위

서로 다른 기록이 충돌하면 아래 우선순위와 각 기록의 적용 범위를 따른다.

| 우선순위 | 기록 | 책임 범위 |
| --- | --- | --- |
| 1 | GitHub Actions / Ruleset / Branch Protection | 실제 merge·배포를 기술적으로 허용하거나 차단하는 설정 |
| 2 | GitHub Issue / Project | 실행 작업의 Owner, Parent/Sub-issue 관계, 상태, 의존성, Milestone |
| 3 | `docs/COLLABORATION.md` | 작업 생명주기, Branch/PR/Review, 역할 간 협업, Agent 운영 |
| 4 | `CONTRIBUTING.md` | 사람 개발자의 실행 절차와 로컬 검증 안내 |
| 5 | `AGENTS.md` | Coding Agent의 Context 탐색, 작업 경계, 원격 작업 제한 |
| 6 | Repository `docs/` 및 `docs/decisions/` | 제품·설계·Interface·Naming과 지속적인 기술 결정 |
| 7 | Notion | 회의 배경, 논의 이력, 아직 확정되지 않은 선택지 |

- 실행 가능한 Schema가 있는 경우 Contract의 정본은 `packages/contracts/` 코드이며, 설명 문서는 `docs/CONTRACTS.md`다.
- Notion 회의록은 구현 지시나 완료 기준을 대체하지 않는다. 구현에 영향을 주는 확정 결정은 Issue/PR와 필요한 ADR, 관련 Repository 문서에 반영한다.
- GitHub 설정과 문서가 다르면 GitHub가 현재 실행을 제한하는 방식이 즉시 적용된다. 문서와 설정의 차이는 해당 Parent Issue 또는 `Open Decision`으로 기록하고, Owner가 정본을 하나로 맞춘다.
- 제품·Contract·보안 경계를 바꾸는 충돌은 임시 구현으로 해결하지 않는다. 영향 Owner의 합의와 필요 시 ADR이 선행되어야 한다.

## 2. 개발 작업 생명주기

```text
Parent Issue
  └─ Sub-issue 또는 Bug Issue
       → short-lived branch (latest dev)
       → PR → dev
       → Review + CI + Squash Merge
       → Sub-issue Done
Parent Feature Done
  → dev → main 통합 PR
  → Release / Demo Done
```

### Issue 유형

- **Parent Issue**: 사용자 가치, 기능 목표, 범위, 성공 조건, 필요한 Sub-issue, 통합 기준을 관리한다. Parent 자체에는 전용 구현 Branch나 closing PR을 만들지 않는다.
- **Sub-issue**: 한 Owner가 책임질 수 있는 구현 단위다. Scope, Out of Scope, Acceptance Criteria, Contract 영향, 의존성, Validation을 포함하고 Parent의 native sub-issue로 연결한다.
- **Bug Issue**: 재현 가능한 결함 단위다. 재현 절차, 기대/실제 결과, 영향, 회귀 방지 조건을 포함한다. 기능 Parent에 속하면 연결하고, 독립적인 운영 결함이면 자체 Milestone으로 관리할 수 있다.

### 완료 상태

- **Sub-issue Done**: Scope와 Acceptance Criteria를 충족하고, 필요한 Fixture/Test/문서가 반영되며, `dev` PR이 Review·적용 CI를 통과해 merge된 상태다. `Blocked`가 남아 있으면 Done이 아니다.
- **Parent Feature Done**: 필수 Sub-issue와 Bug Issue가 모두 Done이고, Parent 수준에도 해소되지 않은 `Blocked` 의존성이 없으며, Parent의 통합 Acceptance Criteria·Consumer 확인·통합 검증이 완료된 상태다. Parent는 사람이 최종 확인 후 닫는다.
- **Release / Demo Done**: `dev → main` 통합 PR이 merge되고, 릴리스·데모에 필요한 E2E/배포 전 검증, 승인, 결과 기록이 끝난 상태다. `main` merge만으로 자동 완료되지 않는다.

## 3. Branch / PR / Review / Merge 기준

### Branch와 PR 경로

- 작업은 최신 `dev`에서 `type/<issue-number>-kebab-case`로 시작한다. 허용 `type`은 `feature`, `fix`, `docs`, `refactor`, `test`, `chore`다.

```text
feature/123-assessment-api
fix/456-policy-profile-validation
docs/789-collaboration-guide
```

- 일반 개발·문서·Bug PR의 base는 항상 `dev`다. `main` 대상 PR은 같은 Repository의 `dev → main` 통합 PR만 허용한다.
- 다른 기능 Branch를 기반으로 작업하거나 다른 기능 Branch로 PR하지 않는다. 선행 산출물이 필요하면 `dev` merge를 기다리거나 Fixture/Fake/Mock으로 병렬화한다.
- PR 전 `dev` 최신 변경을 반영하고 충돌·회귀 위험을 확인한다. 이미 공유된 Branch의 history를 force push하지 않는다.

### Review와 merge

- 모든 PR은 적용되는 CI 성공, 최소 한 명의 다른 팀원 Review, 필요한 Owner/Consumer Review를 받아야 한다.
- 일반 `Sub-issue`/`Bug Issue` PR은 **Squash Merge**로 `dev`에 병합한다. Squash commit 메시지는 변경 목적과 Issue를 식별할 수 있어야 한다.
- `dev → main` 통합 PR의 merge 방식은 릴리스 이력을 보존할 수 있는 **Merge Commit**을 기본으로 한다. GitHub에서 허용할 방식은 Ruleset/Repository Settings와 일치시켜야 한다.
- merge 뒤 Branch는 더 이상 참조되지 않고 handoff가 기록된 경우 삭제한다. Parent Issue와 Project 상태는 사람이 확인해 갱신한다.

### `Refs`와 `Closes`

- `Closes #<issue>`는 이 PR merge만으로 해당 **Sub-issue 또는 Bug Issue**의 Done 조건이 충족될 때만 쓴다.
- `Refs #<issue>`는 기반 작업, 부분 구현, 조사, 후속 PR이 남은 변경처럼 Issue를 열어 두어야 할 때 쓴다.
- Parent Issue는 PR closing keyword로 닫지 않는다. 모든 필수 Sub-issue 완료와 통합 검증 뒤 사람이 닫는다.
- GitHub의 자동 종료 동작은 Repository의 default branch 설정에 따라 달라질 수 있다. 자동 종료가 동작하지 않으면 merge 담당자가 Issue 상태를 수동으로 확인·갱신한다.

### 긴급 수정과 예외

- 긴급 수정도 원칙적으로 `fix/<issue-number>-... → dev`와 Review·CI를 따른다.
- `main` hotfix, CI/Review 예외, 관리자 bypass는 보안·서비스 복구를 위한 최소 경우만 허용한다. 사람 Owner가 사유·영향·승인자·후속 검증을 Issue와 PR에 남기고, 복구 뒤 즉시 `dev` 동기화와 회고를 수행한다.
- 예외가 반복되거나 정책을 바꾸면 `Open Decision`과 필요 시 ADR로 승격한다.

## 4. 역할 간 Contract와 의존성

### Owner 경계

| 역할 | 기본 책임 영역 |
| --- | --- |
| A | Platform / API / Auth / Data |
| B | Governance / Policy / Knowledge |
| C | Agent Platform / Assessment |
| D | Remediation / IaC / GitHub / Deployment |
| Shared | `packages/contracts/`, `packages/common/`, `fixtures/`, `tests/`, `docs/` |

- Issue에는 단일 실행 Owner를 둔다. 여러 영역이 관련되어도 누가 최종 상태와 handoff를 책임지는지 명확해야 한다.
- 공유 Contract에는 **Contract Owner**를 지정한다. Contract Owner는 변경 범위, 호환성, 버전·migration 필요성, 테스트·문서 갱신을 조율한다.
- **Producer**는 변경안, Fixture, Fake/Mock 가능 여부, migration·배포 영향과 검증 근거를 제공한다. **Consumer**는 사용 방식, 호환성, fallback과 통합 검증 조건을 검토한다.
- Consumer가 있는 Contract 변경은 Producer 단독 승인으로 merge하지 않는다. 영향받는 named Consumer Owner가 해당 PR revision에 대해 명시적으로 승인해야 한다. Review 요청이나 단순 Issue 기록은 승인으로 간주하지 않는다.

### 의존성 상태

| 상태 | 의미 | 다음 행동 |
| --- | --- | --- |
| `None` | 현재 추적할 외부 의존성이 없음 | 별도 의존성 조치 없이 Scope와 Validation을 진행한다. |
| `Blocked` | 선행 결정·Contract·환경·승인이 없어 구현 또는 검증을 진행할 수 없음 | GitHub Issue 관계와 Project 상태에 사유·Owner·해결 조건을 기록하고 선행 작업을 기다린다. |
| `Mockable` | 실제 Producer 산출물 전에도 합의된 Schema와 Fixture/Fake/Mock으로 독립 구현·테스트가 가능함 | Mock 경계와 실제 통합 조건을 Issue/PR에 기록하고 병렬 작업한다. |
| `Integrated` | 실제 Producer 산출물로 연결해 Consumer 통합 검증까지 완료함 | 관련 Issue에 검증 결과를 남기고 Parent 완료 조건에 반영한다. |

- **Fixture**는 재현 가능한 고정 입력·기대 결과다. **Fake**는 실제 의존성을 대신하는 단순 동작 구현이다. **Mock**은 상호작용·호출 기대를 검증하는 테스트 대역이다.
- 테스트 대역은 합의된 Contract를 숨기거나 임의로 바꾸는 수단이 아니다. 실제 통합 전 `Mockable`로만 표시하며, Parent 완료 전 `Integrated` 검증을 수행한다.

### ADR 기준

다음은 `docs/decisions/` ADR로 기록한다.

- Architecture, 책임 경계, API/Data/Domain Contract의 장기 호환성 결정
- IAM, 인증/인가, Secret, Trust Boundary, 배포 모델, CI/CD, Runtime, Region 관련 결정
- 여러 Owner에게 장기 영향을 주거나 되돌리기 어려운 운영 결정

국소 구현·일시적 테스트 대역·간단히 되돌릴 수 있는 변경은 Issue/PR에 기록한다.

## 5. CI / 품질 / 보안

### 검사 기준

| 변경 영역 | PR 전 검증 | 현재 CI | Required Check 원칙 |
| --- | --- | --- | --- |
| 공통 | 변경 범위에 맞는 로컬 검증과 문서 확인 | `validate-pr-source`, Secret Scan | 현재 등록된 Required Check를 유지하고 적용 CI를 사람이 확인한다. 공통 PR Gate 검증 후 안정적인 Required Check로 전환한다. |
| Python / Contract / Fixture | Ruff lint/format, unit·contract·integration·security test | `Python Checks` | path-filter job 자체를 직접 새 Required Check로 등록하지 않는다. |
| Frontend | 관련 Node model test, 필요한 build 확인 | `Frontend Checks` | path-filter job 자체를 직접 새 Required Check로 등록하지 않는다. |
| Terraform / IaC | `terraform fmt -check`, `terraform validate`, TFLint, Checkov | 미구현 | 전용 workflow와 공통 PR Gate 연동이 필요하다. |

- **공통 PR Gate**는 모든 PR에서 완료되는 단일 안정적 check를 목표로 한다. Path Filter 때문에 건너뛰는 Python/Frontend/Terraform workflow와 분리하고, 필요한 세부 검사 결과를 종합해야 한다.
- 공통 PR Gate가 실제 PR에서 안정적으로 완료되고 Ruleset에 등록되기 전에는 기존 Required Check를 제거하지 않는다. 이 전환 기간에는 적용되는 Python/Frontend CI의 성공을 사람이 Merge 조건으로 확인한다.
- Path-filter workflow를 직접 새 Required Check로 지정하면 해당 경로를 바꾸지 않은 PR에서 check가 pending으로 남을 수 있으므로 등록하지 않는다. 공통 PR Gate가 검증·등록된 뒤에만 이를 안정적인 Required Check로 사용한다.
- Secret Scan은 모든 `dev`/`main` 대상 PR에서 실행하며, Secret·Credential·Access Key·Session Token을 코드·문서·Fixture·로그에 포함하지 않는다.
- CI 실패는 원인을 수정한 새 commit으로 재실행한다. 외부 장애·GitHub Actions 장애라면 PR에 증거를 기록하고 사람이 재실행한다. bypass는 긴급 예외 절차 외에는 사용하지 않는다.

### 현재 상태

| 항목 | 상태 | 근거 또는 후속 작업 |
| --- | --- | --- |
| PR source 경로 검사 | 구현됨 | `.github/workflows/validate-pr-source.yml`의 `validate-pr-source` |
| Secret Scan | 구현됨 | `.github/workflows/secret-scan.yml`의 Gitleaks 검사 |
| Python Checks | 구현됨 | `.github/workflows/python-checks.yml`의 Ruff와 Python test suite |
| Frontend Checks | 구현됨 | `.github/workflows/frontend-checks.yml`의 Node model test |
| 공통 PR Gate | 후속 작업 필요 | 항상 완료되는 aggregate workflow 구현 및 Ruleset 등록 필요 |
| Terraform CI | 후속 작업 필요 | fmt/validate/TFLint/Checkov workflow와 gate 연동 필요 |
| Required Check·승인·merge method 설정 | 확인 필요 | 실제 GitHub Ruleset/Branch Protection/Repository Settings는 Repository 파일에서 검증할 수 없음 |
| AWS OIDC Role·환경 보호 | 확인 필요 | AWS/GitHub Environment의 실제 trust policy·승인 규칙 확인 필요 |

## 6. AI Agent / Worktree / Handoff

### Context 탐색 순서

1. `git branch --show-current`, `git status --short`, 사용자 변경과 현재 Issue/PR 상태를 확인한다.
2. 이 문서에서 작업 생명주기·역할·의존성 규칙을 확인한다.
3. Issue의 Goal, Scope, Out of Scope, Acceptance Criteria, Contract 영향, Validation을 읽는다.
4. 작업 유형에 해당하는 첫 제품 정본과 필요한 코드·Fixture·Test만 읽는다.
5. Contract 또는 타 Owner 영향이 있을 때만 Producer/Consumer와 ADR·관련 문서를 추가로 읽는다.

Repository 전체를 기본 Context로 적재하지 않는다.

### 개인 상태와 팀 공유 상태

- GitHub Issue/Project, PR, ADR, tracked `docs/`는 팀 공유 상태다.
- `.ai/`는 개인 Agent 세션 메모와 임시 조사 기록이다. `.gitignore`로 제외하며 팀의 완료·의존성·결정 정본으로 사용하지 않는다.
- 개인 메모에서 확정된 결과는 Issue, PR, `docs/`, ADR 또는 handoff에 옮겨야 한다. `.ai/` 파일만으로 팀에 전달한 것으로 간주하지 않는다.
- Git Worktree는 병렬 Branch 작업을 격리할 때 선택적으로 사용한다. worktree 하나에는 하나의 Branch와 명확한 Issue 범위만 둔다. 다른 worktree의 변경을 임의로 수정·삭제하지 않는다.

### Handoff

세션 종료 또는 담당자 교체 전 Issue 또는 PR에 아래 항목을 한국어로 남긴다.

```markdown
- Completed:
- In Progress:
- Next:
- Blocked:
- Validation:
```

`Blocked`에는 의존 대상, Owner, 해소 조건을 함께 적고, `Validation`에는 실행 명령·CI 결과·미실행 사유를 구분한다.

- Agent는 열린 Issue와 명시된 Scope 안에서 조사·구현·검증을 수행한다. 새 작업을 임의로 시작하거나 완료를 판단해 다음 Issue로 전환하지 않는다.
- Agent의 Commit, Push, PR 생성, Issue 상태 변경, GitHub/AWS 원격 작업은 사람의 **명시적 요청**이 있을 때만 수행한다. Merge는 Agent가 수행하지 않으며, Review와 모든 보호 조건을 확인한 사람이 수행한다.
- Agent가 만든 변경도 동일한 Review, CI, Secret, Contract 검토 기준을 따른다.

## 7. Open Decision 형식

합의가 아직 필요한 운영·Contract·GitHub/AWS 설정은 Parent Issue 또는 관련 Sub-issue에 아래 형식으로 기록한다. 장기 영향을 주는 확정 결과는 ADR과 관련 문서에도 반영한다.

```markdown
- Decision:

- Owner:

- Needed by:

- Blocks:

- Options:

- Final record:
```
