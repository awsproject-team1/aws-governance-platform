# Coding Agent Map

이 Repository의 Coding Agent는 [docs/COLLABORATION.md](docs/COLLABORATION.md)를 협업 운영 정본으로, 이 문서를 Context 탐색과 Agent 실행 경계의 정본으로 사용한다. 제품 Architecture, API, Domain Contract는 해당 `docs/`와 실행 코드가 정본이다.

## 최소 Context로 시작

1. `git branch --show-current`, `git status --short`와 기존 사용자 변경을 확인한다.
2. [docs/COLLABORATION.md](docs/COLLABORATION.md)에서 Issue 생명주기, 역할, 의존성, Agent 원격 작업 제한을 확인한다.
3. 현재 GitHub Issue의 Goal, Scope, Out of Scope, Acceptance Criteria, Contract 영향, Validation을 읽는다.
4. 아래 Router에서 작업 유형의 **첫 정본 하나**와 영향을 받는 코드·Fixture·Test만 읽는다.
5. Contract 또는 다른 Owner 영향이 있을 때만 Producer/Consumer, 관련 ADR·문서를 추가로 읽는다.
6. 같은 실행에서 읽은 안정 문서는 실제 변경 또는 최신 재확인이 필요할 때만 다시 읽는다. `git status`, `git diff`, 테스트 결과는 필요할 때 재확인한다.

Repository 전체 문서나 디렉터리를 기본 Context로 적재하지 않는다.

## Source of Truth Router

| 작업 | 먼저 읽을 정본 | 관련 코드 | 부족할 때만 추가 |
| --- | --- | --- | --- |
| 협업·Issue·Branch·PR·CI·Agent 운영 | `docs/COLLABORATION.md` | `.github/`, `CONTRIBUTING.md` | 실제 강제 상태는 GitHub Ruleset/Settings |
| 제품 범위·MVP·상위 결정 | `docs/PRD.md` | 영향 영역 | `docs/DESIGN.md`, `docs/decisions/` |
| Architecture·AWS 서비스·보안 경계·책임 | `docs/DESIGN.md`의 관련 절 | `apps/`, `agent/`, `tools/`, `infrastructure/` | 장기 결정이면 `docs/decisions/` |
| HTTP API·Request·Response | `docs/API.md`의 관련 Endpoint | `apps/backend/`, `apps/frontend/src/api/` | Domain 필드가 필요할 때 `docs/CONTRACTS.md` |
| Data/Domain Contract·Schema·상태 | `packages/contracts/` 코드, 없으면 `docs/CONTRACTS.md` | Producer, Consumer, `fixtures/`, contract test | API/Architecture 영향이 있을 때만 관련 문서 |
| Rule·Policy·Profile·Scoring | `docs/CONTRACTS.md`의 관련 Domain | `packages/governance/`, policy/evidence tool | 책임 경계가 필요할 때 `docs/DESIGN.md` |
| Agent Graph·Assessment·Tool | `docs/DESIGN.md`의 관련 절 | `agent/`, `tools/` | 교환 데이터가 필요할 때 `docs/CONTRACTS.md` |
| Terraform·IAM·Deployment | `docs/DESIGN.md`의 관련 절 | `infrastructure/`, `ci/`, AWS/GitHub tool | 협업 CI는 `docs/COLLABORATION.md` |
| Naming | `docs/NAMING.md` | 영향 파일 | Contract 영향이 있을 때만 `docs/CONTRACTS.md` |

Notion은 회의 배경과 미확정 선택지의 보조 기록이며 구현 정본이 아니다. GitHub Actions/Ruleset/Branch Protection은 실제 merge·배포의 기술적 정본이다.

## Repository Map과 Owner

- A — Platform/API/Auth/Data: `apps/backend/`, Frontend `common/`, `auth/`, `api/`, `routes/`
- B — Governance/Policy/Knowledge: `packages/governance/`, Policy/Evidence Tool, Frontend `policy/`
- C — Agent Platform/Assessment: `agent/`, Frontend `assessment/`
- D — Remediation/IaC/GitHub/Deployment: GitHub/AWS Tool, `infrastructure/`, `ci/`, Frontend `remediation/`
- 공유: `packages/contracts/`, `packages/common/`, `fixtures/`, `tests/`, `docs/`

작업 시작 시 영향 경로와 Issue의 Related Domain으로 현재 Owner를 확인한다. 다른 Owner 또는 공유 Contract에 영향이 있으면 Contract Owner와 Producer/Consumer 검토를 요청하고, `Blocked`/`Mockable`/`Integrated` 상태를 Issue와 PR에 기록한다.

## Agent 실행 경계

- GitHub Issue/Project, PR, ADR, tracked `docs/`는 팀 공유 상태다. `.ai/`는 개인 Agent 세션 메모이며 Git 추적하지 않는다.
- Agent는 열린 Issue의 Scope와 Acceptance Criteria 안에서만 조사·구현·검증한다. 새 작업을 임의로 시작하거나 완료를 판단해 다음 Issue로 전환하지 않는다.
- 세션 종료 또는 담당자 전환 전 Issue 또는 PR에 `Completed`, `In Progress`, `Next`, `Blocked`, `Validation` handoff를 남긴다.
- Git Worktree는 병렬 Branch 작업을 격리할 때 선택적으로 사용한다. worktree 하나에는 하나의 Branch와 명확한 Issue 범위만 둔다.
- 사용자 명시 요청 없이 Commit, Push, PR 생성, Issue 상태 변경, 원격 GitHub/AWS 작업을 수행하지 않는다. Merge는 Agent가 수행하지 않으며, Review와 모든 보호 조건을 확인한 사람이 수행한다.
- `main`과 `dev`에서 직접 구현하거나 push하지 않는다. 일반 PR은 `dev`, 통합 PR만 `main`을 대상으로 하며 Review와 CI를 우회하지 않는다.

## 공통 원칙

- 기존 사용자 변경을 삭제·덮어쓰지 않고 관련 없는 파일을 수정하지 않는다.
- 공통 Contract는 Producer·Consumer·Fixture를 먼저 확인한다. `packages/contracts/` 변경과 `docs/CONTRACTS.md` 변경은 같은 PR에서 동기화한다.
- Architecture/API/Naming/장기 결정 영향이 있을 때만 해당 정본 또는 ADR을 갱신한다.
- LLM 출력은 Schema, 허용 ID/Enum, 권한, CI, Plan, Human Approval로 검증한다.
- Agent와 AWS Resource Tool은 Customer Workload를 변경하지 않는다. Terraform Apply는 승인 후 GitHub Actions만 수행한다.
- Secret, Credential, Access Key, Session Token을 코드·문서·Fixture·로그에 넣지 않는다.
- 문서와 handoff의 서술은 한국어로 작성한다. 식별자·파일 경로·코드 심볼·기술 용어, ADR `Status` 값, 링크·URL은 원문을 유지한다.

## Skills와 Validation

- 구현 작업: `.agents/skills/implement-task/SKILL.md`
- 변경 검토·PR 준비·검증: `.agents/skills/pr-validation/SKILL.md`

검증 명령은 root의 실제 manifest/config, `.github/workflows/`, `ci/`를 정본으로 사용한다. 아직 manifest나 workflow에 정의되지 않은 명령을 임의로 만들거나 도구를 Harness만을 위해 설치하지 않는다. 변경 영역별 검증은 `docs/COLLABORATION.md`와 `CONTRIBUTING.md`를 따른다.
