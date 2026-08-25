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
  → Squash Merge to dev
```

안정화 시에는 다음 흐름을 사용한다.

```text
dev → Pull Request → Required CI / Review → Squash Merge → main
```

`main`에 직접 Push하지 않습니다. `dev`에서도 직접 작업하지 않고 Issue에 연결된 short-lived branch를 사용합니다.

## Issue와 작업 단위

- 개발 시작 시 A/B/C/D Parent Issue를 만들고 Owner와 Scope를 고정합니다.
- 실제 구현은 Parent 아래 Sub-issue 또는 Bug 단위로 진행합니다.
- Parent 전용 branch는 만들지 않습니다.
- Sub-issue는 Review와 Merge가 가능한 크기로 유지하되 억지로 지나치게 작게 나누지 않습니다.
- 다른 Owner 영역이나 공통 Contract에 영향을 주면 구현 전에 관련 Owner와 합의합니다.

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

Merge 조건은 해당 PR의 Required CI 통과와 다른 팀원 최소 1명 승인입니다. CI 실패 상태에서는 Merge하지 않습니다. Squash Merge를 기본으로 하며 Merge 후 더 이상 필요 없는 feature branch는 삭제할 수 있습니다.

## Test와 CI

GitHub Actions는 Path Filter로 변경 영역에 필요한 검사를 자동 선택하는 것을 원칙으로 합니다.

- 모든 PR: Secret Scan
- Python 변경: Unit Test, Contract Test, Ruff Lint/Format
- Terraform 변경: `terraform fmt -check`, `terraform validate`, TFLint, Checkov
- Frontend 변경: Frontend Test, Build
- Integration/E2E: 모든 PR에 강제하지 않고 주요 Domain 연결, 주요 Merge, Demo/Release 전에 수행

테스트 커버리지 수치는 MVP의 일률적 Gate로 두지 않으며 핵심 기능과 Contract Test의 존재를 우선합니다. 구체 명령은 기술 Bootstrap과 CI 구현 시 확정합니다.

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
