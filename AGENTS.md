# Coding Agent Map

이 Repository는 고객의 Terraform/IaC와 조직 정책을 기준으로 AWS Governance/Compliance를 평가하고, 사람 승인 뒤 개선·배포·재검증을 연결하는 플랫폼이다.

## 최소 Context로 시작

1. 작업 전에 `git branch --show-current`, `git status --short`와 기존 변경을 확인한다.
2. 사용자 요청을 분류하고 아래 표에서 **첫 정본 하나**를 선택한다.
3. `rg`와 `rg --files`로 영향받는 코드·Fixture·Test를 좁혀 읽는다.
4. 첫 정본과 관련 코드만으로 판단할 수 없을 때만 두 번째 문서를 읽는다.
5. 같은 Codex 실행에서 이미 읽은 안정적인 문서는 실제로 변경됐거나 최신 재확인이 필요하지 않으면 다시 읽지 않는다. `git status`, `git diff`, 테스트 결과처럼 변하는 정보는 필요할 때 재확인한다.

Repository 전체 문서나 디렉터리를 기본 Context로 적재하지 않는다.

## Source of Truth Router

| 작업 | 먼저 읽을 정본 | 관련 코드 | 부족할 때만 추가 |
| --- | --- | --- | --- |
| 제품 범위·MVP·상위 결정 | `docs/PRD.md` | 영향 영역 | Notion `최종 계획서`와 하위 문서 |
| Architecture·AWS 서비스·보안 경계·책임 | `docs/DESIGN.md`의 관련 절 | `apps/`, `agent/`, `tools/`, `infrastructure/` | 장기 결정이면 `docs/decisions/` |
| HTTP API·Request·Response | `docs/API.md`의 관련 Endpoint | `apps/backend/`, `apps/frontend/src/api/` | Domain 필드가 필요할 때 `docs/CONTRACTS.md` |
| Data/Domain Contract·Schema·상태 | `packages/contracts/`에 실행 가능한 Schema 코드가 있으면 코드, 없으면 `docs/CONTRACTS.md` | Producer, Consumer, `fixtures/`, contract test | API/Architecture 영향이 있을 때만 `docs/API.md` 또는 `docs/DESIGN.md` |
| Rule·Policy·Profile·Scoring | `docs/CONTRACTS.md`의 관련 Domain | `packages/governance/`, `tools/policy-knowledge/`, `tools/external-evidence/` | 책임 경계가 필요할 때 `docs/DESIGN.md` |
| Agent Graph·Assessment·Tool | `docs/DESIGN.md`의 관련 절 | `agent/`, `tools/` | 교환 데이터가 필요할 때 `docs/CONTRACTS.md` |
| Terraform·IAM·Deployment | `docs/DESIGN.md`의 Remediation/IAM/Deployment 절 | `infrastructure/`, `ci/`, `tools/aws-resource/`, `tools/github/` | 명명은 `docs/NAMING.md`, 협업 CI는 `CONTRIBUTING.md` |
| Git·Issue·Branch·PR·GitHub Actions | `CONTRIBUTING.md`의 관련 절 | `.github/`, `ci/` | 이름을 바꿀 때만 `docs/NAMING.md` |
| Naming | `docs/NAMING.md` | 영향 파일 | Contract 영향이 있을 때만 `docs/CONTRACTS.md` |

상위 제품 방향은 Notion, 구현 세부사항은 Repository 문서, 실행 가능한 Contract는 `packages/contracts/`가 정본이다. 실제 작업 상태는 GitHub Issue/Projects, 고객 Workload Terraform은 고객 Repository가 정본이다. 확정되지 않은 내용은 추측하지 않고 `TODO` 또는 `Open Decision`으로 남긴다. deprecated 문서가 생기면 정본으로 사용하지 않는다.

## Repository Map

- A — Platform/API/Auth/Data: `apps/backend/`, Frontend `common/`, `auth/`, `api/`, `routes/`
- B — Governance/Policy/Knowledge: `packages/governance/`, Policy/Evidence Tool, Frontend `policy/`
- C — Agent Platform/Assessment: `agent/`, Frontend `assessment/`
- D — Remediation/IaC/GitHub/Deployment: GitHub/AWS Tool, `infrastructure/`, `ci/`, Frontend `remediation/`
- 공유: `packages/contracts/`, `packages/common/`, `fixtures/`, `tests/`, `docs/`
- `fixtures/`, `tests/`: 고정 입력과 Unit/Contract/Integration/E2E/Security 검증
- `docs/`: 제품·설계·Interface·Naming 정본과 ADR
- `.github/`: Issue/PR template과 GitHub Actions

세부 책임과 금지 경계는 `docs/DESIGN.md`를 따른다. 고객 Workload Terraform을 `infrastructure/`에 넣지 않는다.

## 역할별 GitHub 작업 범위

- GitHub 작업을 시작할 때 요청된 Parent Issue, Issue Assignee, Related Domain과 영향받는 경로를 기준으로 A/B/C/D 중 현재 역할을 먼저 확인한다.
- Issue 계획을 명시적으로 요청받은 경우 해당 역할의 Parent Issue와 직접 연결된 의존 관계만 확인하고, 그 Parent 아래의 Sub-issue만 생성·관리한다. 다른 역할의 Parent와 전체 Milestone 항목을 기본 Context로 읽지 않는다.
- 이미 생성된 Sub-issue를 구현할 때는 Issue Template을 다시 읽지 않고, 선택한 Sub-issue의 Scope, Acceptance Criteria, Test / Validation과 직접 연결된 의존 Issue만 확인한다.
- Sub-issue가 자체 완결적이면 구현 중 Parent를 다시 읽지 않는다. Sub-issue만으로 범위를 판단할 수 없거나 Parent Scope·의존 관계가 변경됐을 때, 또는 모든 Sub-issue 완료 후 Parent를 종료할 때만 다시 확인한다.
- A/B/C/D는 같은 공유 Milestone과 Project 안에서 각자 담당 Sub-issue의 Assignee와 상태를 갱신한다. Milestone 기간·전체 범위·Owner 간 우선순위는 임의로 변경하지 않고 사람이 종합 판단한다.
- 공통 Contract 또는 다른 Owner 영역에 영향이 있을 때만 관련 Parent·Issue와 정본을 추가로 확인하고 해당 Owner와 합의한다.
- 이 절은 Context와 책임 범위를 제한하는 규칙이다. Issue 생성·수정 등 GitHub 원격 변경은 사용자의 명시적 요청이 있을 때만 수행한다.

## Skills

- 구현 작업: `.agents/skills/implement-task/SKILL.md`
- 변경 검토·PR 준비·검증: `.agents/skills/pr-validation/SKILL.md`

Project Context 전용 Skill은 두지 않는다. 이 파일의 Router를 사용하고 선택한 Skill은 필요한 정본만 추가로 읽는다.

## 공통 원칙

- 기존 사용자 변경을 삭제하거나 덮어쓰지 않고 관련 없는 파일을 수정하지 않는다.
- 공통 Contract는 Producer·Consumer·Fixture를 먼저 확인한다. `packages/contracts/` 변경과 `docs/CONTRACTS.md` 변경은 같은 PR에서 동기화한다.
- Architecture/API/Naming/장기 결정 영향이 있을 때만 해당 정본 또는 ADR을 갱신한다.
- LLM 출력은 Schema, 허용 ID/Enum, 권한, CI, Plan, Human Approval로 검증한다.
- Agent와 AWS Resource Tool은 Customer Workload를 변경하지 않는다. Terraform Apply는 승인 후 GitHub Actions만 수행한다.
- Secret, Credential, Access Key, Session Token을 코드·문서·Fixture·로그에 넣지 않는다.
- `main`과 `dev`에서 직접 구현하거나 Push하지 않는다. 허용 PR 경로와 Review 조건은 `CONTRIBUTING.md`를 따른다.
- 사용자 명시 요청 없이 commit, push, PR 생성, merge, remote 변경을 수행하지 않는다.

## Validation 위치

검증 명령은 root의 실제 manifest/config, `.github/workflows/`, `ci/`를 정본으로 사용한다. 현재는 Repository Skeleton 단계라 실행 가능한 manifest와 Workflow가 없으므로 명령을 임의로 만들거나 도구를 Harness만을 위해 설치하지 않는다. 변경 영역별 기대 검증과 아직 미구현된 CI 기준은 `CONTRIBUTING.md`의 `Test와 CI`를 따른다.
