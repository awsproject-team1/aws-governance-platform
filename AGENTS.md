# Coding Agent Map

이 Repository는 고객의 Terraform/IaC와 조직 정책을 기준으로 AWS Governance/Compliance를 평가하고, 사람 승인 뒤 개선·배포·재검증을 연결하는 플랫폼이다.

## 최소 Context로 시작

1. 작업 전에 `git branch --show-current`, `git status --short`와 기존 변경을 확인한다.
2. 사용자 요청을 분류하고 아래 표에서 **첫 정본 하나**를 선택한다.
3. `rg`와 `rg --files`로 영향받는 코드·Fixture·Test를 좁혀 읽는다.
4. 첫 정본과 관련 코드만으로 판단할 수 없을 때만 두 번째 문서를 읽는다.
5. 같은 실행(Session)에서 **한번 읽은 안정적인 문서는 다시 읽지 않는다.** 실제로 변경됐거나 최신 재확인이 필요할 때만 다시 읽는다. `git status`, `git diff`, 테스트 결과처럼 변하는 정보는 필요할 때 재확인한다.
6. 하위 작업(기능)은 각각 새 Session에서 진행해 Context 오염을 막는다. 현재 작업의 Goal, Scope(제외 범위 포함), Acceptance Criteria는 `.ai/task/taskN.md`에서 확인하고, 팀 공용 진행·의존 관계는 `PROGRESS.md`에서 확인한다.

Repository 전체 문서나 디렉터리를 기본 Context로 적재하지 않는다.

## Source of Truth Router

| 작업 | 먼저 읽을 정본 | 관련 코드 | 부족할 때만 추가 |
| --- | --- | --- | --- |
| 제품 범위·MVP·상위 결정 | `docs/PRD.md` | 영향 영역 | `docs/DESIGN.md`, `docs/decisions/` |
| Architecture·AWS 서비스·보안 경계·책임 | `docs/DESIGN.md`의 관련 절 | `apps/`, `agent/`, `tools/`, `infrastructure/` | 장기 결정이면 `docs/decisions/` |
| HTTP API·Request·Response | `docs/API.md`의 관련 Endpoint | `apps/backend/`, `apps/frontend/src/api/` | Domain 필드가 필요할 때 `docs/CONTRACTS.md` |
| Data/Domain Contract·Schema·상태 | `packages/contracts/`에 실행 가능한 Schema 코드가 있으면 코드, 없으면 `docs/CONTRACTS.md` | Producer, Consumer, `fixtures/`, contract test | API/Architecture 영향이 있을 때만 `docs/API.md` 또는 `docs/DESIGN.md` |
| Rule·Policy·Profile·Scoring | `docs/CONTRACTS.md`의 관련 Domain | `packages/governance/`, `tools/policy-knowledge/`, `tools/external-evidence/` | 책임 경계가 필요할 때 `docs/DESIGN.md` |
| Agent Graph·Assessment·Tool | `docs/DESIGN.md`의 관련 절 | `agent/`, `tools/` | 교환 데이터가 필요할 때 `docs/CONTRACTS.md` |
| Terraform·IAM·Deployment | `docs/DESIGN.md`의 Remediation/IAM/Deployment 절 | `infrastructure/`, `ci/`, `tools/aws-resource/`, `tools/github/` | 명명은 `docs/NAMING.md`, 협업 CI는 `CONTRIBUTING.md` |
| Git·Branch·PR·GitHub Actions | `CONTRIBUTING.md`의 관련 절 | `.github/`, `ci/` | 이름을 바꿀 때만 `docs/NAMING.md` |
| 팀 진행·작업 상태 | `PROGRESS.md`(팀 공용), `.ai/task/taskN.md`(개인) | 영향 영역 | 규칙은 `CONTRIBUTING.md` |
| Naming | `docs/NAMING.md` | 영향 파일 | Contract 영향이 있을 때만 `docs/CONTRACTS.md` |

제품 방향·구현 세부사항 모두 Repository 문서(`docs/`)가 정본이고, 실행 가능한 Contract는 `packages/contracts/`가 정본이다. **상위 제품 방향을 위해 Notion 문서를 정본으로 참조하지 않는다.** 팀 공용 작업 상태는 `PROGRESS.md`, 개인/Agent 작업 상태는 `.ai/task/taskN.md`, 고객 Workload Terraform은 고객 Repository가 정본이다. 확정되지 않은 내용은 추측하지 않고 `TODO` 또는 `Open Decision`으로 남긴다. deprecated 문서가 생기면 정본으로 사용하지 않는다.

## Repository Map

- A — Platform/API/Auth/Data: `apps/backend/`, Frontend `common/`, `auth/`, `api/`, `routes/`
- B — Governance/Policy/Knowledge: `packages/governance/`, Policy/Evidence Tool, Frontend `policy/`
- C — Agent Platform/Assessment: `agent/`, Frontend `assessment/`
- D — Remediation/IaC/GitHub/Deployment: GitHub/AWS Tool, `infrastructure/`, `ci/`, Frontend `remediation/`
- 공유: `packages/contracts/`, `packages/common/`, `fixtures/`, `tests/`, `docs/`
- `fixtures/`, `tests/`: 고정 입력과 Unit/Contract/Integration/E2E/Security 검증
- `docs/`: 제품·설계·Interface·Naming 정본과 ADR
- `.github/`: PR template과 GitHub Actions (CI/PR Gate). GitHub Issue는 사용하지 않는다.

세부 책임과 금지 경계는 `docs/DESIGN.md`를 따른다. 고객 Workload Terraform을 `infrastructure/`에 넣지 않는다.

## 역할별 작업 범위

- **GitHub Issue / Project는 사용하지 않는다.** 팀 공용 진행·마일스톤·의존성은 `PROGRESS.md`, 개인/Agent 세부 작업은 `.ai/task/taskN.md`로 관리한다.
- 작업을 시작할 때 영향받는 경로와 Related Domain을 기준으로 A/B/C/D 중 현재 역할을 먼저 확인한다.
- 현재 기능은 `.ai/task/taskN.md`의 Goal, Scope(제외 범위 포함), Acceptance Criteria, Test / Validation을 완료 기준으로 사용한다. 하위 작업(기능)마다 새 Session에서 진행하고, 각 기능은 `taskN.md`를 새로 만들어 누적한다(이전 파일을 덮어쓰지 않는다).
- 과거 task를 다시 볼 때는 전체를 로드하지 않고 필요한 `taskN.md` 하나만 골라 읽는다(재독 금지 원칙과 동일).
- 기능 완료 시 핵심 결정·결과 한 줄을 `PROGRESS.md`의 Completed에 올린다. 아키텍처·계약에 지속 영향을 주는 결정은 `taskN.md`에만 두지 않고 `docs/decisions/` ADR로 옮긴다(`.ai/`는 Git 제외라 task에만 두면 유실될 수 있다).
- 팀 공유가 필요한 진행·의존 관계·Blocked만 `PROGRESS.md`에 갱신한다. 다른 역할 전체 작업을 기본 Context로 읽지 않는다.
- 공통 Contract 또는 다른 Owner 영역에 영향이 있을 때만 관련 정본을 추가로 확인하고 해당 Owner와 합의하며 `PROGRESS.md`에 의존성을 명시한다.
- `dev` 대상 PR에는 Issue 연결 키워드(`Closes`/`Refs`)를 사용하지 않는다. Review와 Merge는 사람이 수행한다.
- 이 절은 Context와 책임 범위를 제한하는 규칙이다. commit, push, PR 생성 등 GitHub 원격 변경은 사용자의 명시적 요청이 있을 때만 수행한다.

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
- 문서와 task(`docs/`, ADR, `.ai/task/`, PROGRESS 등)의 **서술은 한국어로 작성한다.** 단 식별자·파일 경로·코드 심볼·기술 용어(예: `apps.backend`, `job_id`, API Gateway, Lambda)와 ADR `Status` 값(`Accepted`/`Proposed`/`Superseded`), 링크·URL은 원문을 유지한다.
- `main`과 `dev`에서 직접 구현하거나 Push하지 않는다. 허용 PR 경로와 Review 조건은 `CONTRIBUTING.md`를 따른다.
- GitHub의 admin/bypass 권한으로 Branch/Ruleset/Required Check/Review 조건을 우회하지 않는다. 보호 설정을 약화·삭제하거나 Required Check 이름을 바꾸지 않는다. PR의 head/base 조합을 검사하는 Required Check 이름은 `validate-pr-source`다.
- 사용자 명시 요청 없이 commit, push, PR 생성, merge, remote 변경을 수행하지 않는다.

## Validation 위치

검증 명령은 root의 실제 manifest/config, `.github/workflows/`, `ci/`를 정본으로 사용한다. 현재 Python 검증은 `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/python-checks.yml`에 Ruff Lint/Format, Unit Test, Contract Test로 정의되어 있으므로 변경 경로에 해당하면 실행한다. 실제 manifest나 Workflow에 아직 정의되지 않은 영역의 명령을 임의로 만들거나 도구를 Harness만을 위해 설치하지 않는다. 변경 영역별 검증은 `CONTRIBUTING.md`의 `Test와 CI`를 따른다.
