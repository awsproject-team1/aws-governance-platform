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
type/kebab-case
```

예:

```text
feature/11-assessment-api
fix/42-policy-profile-validation
docs/update-contracts
chore/bootstrap-repository
```

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

확정 형식:

```text
<SOURCE>-<RESOURCE_GROUP>-<CONTROL>-<NNN>
```

예:

```text
CUSTOMER-S3-ENC-001
GLOBAL-SG-PUBLIC-001
CUSTOMER-IAM-MFA-001
```

원문 절 번호는 Rule ID에 넣지 않는다. 원문이 개정되어도 Rule identity와 과거 Finding 연결을 유지하기 위해서다. 의미가 바뀌면 ID 재사용 여부보다 Rule `version` 증가와 재승인 규칙을 우선 적용한다.

## Control Key

현재 설계는 다음과 같은 점 구분 key를 사용한다.

```text
s3.encryption.at_rest
sg.ingress.least_privilege
cloudtrail.trail.enabled
```

Control Key는 Control Registry가 소유한다. 위 예시를 넘어서는 전체 조합 규칙, 약어 목록, rename/version 정책은 아직 확정되지 않았다.

## Domain ID와 API Field

Domain ID와 API Field Naming은 [CONTRACTS.md](CONTRACTS.md)와 `packages/contracts/`를 따른다. 문서 예시에는 `job-001`, `asm-001`, `ar-001`, `fd-001`, `rem-001`, `dep-001`이 사용되지만 생성 알고리즘과 prefix 강제 여부는 확정되지 않았다.

API JSON 예시는 `snake_case`를 사용하고 있으나 모든 외부/내부 Schema에 대한 전역 Field case 규칙은 Contract 구현 시 확정한다.

## GitHub 관련 Naming

- Platform Repository와 Customer IaC Repository는 별도 Naming과 Lifecycle을 가진다.
- 일반 개발 branch는 `type/kebab-case`를 따른다.
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

## 근거 문서

- [Notion — Collaboration](https://app.notion.com/p/14d6ab0f231144c391fc52bd7e211ca4)
- [Notion — 04. Governance Rule / Policy / Assessment / Scoring](https://app.notion.com/p/3c66e3d0b3258045bc30fcf379a5be02)
- [Notion — 05. Remediation · GitHub · CI/CD · 보안](https://app.notion.com/p/3c66e3d0b32581229260d95b7a449863)
