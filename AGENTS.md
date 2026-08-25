# Coding Agent Guide

이 문서는 Codex를 포함한 Coding Agent가 이 Repository에서 행동할 때 지켜야 할 실행 규칙이다. 제품 요구사항이나 설계 상세를 여기에서 재정의하지 않는다.

## 작업 전 필수 확인

1. `git branch --show-current`, `git status`, 기존 파일과 변경사항을 확인한다.
2. 작업 범위에 따라 `README.md`, `docs/PRD.md`, `docs/DESIGN.md`, `docs/API.md`, `docs/CONTRACTS.md`, `docs/NAMING.md`, `CONTRIBUTING.md`를 읽는다.
3. 상위 제품 방향이 필요하면 Notion의 최신 `최종 계획서`와 하위 문서를 확인한다.
4. 기존 사용자 변경을 삭제하거나 덮어쓰지 않는다. 충돌 가능성이 있으면 차이를 먼저 설명한다.

## Source of Truth

- 제품 방향, MVP 범위, 상위 Architecture, 주요 기술 결정: Notion `최종 계획서`
- 구현 시점 API/Schema/Contract와 코드 직접 연결 설계: Repository의 `docs/`와 `packages/contracts/`
- 구현 시점 Contract 코드: `packages/contracts/`
- 고객 IaC: 고객 소유 GitHub Repository
- 실제 개발 작업: GitHub Issue/Projects
- 구현에 지속적인 영향을 주는 확정 기술 결정: `docs/decisions/` ADR

충돌 시 상위 제품 결정은 Notion, 구현 세부사항은 Repository 문서를 따른다. 상위 변경이 구현에 영향을 주면 양쪽을 함께 갱신한다. 미결정사항은 추측하지 말고 `TODO` 또는 `Open Decision`으로 남긴다.

## 책임 경계

- A — Platform / API / Auth / Data: `apps/backend/`, Frontend의 `common/`, `auth/`, `api/`, `routes/`
- B — Governance / Policy / Knowledge: `packages/governance/`, Policy/Evidence Tool, Policy Agent/Prompt, Frontend `policy/`
- C — Agent Platform / Assessment: Graph, Assessment Agent, Node, Context, Runtime, Validator, Frontend `assessment/`
- D — Remediation / IaC / GitHub / Deployment: GitHub/AWS Tool, Remediation Agent/Prompt, `infrastructure/`, `ci/`, Frontend `remediation/`
- 공동: `packages/contracts/`, `packages/common/`, `fixtures/`, Contract/Integration/E2E Test, `docs/`

자세한 디렉터리 책임은 `docs/DESIGN.md`를 따른다. 다른 Domain의 판정이나 외부 시스템 책임을 자기 영역으로 옮기지 않는다. 다른 Owner 영역에 영향을 주면 해당 Contract를 먼저 합의한다.

특히 다음 경계를 지킨다.

- Backend는 Domain 기능을 연결하되 Rule 판정, Assessment 의미 판정, Terraform 수정·배포 로직을 소유하지 않는다.
- Governance는 무엇을 검사할지 결정하되 실제 Resource × Rule PASS/FAIL을 판정하지 않는다.
- Agent Platform은 Tool을 조정하되 각 Domain Tool의 구현 책임을 흡수하지 않는다.
- AWS Resource Tool은 Read-Only 사실만 반환하며 Compliance를 판정하지 않는다.
- Terraform Apply는 Agent Tool이 아니라 승인 후 GitHub Actions의 책임이다.
- 고객 Workload Terraform을 `infrastructure/`에 넣지 않는다.

## Contract 우선 개발

병렬 개발은 Contract와 Fixture를 먼저 합의한 뒤 진행한다.

- `packages/contracts/`에는 데이터 형식과 검증 계약만 두고 비즈니스 로직을 넣지 않는다.
- `packages/contracts/` 변경과 `docs/CONTRACTS.md` 변경은 같은 Pull Request에서 동기화한다.
- Contract 변경은 Producer와 Consumer 및 영향받는 Owner가 함께 검토한다.
- Architecture 변경 시 `docs/DESIGN.md`, API 변경 시 `docs/API.md`, Naming 변경 시 `docs/NAMING.md`를 갱신한다.
- 장기적인 Architecture/Security/Contract/Deployment 결정은 ADR도 작성한다.
- 확정되지 않은 필드, Enum, Endpoint, AWS Service, Naming은 임의로 만들지 않는다.

## Git 작업 규칙

- `main`과 `dev`에서 직접 구현하거나 직접 Push하지 않는다.
- 실제 작업은 Issue에 연결된 short-lived `type/kebab-case` branch에서 수행한다.
- 일반 PR은 `dev`, 안정화 통합 PR만 `main`을 대상으로 한다.
- Commit은 Conventional Commits의 `feat`, `fix`, `docs`, `refactor`, `test`, `chore`를 사용한다. Scope는 선택사항이다.
- PR에는 Related Issue, What/Why, Validation, Architecture/Contract/Security 영향을 기록한다.
- 해당 Required CI 통과와 다른 팀원 최소 1명 승인이 있어야 Merge한다.
- Squash Merge를 기본으로 한다.
- 사용자의 명시적 요청 없이 commit, push, PR 생성, merge, remote 변경을 수행하지 않는다.

## 검증 기준

변경 범위에 필요한 검사만 실행하되 결과를 누락하지 않는다.

- 모든 PR: Secret Scan
- Python: Unit Test, Contract Test, Ruff Lint/Format
- Terraform: `terraform fmt -check`, `terraform validate`, TFLint, Checkov
- Frontend: Frontend Test, Build
- Domain 연결, 주요 Merge, Demo/Release: 필요한 Integration/E2E Test
- 보안 경계 변경: 관련 Security Test

GitHub Actions는 Path Filter로 변경 영역에 맞는 Workflow를 선택한다. 실제 명령이 아직 Repository에 정의되지 않았다면 임의의 도구 구성을 확정하지 말고 문서의 TODO를 유지한다.

## 보안

- Secret, Access Key, Session Token, 실제 Credential을 코드·문서·Fixture·로그에 저장하지 않는다.
- 공동 AWS Access Key를 사용하지 않는다. 로컬 개발자는 각자 IAM User를 사용한다.
- GitHub Actions의 AWS 인증은 장기 Key가 아닌 OIDC를 사용한다.
- Agent Runtime에는 Customer Workload Write 권한을 부여하지 않는다.
- LLM 출력은 신뢰하지 않고 Schema, 허용 ID/Enum, 권한, CI, Plan, Human Approval로 검증한다.
- AI 생성 코드도 사람의 코드와 동일하게 Review와 CI를 거친다.

## 작업 방식

복잡한 작업은 `Research → Plan → Implement → Test → Review` 순서로 수행한다. 간단한 문서 수정이나 국소 변경에는 불필요한 형식 절차를 강제하지 않는다. Git Worktree는 병렬 branch/agent 작업이 유용할 때 선택적으로 사용한다.

## Definition of Done

- Acceptance Criteria를 충족했다.
- 요청 범위의 구현과 필요한 Fixture가 완료됐다.
- 필요한 Unit/Contract Test 및 변경 영역의 Lint/Build/Validation이 통과했다.
- 적용되는 Required CI가 통과했다.
- Secret과 민감정보가 포함되지 않았다.
- Architecture/Workflow/Contract/API/Naming 영향이 있으면 관련 문서와 ADR을 갱신했다.
- 다른 팀원 최소 1명이 승인했다.
- 일반 작업은 `dev`에 Merge됐다.

문서 전용 또는 E2E/배포 작업의 추가 DoD는 Issue Acceptance Criteria에 명시한다.
