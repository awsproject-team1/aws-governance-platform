# Contributing

이 문서는 사람 개발자를 위한 실행 규칙이다. 협업 운영의 정본은 [docs/COLLABORATION.md](docs/COLLABORATION.md)이며, 제품·설계·Contract 내용은 관련 `docs/`와 실행 가능한 Contract를 따른다.

## 개발 흐름

```text
Parent Issue
  → Native Sub-issue 또는 Bug Issue
  → 최신 dev에서 short-lived branch 생성
  → 구현 및 관련 로컬 검증
  → Pull Request → dev
  → CI / Owner Review / Squash Merge
  → Sub-issue Done
  → Parent 통합 검증
  → dev → main 통합 PR / Release 또는 Demo 검증
```

- `main`과 `dev`에 직접 push하거나 직접 작업하지 않는다. 모든 일반 작업은 short-lived branch에서 시작한다.
- 일반 작업 PR의 base는 `dev`이며, `main` PR은 같은 Repository의 `dev → main` 통합 PR만 허용한다.
- Parent Issue는 목표·통합 기준을 관리한다. 실제 구현은 Native Sub-issue 또는 Bug Issue로 분리한다.
- Issue 유형, 완료 조건, 의존성 상태, Contract 검토 기준은 `docs/COLLABORATION.md`를 따른다.

## Branch Naming

기본 형식은 `type/<issue-number>-kebab-case`다.

```text
feature/123-assessment-api
fix/456-policy-profile-validation
docs/789-collaboration-guide
```

허용되는 Platform Repository PR 경로는 아래 두 가지뿐이다.

| Head | Base | 허용 목적 |
| --- | --- | --- |
| `feature/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, `chore/*` | `dev` | 일반 작업 |
| `dev` | `main` | 안정화 통합 / Release |

다른 기능 branch를 기반으로 작업하거나 다른 기능 branch를 base로 하는 PR을 만들지 않는다. 선행 산출물이 필요하면 `dev` merge를 기다리거나 합의한 Fixture/Fake/Mock으로 병렬화한다.

## Commit과 Pull Request

Conventional Commits를 사용한다. `feat`, `fix`, `docs`, `refactor`, `test`, `chore` 중 하나를 사용하고 하나의 commit에는 이해 가능한 변경 단위를 담는다.

PR에는 다음을 포함한다.

- What / Why와 포함·제외 Scope
- Parent와 관련 Sub-issue 또는 Bug Issue
- 적용한 `Refs #<issue>` 또는 `Closes #<issue>`
- Validation과 CI 결과
- Contract 영향, Producer/Consumer와 필요한 Owner Review
- Security·Secret 확인 및 갱신 문서

`Closes #<issue>`는 merge로 Sub-issue 또는 Bug Issue의 Acceptance Criteria를 모두 충족할 때만 사용한다. 일부 구현·기반 작업·조사처럼 Issue를 유지해야 하면 `Refs #<issue>`를 사용한다. Parent Issue에는 closing keyword를 사용하지 않는다.

## Review와 Merge

- 모든 PR은 적용되는 CI 성공과 다른 팀원 최소 한 명의 Review가 필요하다.
- Contract 또는 다른 Owner 영역에 영향이 있으면 영향받는 named Consumer/Owner가 해당 PR revision을 명시적으로 승인해야 한다. Review 요청만으로는 merge할 수 없다.
- 일반 Sub-issue/Bug PR은 Squash Merge로 `dev`에 병합한다. `dev → main` 통합 PR은 Merge Commit을 기본으로 한다.
- CI 실패는 수정 후 새 commit으로 재실행한다. 외부 장애는 증거와 함께 PR에 기록하고 사람이 재실행한다.
- `main` hotfix, bypass 등 긴급 예외는 `docs/COLLABORATION.md`의 긴급 수정 절차를 따른다. 관리자 권한으로 Required Check·Review·Ruleset을 우회하지 않는다.
- merge 뒤 불필요한 branch를 삭제하고 Issue/Project 상태와 handoff를 사람이 확인한다.

## CI와 품질

- 모든 PR: `validate-pr-source`, Secret Scan
- Python/Contract/Fixture 변경: Ruff lint/format, unit·contract·integration·security test
- Frontend 변경: Frontend model test
- Terraform 변경: `terraform fmt -check`, `terraform validate`, TFLint, Checkov를 목표로 하며 현재 workflow는 후속 작업이다.

Python과 Frontend workflow는 Path Filter를 사용하므로 해당 job을 직접 Required Check로 등록하지 않는다. 공통 PR Gate를 구현·실제 PR에서 검증한 뒤 Ruleset의 안정적인 Required Check로 등록한다. 전환이 완료되기 전에는 기존 Required Check를 제거하지 않으며, 적용되는 Python/Frontend CI 성공을 사람이 Merge 조건으로 확인한다. 현재 구현·확인 필요·후속 작업 상태는 `docs/COLLABORATION.md`를 따른다.

### 로컬 Python 검증

```powershell
python -m pip install --requirement requirements-dev.txt --requirement apps/backend/requirements.txt --requirement packages/governance/requirements.txt
python -m ruff check .
python -m ruff format --check .
python -m unittest discover --start-directory tests/unit --pattern "test_*.py" --verbose
python -m unittest discover --start-directory tests/contract --pattern "test_*.py" --verbose
python -m unittest discover --start-directory tests/integration --pattern "test_*.py" --verbose
python -m unittest discover --start-directory tests/security --pattern "test_*.py" --verbose
node --test tests/unit/test_policy_frontend.mjs
```

## 문서·Contract·보안

- 제품·설계·API·Naming·Contract 변경은 해당 `docs/`와 실행 코드·test를 같은 PR에서 갱신한다.
- 장기 Architecture, Security, Contract, CI/CD 결정은 `docs/decisions/` ADR로 기록한다.
- `.env`와 실제 Credential은 commit하지 않는다. `.env.example`에는 비밀이 아닌 예시만 둔다.
- 개인 Access Key를 공유하지 않고, GitHub Actions와 Runtime은 AWS OIDC 기반 역할을 사용한다. 실제 AWS/GitHub 설정은 Repository 밖의 관리자 후속 작업이다.

## AI Agent와 Worktree

AI Agent에도 동일한 Branch, CI, Review, Secret, Contract 규칙이 적용된다. `.ai/`는 개인 Agent 상태로 Git 추적하지 않으며, 팀 공유 상태는 GitHub Issue/Project, PR, ADR, tracked `docs/`에 기록한다. Agent의 Commit, Push, PR 생성, Issue 상태 변경, 원격 GitHub/AWS 작업은 사람의 명시적 요청이 있을 때만 수행한다. Merge는 Agent가 수행하지 않고 사람이 Review와 보호 조건을 확인한 뒤 수행한다.

Git Worktree는 병렬 작업에 선택적으로 사용한다. worktree 하나에는 하나의 Branch와 Issue 범위를 두고, 세션 종료 전 `Completed`, `In Progress`, `Next`, `Blocked`, `Validation` handoff를 Issue 또는 PR에 남긴다.
