# API Interface

이 문서는 Frontend ↔ Backend의 MVP HTTP Interface 설명 정본이다. 실제 Schema 코드가 생기면 `packages/contracts/`가 실행 가능한 정본이며 이 문서와 같은 Pull Request에서 동기화한다. 명시적으로 Open Decision 또는 candidate example로 표시한 항목은 호환성 보장이 아니다. 특히 첫 S3 Slice의 Rule/Control label과 아직 정의하지 않은 Apply/Verification field·status는 Shared Contract·Fixture·Contract Test 및 Producer/Consumer 검토 전까지 Proposed 상태다. 인증 Context에서 승인자를 얻고 Commit/Plan 변경 시 재승인을 요구하는 Security invariant는 유지한다. Domain 필드는 [CONTRACTS.md](CONTRACTS.md), 처리 구조는 [DESIGN.md](DESIGN.md)를 따른다.

## 공통 원칙

- Browser 요청은 Cognito Access Token으로 인증한다. API Gateway HTTP API JWT Authorizer가 Token을 검증하고 Backend가 검증된 claim의 목적·identity와 action별 RBAC를 다시 확인한다.
- Product Role은 `cognito:groups`의 정확한 `Admin`, `User` 값만 사용하며 Request Body나 Frontend 상태에서 Role을 받지 않는다. `Admin`은 User 기능을 포함한다.
- 현재 실행 가능한 권한 정본은 `START_ASSESSMENT`(`POST /assessments`)와 `READ_JOB`(`GET /jobs/{job_id}`)이며 Admin/User 모두 허용한다. 다른 Endpoint의 Action/Role Matrix는 Open Decision이고 등록 전까지 허용하지 않는다.
- 명시적인 Assessment/Remediation UI는 전용 API를 호출하며 자연어 Router를 거치지 않는다.
- 장시간 Workflow는 `202 Accepted + job_id`를 반환하고 `GET /jobs/{job_id}` Polling으로 추적한다.
- Job API는 진행 상태와 연결 ID만 반환한다. 실제 결과는 Domain API로 조회한다.
- API Callback/SSE/WebSocket은 MVP에 포함하지 않는다.
- 정확한 Content-Type, Pagination, Idempotency Key, API version prefix와 Role별 Endpoint Matrix는 Open Decision이다.

## Endpoint 요약

| Method | Endpoint | Purpose | Mode | 관련 Contract |
|---|---|---|---|---|
| `POST` | `/chat` | 자연어 Policy Q&A 또는 Workflow Routing | 조건부 Sync → Async | Job |
| `GET` | `/repositories` | 연결된 승인 IaC Repository 조회 | Sync | Repository Metadata |
| `POST` | `/assessments` | 구조화된 Assessment 시작 | Async | Job, Assessment |
| `GET` | `/assessments/{assessment_id}` | Assessment 메타데이터 조회 | Sync | Assessment |
| `GET` | `/assessments/{assessment_id}/results` | Rule별 평가 결과 조회 | Sync | AssessmentResult |
| `GET` | `/assessments/{assessment_id}/findings` | FAIL Finding 목록 조회 | Sync | Finding |
| `GET` | `/assessments/{assessment_id}/report?type=review\|final` | Assessment Report Artifact 조회 | Sync | Report Artifact |
| `POST` | `/assessments/{assessment_id}/policy-review` | 미확정 조건 보완 후 같은 Job 재개 | Async | AssessmentResult, Job |
| `POST` | `/remediations` | Finding 1개의 Remediation 시작 | Async | Job, Remediation |
| `GET` | `/remediations/{remediation_id}` | Remediation 메타데이터 조회 | Sync | Remediation |
| `GET` | `/deployments/{deployment_id}` | PR/Plan/Approval/Apply 상태 조회 | Sync | Deployment |
| `POST` | `/deployments/{deployment_id}/approval` | Apply 승인 또는 거절 | Async resume/terminate | Deployment |
| `GET` | `/jobs/{job_id}` | Workflow 진행 상태 Polling | Sync | Job, Error |

모든 Endpoint는 인증 대상이다. 현재 확정된 `POST /assessments`와 `GET /jobs/{job_id}` 외 Endpoint의 Admin/User 허용 Matrix는 Open Decision이며, Backend Action Policy에 등록되기 전까지 허용하지 않는다. Frontend 표시만으로 권한을 허용하지 않는다.

## Chat

### `POST /chat`

Purpose: 자연어 Policy Q&A와 요청 유형 Routing.

Request candidate example:

```json
{
  "message": "현재 운영 인프라의 S3 보안 설정을 평가해줘",
  "repository_id": "repo-001"
}
```

`repository_id`가 필요하지 않은 Policy Q&A에서의 필수 여부는 Open Decision이다.

Policy Q&A가 설정된 sync wait 안에 완료되면:

```text
200 OK
```

```json
{
  "type": "ANSWER",
  "answer": "..."
}
```

시간을 초과하거나 장시간 Workflow이면 처음 생성한 동일 Job을 유지한다.

```text
202 Accepted
```

```json
{
  "type": "JOB",
  "job_id": "job-003",
  "status": "QUEUED"
}
```

내부 sync timeout은 10초 초기값을 기준으로 검토하되 환경변수 이름과 운영값은 구현 시 확정한다.

## Repository

### `GET /repositories`

Purpose: 사용자가 Assessment에 사용할 수 있는, 이미 연결되고 승인된 Repository 목록 조회.

```json
{
  "items": [
    {
      "repository_id": "repo-001",
      "name": "company-infra",
      "default_branch": "main"
    }
  ]
}
```

Repository 연결·권한 설정 Endpoint는 현재 Workflow Contract에 정의되지 않았다. GitHub App 설치 및 Admin 연결 API는 Open Decision이다.

## Assessment

### `POST /assessments`

Purpose: 명시적인 Initial Assessment를 시작한다.

```json
{
  "phase": "INITIAL",
  "repository_id": "repo-001",
  "policy_profile_id": "profile-001",
  "policy_profile_version": 1
}
```

`phase`, `repository_id`, `policy_profile_id`, `policy_profile_version`는 모두 필수이며 unknown field는 거절한다. 이 Endpoint는 현재 `INITIAL`만 허용한다. MVP에는 기본 Profile이 없으므로 Profile ID 또는 version이 없는 요청은 거절한다. A는 transport/type과 호출자의 Profile 사용 권한을 검증하고, B Governance port는 `(policy_profile_id, policy_profile_version)` 존재 및 pin된 Rule의 ACTIVE 상태를 검증한다.

`admin_settings_snapshot_hash`, `scoring_version`, `EffectiveRuleSet`은 client request field가 아니다. A가 start 시점에 Admin Settings snapshot을 저장·hash로 pin한 뒤 B에서 Effective Rule Set과 scoring version을 얻어 C에 전달한다. 현재 Scope의 Resource inventory 및 전체/부분 표현은 D/C 공동 Open Decision이므로 request에 포함하지 않는다.

```text
202 Accepted
```

```json
{
  "job_id": "job-001",
  "status": "QUEUED"
}
```

실행 가능한 공개 정본은 `packages.contracts.AssessmentAcceptedResponse`다. 이 타입은 `job_id`와 고정된 `QUEUED` 상태만 소유하며 `assessment_id` 또는 internal revision을 노출하지 않는다. 실제 Handler와 HTTP `Idempotency-Key` 정책은 별도 A 작업이다.

### `GET /assessments/{assessment_id}`

Purpose: 평가 실행 메타데이터 조회.

```json
{
  "assessment_id": "asm-001",
  "job_id": "job-001",
  "phase": "INITIAL",
  "repository_id": "repo-001",
  "policy_profile_id": "profile-001",
  "status": "WAITING_REVIEW",
  "deployment_id": null,
  "has_review_report": true,
  "has_final_report": false,
  "created_at": "...",
  "completed_at": null
}
```

### `GET /assessments/{assessment_id}/results`

Purpose: Resource × Rule 상세 판정 조회.

```json
{
  "items": [
    {
      "assessment_result_id": "ar-001",
      "resource_id": "s3_bucket.logs",
      "rule_id": "<approved_rule_id>",
      "rule_version": 1,
      "evaluation_status": "FAIL",
      "execution_status": "SUCCESS"
    }
  ]
}
```

Pagination과 collection field 이름은 실행 Contract에서 함께 확정하며 현재 `items`는 response candidate example이다.

### `GET /assessments/{assessment_id}/findings`

Purpose: 사용자가 조치할 Rule-level Finding 조회.

```json
{
  "items": [
    {
      "finding_id": "fd-001",
      "assessment_result_id": "ar-001",
      "resource_id": "s3_bucket.logs",
      "control_key": "<approved_control_key>",
      "rule_id": "<approved_rule_id>",
      "rule_version": 1,
      "source_type": "GLOBAL",
      "status": "FAIL",
      "severity": "HIGH"
    }
  ]
}
```

### `GET /assessments/{assessment_id}/report?type=review|final`

Purpose: Assessment에 귀속된 Review 또는 Final Report 조회.

Report는 별도 `report_id`를 갖지 않는다. Backend는 S3 위치를 직접 노출하지 않고 권한 검증 후 응답 또는 제한된 다운로드 URL을 제공한다. 정확한 응답 형식은 Open Decision이다. 생성 전 요청은 `409 REPORT_NOT_READY`로 구분한다.

### `POST /assessments/{assessment_id}/policy-review`

Purpose: Scope/Admin Settings/승인·예외 근거 등 사람이 해소한 조건을 전달하고 동일 Job을 재개.

```json
{
  "decisions": [
    {
      "assessment_result_id": "ar-001",
      "control_key": "s3.encryption.at_rest",
      "resolution_type": "ADMIN_SETTINGS_UPDATED",
      "resolution_ref": "admin-settings-rev-008"
    }
  ]
}
```

`resolution_type` Enum은 Governance/Admin Settings Contract가 소유하며 아직 확정되지 않았다. Source 간 승자 Rule을 고르는 `selected_rule_id`는 사용하지 않는다.

```text
202 Accepted
```

```json
{
  "job_id": "job-001",
  "status": "RUNNING"
}
```

## Remediation

### `POST /remediations`

Purpose: 사용자가 선택한 Finding 하나의 개선 Workflow 시작.

```json
{
  "finding_id": "fd-001"
}
```

```text
202 Accepted
```

```json
{
  "job_id": "job-002",
  "status": "QUEUED"
}
```

### `GET /remediations/{remediation_id}`

```json
{
  "remediation_id": "rem-001",
  "job_id": "job-002",
  "finding_id": "fd-001",
  "status": "GENERATED",
  "patch_available": true,
  "created_at": "..."
}
```

큰 Diff는 메타데이터 응답에 포함하지 않는다. Patch Artifact Endpoint/응답 방식은 Open Decision이다.

## Deployment와 Approval

### `GET /deployments/{deployment_id}`

```json
{
  "deployment_id": "dep-001",
  "job_id": "job-002",
  "remediation_id": "rem-001",
  "status": "WAITING_APPROVAL",
  "pr_url": "...",
  "planned_commit_sha": "abc123...",
  "plan_available": true,
  "plan_hash": "sha256:...",
  "approval_status": "PENDING",
  "approved_commit_sha": null,
  "approved_plan_hash": null,
  "approved_by": null,
  "approved_at": null
}
```

Apply/Verification field 이름과 상태 어휘는 Shared Contract 구현 전까지 Open Decision이므로 이 response example에 고정하지 않는다. 구현 시 별도 Apply 결과와 AWS Actual verification artifact를 연결하되 IaC 판정과 혼합하지 않는다.

### `POST /deployments/{deployment_id}/approval`

승인:

```json
{ "decision": "APPROVE" }
```

거절:

```json
{ "decision": "REJECT" }
```

Backend가 인증 Context에서 승인자와 시각을 기록한다. Request에서 `approved_by`를 받지 않는다. 승인 시 현재 Commit SHA와 Plan Hash를 고정하고 Workflow를 재개한다. Apply 직전 값이 다르면 기존 승인을 무효화하고 재검증·재승인을 요구한다.

## Job

### `GET /jobs/{job_id}`

Purpose: Polling용 Workflow 진행 상태와 연결된 Domain ID 조회.

```json
{
  "job_id": "job-001",
  "job_type": "ASSESSMENT",
  "status": "WAITING_REVIEW",
  "current_step": "POLICY_REVIEW",
  "assessment_id": "asm-001",
  "remediation_id": null,
  "deployment_id": null,
  "error": null
}
```

Finding, Report, Patch, Plan 본문은 이 API가 반환하지 않는다.

실행 가능한 응답 정본은 `packages.contracts.JobResponse`이며 상태와 단계는 각각 `JobStatus`, `JobCurrentStep`으로 제한한다. `job_type`과 연결 ID는 opaque non-empty string이고 연결 전 ID는 `null`이다. Job 내부 `error`는 공개 `ApiError` detail 또는 `null`이며 `ApiErrorResponse`의 최상위 envelope를 중첩하지 않는다. 닫힌 `job_type` 집합과 `QUEUED`의 기본 `current_step`은 Open Decision이다.

내부 Job의 `requested_by`와 `revision`은 이 응답에 포함하지 않는다. Backend는 action-level `READ_JOB` 확인 뒤 User에게 `requested_by`가 자신의 Cognito subject와 같은 Job만 반환하고 Admin에게는 모든 Job 조회를 허용한다. 존재 여부와 소유권 거부를 HTTP에서 구분할지는 Handler Contract에서 확정한다.

## Error

Backend API의 최소 오류 응답은 다음 형식이다.

```json
{
  "error": {
    "code": "ASSESSMENT_NOT_FOUND",
    "message": "Assessment not found"
  }
}
```

실행 가능한 정본은 `packages.contracts.ApiError`와 최상위 `ApiErrorResponse`다. `code`와 `message`는 non-empty string이지만 endpoint별 `code`의 닫힌 Enum은 아직 확정하지 않는다. Job 응답의 `error` 필드는 `ApiError` detail만 사용한다.

| HTTP | Category |
|---|---|
| `400` | `INVALID_REQUEST` |
| `401` | `UNAUTHORIZED` |
| `403` | `FORBIDDEN` |
| `404` | `NOT_FOUND` |
| `409` | `INVALID_STATE`, `REPORT_NOT_READY` |
| `422` | `VALIDATION_ERROR` |
| `500` | `INTERNAL_ERROR` |
| `502` | `EXTERNAL_SERVICE_ERROR` |

Tool 내부 오류는 더 풍부한 `error_code`, `retryable`, `source`, `details`를 사용할 수 있지만 외부 API 최소 Contract와 혼합하지 않는다. AWS/GitHub/LLM 실패는 Governance `FAIL`이 아니라 Workflow 실행 오류다. Backend는 provider exception text를 응답에 복사하지 않고 lifecycle/CAS 충돌을 `INVALID_STATE`, repository provider 실패를 `EXTERNAL_SERVICE_ERROR`, 알 수 없는 예외를 `INTERNAL_ERROR`의 고정 message로 정제한다. 실제 Handler의 HTTP mapping과 endpoint별 닫힌 code 집합은 해당 Handler Contract에서 확정한다.

## 외부 Interface

### GitHub App

- 입력/식별: 승인 Repository, 기준 Branch/Commit, Patch/Remediation Metadata
- 결과: IaC Snapshot 또는 Branch/Commit/PR Metadata
- 인증: GitHub App Installation Token
- Callback/Webhook와 CI 결과 수신 Endpoint: Open Decision

### AWS Control Plane

- Agent Runtime/AWS Resource Tool: Read-Only `Describe/List/Get`
- Terraform Plan/Apply: GitHub Actions OIDC를 통한 별도 Role
- 직접 공개 HTTP Endpoint는 정의하지 않는다.

### GitHub Actions

- CI/Plan/Apply를 수행하고 Deployment/Job과 결과를 연결해야 한다.
- 결과 전달 방식, Artifact Callback, 서명/검증 Contract는 Open Decision이다.

## 근거 문서

- [Notion — 03. workflow/contract](https://app.notion.com/p/3c56e3d0b32580d38743ed1e6fd6b02f)
