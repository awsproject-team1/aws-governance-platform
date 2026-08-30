# Naming Convention

이 문서는 Repository의 Naming 정본이다. 확정되지 않은 규칙은 강제하지 않으며 Open Decision으로 표시한다.

## Repository

Notion Collaboration에 확정된 Governance Platform Repository 이름은 다음과 같다.

```text
cloud-governance-agent
```

고객 Demo IaC는 별도 Repository로 관리한다.

```text
customer-demo-iac
```

현재 실제 Remote는 `awsproject-team1/aws-governance-platform`이고 Bootstrap 요청의 구조명은 `cloud-governance-platform`이다. 이 작업에서는 Remote나 로컬 root를 변경하지 않는다. 확정 Naming과 실제 Repository 이름을 언제·어떻게 맞출지는 Open Decision이다.

## Directory와 File

최상위 Directory Skeleton과 책임은 [DESIGN.md](DESIGN.md)에 확정되어 있다. 일반적인 Directory/File case 규칙은 Collaboration에서 아직 확정되지 않았으므로 임의의 전역 규칙을 추가하지 않는다. 새 이름은 기존 확정 Skeleton과 사용하는 언어의 아래 규칙을 따른다.

## Branch

형식:

```text
type/<issue-number>-kebab-case
```

예:

```text
feature/11-assessment-api
fix/42-policy-profile-validation
docs/53-update-contracts
chore/54-bootstrap-repository
```

Platform Repository의 branch와 PR 경로는 다음과 같이 고정한다.

- short-lived 작업 branch: `feature/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, `chore/*`
- 일반 PR: short-lived 작업 branch → `dev`
- 안정화 통합 PR: 같은 Repository의 `dev` → `main`
- 금지: short-lived 작업 branch → `main`, `main`/`dev` direct push, force push, 보호 규칙 bypass

PR의 head/base 조합을 확인하는 Required Check 이름은 `validate-pr-source`를 사용한다. GitHub Workflow/Job 전체 Naming은 별도 Open Decision이지만, Ruleset에 연결되는 이 check 이름은 보호 설정과 문서에서 동일하게 유지한다.

Remediation이 고객 IaC Repository에 만드는 Branch의 현재 설계 예시는 다음과 같다.

```text
feature/governance-remediation-<id>
```

Customer Repository의 기준 branch가 항상 `main`인지 여부는 연결된 Repository 설정을 따른다.

## Commit

Conventional Commits 형식을 사용한다.

```text
type(optional-scope): description
```

허용 type:

- `feat`
- `fix`
- `docs`
- `refactor`
- `test`
- `chore`

Scope는 선택사항이다.

## Python

- Module: `snake_case`
- Function: `snake_case`
- Variable: `snake_case`
- Class: `PascalCase`

## React와 TypeScript

- React Component: `PascalCase`
- TypeScript function/variable: `camelCase`

TypeScript type/interface, hook, test file, style file Naming은 Open Decision이다.

## Environment Variable

```text
UPPER_SNAKE_CASE
```

실제 변수 이름은 필요가 확정될 때 `.env.example`과 Runtime 설정 문서에 함께 추가한다.

## Environment

공동 개발 환경명은 다음으로 확정한다.

```text
dev
```

추가 Environment 이름과 승격 규칙은 Open Decision이다.

## AWS Resource

현재 기본 검토 형식은 다음과 같다.

```text
<project>-<env>-<component>
```

예:

```text
governance-dev-backend
governance-dev-artifacts
governance-dev-audit
```

이는 최종 강제 규칙이 아니다. Project prefix, Resource별 길이 제한/예외, Tagging, 개인 실험 prefix는 팀 확정이 필요하다. 개발 Region은 `us-east-1`이다.

## Rule ID

Candidate 형식:

```text
<SOURCE>-<RESOURCE_GROUP>-<CONTROL>-<NNN>
```

첫 Slice 계획용 Candidate example:

```text
GLOBAL-S3-PAB-001
```

추가 설계 예:

```text
CUSTOMER-S3-ENC-001
GLOBAL-SG-PUBLIC-001
CUSTOMER-IAM-MFA-001
```

위 형식과 값은 Shared Contract, Registry 및 Human Approval 전까지 예약되거나 ACTIVE인 식별자가 아니다. 원문 절 번호를 Rule ID에 넣지 않고 의미 변경 시 version과 재승인을 검토한다는 방향만 유지한다. 정확한 ID format, version 정책과 재사용 규칙은 Rule Registry 구현 시 확정한다.

## Control Key

첫 Slice 계획용 Candidate example:

```text
s3.public_access_block.enabled
```

추가 설계 예시는 다음과 같다.

```text
s3.encryption.at_rest
sg.ingress.least_privilege
cloudtrail.trail.enabled
```

Control Key는 향후 Control Registry가 소유한다. 위 값은 Shared Contract와 Registry review 전까지 실제 key로 예약되지 않는다. 전체 조합 규칙, 약어 목록, rename/version 정책은 아직 확정되지 않았다.

## Source 결과 표시 이름

내부 산식의 Source별 결과는 다음 표시 이름을 사용한다.

- `FSBP 기반 Governance Score`
- `CIS 기반 Governance Score`
- `AWS Resource Tagging Score`
- `Customer Policy Score`
- `Source별 Evaluation Coverage`
- `ISMS-P Mapping Coverage`
- `ISMS-P Evidence Readiness`

공식 산식과 동일한 구현이 아니므로 `AWS Security Hub Score`, `공식 FSBP Score`, `공식 CIS Score`, `ISMS-P Compliance Score`, `ISMS-P 인증 점수`는 사용하지 않는다. Core/Foundational/Hygiene/Control Tower Profile 이름은 개념적 설명이며 production Profile ID와 이름은 계속 Open Decision이다.

## Domain ID와 API Field

Domain ID와 API Field Naming은 [CONTRACTS.md](CONTRACTS.md)와 `packages/contracts/`를 따른다. 문서 예시에는 `job-001`, `asm-001`, `ar-001`, `fd-001`, `rem-001`, `dep-001`이 사용되지만 생성 알고리즘과 prefix 강제 여부는 확정되지 않았다.

API JSON 예시는 `snake_case`를 사용하고 있으나 모든 외부/내부 Schema에 대한 전역 Field case 규칙은 Contract 구현 시 확정한다.

## GitHub 관련 Naming

- Platform Repository와 Customer IaC Repository는 별도 Naming과 Lifecycle을 가진다.
- 일반 개발 branch는 `type/<issue-number>-kebab-case`를 따른다.
- Platform Repository의 일반 PR base는 `dev`이며 `main` 대상 PR의 유일한 허용 head는 같은 Repository의 `dev`다.
- Platform Repository의 source 검증 Required Check는 `validate-pr-source`다.
- Customer Remediation branch는 현재 설계 예시 `feature/governance-remediation-<id>`를 사용한다.
- GitHub Actions Workflow, Environment, OIDC Role/Subject Naming은 Open Decision이다.

## Open Decisions

- 실제 Remote Repository 이름과 확정 Repository 이름의 정합화
- Directory/File의 일반 case 규칙
- TypeScript type/hook/test Naming
- AWS Resource Naming/Tagging 최종 규칙
- Domain ID 생성과 prefix 규칙
- API Field Naming 전역 규칙
- GitHub Workflow/Environment Naming

참고: Naming 정본은 이 문서다. 과거 Notion 문서는 정본·참조 경로로 사용하지 않는다.
