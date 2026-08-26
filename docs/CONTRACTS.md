# Data and Domain Contracts

이 문서는 Repository 내부 Data/Domain Contract의 설명 정본이다. 실제 Schema 코드가 생기면 `packages/contracts/`가 실행 가능한 정본이며 이 문서와 항상 같은 Pull Request에서 동기화해야 한다.

## Contract 원칙

- 자유형 LLM 출력은 후속 단계 Contract로 사용하지 않는다.
- Producer가 만든 값은 Schema, Enum, Registry ID, 권한을 검증한 뒤 Consumer에 전달한다.
- 평가 실행 성공/실패와 Governance PASS/FAIL은 별도 축이다.
- 판정 정본은 `Resource × Rule`, UI/Report Grouping은 `Resource × Control`이다.
- 같은 Control의 Source별 판정·Severity·Evidence를 자동 병합하지 않는다.
- 상세 원문과 큰 결과는 Artifact로 저장하고 Contract에는 ID/Reference를 전달한다.
- 미확정 필드는 추측하지 않고 Open Decision으로 유지한다.

## Job

- Purpose: 사용자 요청 하나의 상위 Workflow 실행 추적
- Producer: Backend
- Consumer: Frontend, Parent Graph, 운영/Audit
- Required: `job_id`, `job_type`, `status`, `current_step`
- Optional/conditional: `assessment_id`, `remediation_id`, `deployment_id`, `error`
- Status: `QUEUED`, `RUNNING`, `WAITING_REVIEW`, `WAITING_APPROVAL`, `COMPLETED`, `FAILED`, `CANCELLED`
- Validation: 요청 접수 시 즉시 생성하며 sync→async 전환에도 같은 ID를 유지한다. Domain ID는 해당 단계 진입 시 생성한다.
- Versioning: Job Schema version field는 Open Decision이다.

`current_step`의 현재 확정 집합:

```text
LOAD_IAC
LOAD_POLICY_PROFILE
BUILD_EFFECTIVE_RULES
LOAD_POLICY_EVIDENCE
ASSESS
POLICY_REVIEW
GENERATE_FINDINGS
GENERATE_REPORT
GENERATE_REMEDIATION
CREATE_PR
CI_VALIDATION
AWS_DISCOVERY
PRE_DEPLOY_VALIDATION
TERRAFORM_PLAN
APPLY
POST_DEPLOY_VERIFICATION
```

실행 가능한 정본은 `packages.contracts.JobStatus`, `JobCurrentStep`, `JobResponse`다. `job_type`과 ID는 별도 Prefix나 닫힌 Enum을 강제하지 않는 opaque non-empty string이다. `JobResponse.error`는 `ApiError` detail 또는 `null`이며 내부 Tool 오류 세부정보를 포함하지 않는다. `job_type`의 닫힌 집합, `QUEUED`의 기본 `current_step`, Job Schema version은 Open Decision으로 유지한다.

## Control

- Purpose: 서로 다른 Policy Source가 공유할 수 있는 Governance 통제 어휘와 Grouping Key
- Producer/Owner: Governance Domain의 Control Registry
- Consumer: Rule, AssessmentResult, Finding, UI/Report Grouping
- Required semantic: `control_key`
- Validation: Source Mapping이 등록된 Control을 참조해야 한다.
- Versioning: Control Schema와 key 변경 정책은 Open Decision이다.

`Resource × Control`은 표시 묶음일 뿐 `final_status`, `final_severity`, Cross-Source Overall Score를 소유하지 않는다. Control의 정확한 코드 Schema는 아직 확정되지 않았다.

## Rule

- Purpose: 무엇을 어떤 근거와 Phase에서 평가할지 정의
- Producer: Governance/Policy 영역; Candidate는 Policy Agent가 보조 가능
- Consumer: Policy Profile, Effective Rule Set, Assessment Agent, Finding, Scoring
- Required: `rule_id`, `version`, `status`, `source_type`, `source_references[]`, `resource_type`, `control_key`, `evaluation_type`, `severity`, `requirement`, `remediation_type`
- Conditional: Scope/Threshold reference, Companion/Related Resource 정보
- Evaluation Type: `IAC`, `AWS`, `HYBRID`, `MANUAL`
- Severity: `CRITICAL`, `HIGH`, `MEDIUM`, `LOW`
- Known lifecycle states: `ACTIVE`, `DEPRECATED`; 전체 Candidate/Approval Status Enum은 Open Decision
- Validation: Registry와 Source Reference를 검증하고 `ACTIVE`는 `(rule_id, version)` Human Approval이 필요하다. 근거 없는 Criterion/Threshold를 생성하지 않는다.
- Versioning: requirement, severity, scope reference, control key, evaluation type, remediation type, resource/source mapping 등 평가 의미가 바뀌면 version을 올리고 재승인한다. 삭제 대신 `DEPRECATED`를 사용한다.

Rule ID 형식은 [NAMING.md](NAMING.md)를 따른다. 하나의 Rule이 여러 원문 항목을 근거로 가질 수 있으므로 단일 `source_reference`가 아닌 `source_references[]`를 사용한다.

## PolicyProfile

- Purpose: 조직이 실제 Assessment에 활성화할 Source/Rule과 Version Pin 집합 확정
- Producer: Admin
- Consumer: Backend, Governance Domain, Assessment
- Required semantic: `policy_profile_id`, `policy_profile_version`, 활성 Rule과 Version Pin
- Optional/conditional: Default Profile 표시와 Admin Settings 연결 방식
- Validation: User는 Admin이 등록한 Profile 중 선택하며 Profile 자체를 수정하지 않는다. 동일 Control의 여러 활성 Source Rule을 모두 유지하고 승자를 고르지 않는다.
- Versioning: Assessment는 사용한 Profile Version을 저장한다. 정확한 Profile Schema와 상태 Enum은 Open Decision이다.

## EffectiveRuleSet

- Purpose: Policy Profile에서 현재 Phase에 실제 평가할 Rule 집합 확정
- Producer: deterministic Governance Code
- Consumer: Assessment Agent, Coverage/Scoring, Audit
- Required semantic: `rule_id + version + source_type + severity`의 pin 목록과 Phase
- Validation: `INITIAL → IAC`, `PRE_DEPLOY/POST_DEPLOY → IAC + AWS + HYBRID`, `manual_review → MANUAL` 기준으로 결정론적으로 필터링한다.
- Versioning: 독립 객체 version보다 포함 Rule Version Pin Set을 재현성 기준으로 사용한다. 별도 Schema version은 Open Decision이다.

## IaCSnapshot

- Purpose: 특정 고객 Repository/Commit 시점의 Terraform 입력을 재현
- Producer: GitHub Repository Tool
- Consumer: Terraform Analyzer, Assessment, Remediation
- Required: `repository_id`, `commit_sha`, `files[]`, `snapshot_ref`
- Optional: 기준 branch/base ref의 정확한 저장 필드는 Open Decision
- Validation: 승인 Repository와 Commit 존재·권한을 검증한다. Terraform 원문은 S3 Artifact, 메타데이터는 Application Data Store에 둔다.
- Versioning: Commit SHA가 Snapshot identity의 핵심이며 Schema version은 Open Decision이다.

## Assessment

- Purpose: Initial/Pre/Post Governance 평가 실행 1회의 Header/Metadata
- Producer: Assessment Workflow
- Consumer: API, AssessmentResult/Finding, Report, Audit
- Required: `assessment_id`, `job_id`, `phase`, `repository_id`, `policy_profile_id`, `policy_profile_version`, `admin_settings_snapshot_hash`, `scoring_version`, `status`, `created_at`
- Conditional: `deployment_id`는 PRE/POST일 때, `review_report_s3_key`, `final_report_s3_key`, `completed_at`
- Phase: `INITIAL`, `PRE_DEPLOY`, `POST_DEPLOY`
- Validation: 각 실행에 새 ID를 만들고 과거 기록을 덮어쓰지 않는다. Rule Pin Set, Runtime Settings, Phase를 보존한다.
- Versioning: Assessment 자체보다 연결된 Profile/Rule/Settings/Scoring Version을 pin한다. Schema version은 Open Decision이다.

현재 실행 가능한 Assessment 정본은 `AssessmentPhase`와 `AssessmentAcceptedResponse`로 제한한다. `AssessmentAcceptedResponse`는 Initial Assessment 요청 수락 시 `job_id`와 고정된 `QUEUED` 상태만 전달한다. Assessment lifecycle status, 전체 Assessment record/projection과 create request의 Scope/Profile Schema는 확정 전까지 문서 Contract로만 유지한다.

## AssessmentResult / RuleEvaluation

현재 Workflow 문서의 객체 이름은 `AssessmentResult`이며 의미상 Resource × Rule의 Rule Evaluation이다.

- Purpose: 판정·Severity·Evidence·실행 상태의 평가 정본
- Producer: Assessment Agent 출력 + Schema Validator
- Consumer: Finding 생성, Report, Scoring, Audit
- Required: `assessment_result_id`, `assessment_id`, `resource_id`, `control_key`, `rule_id`, `rule_version`, `source_type`, `evaluation_status`, `severity`, `execution_status`
- Conditional: Evidence, explanation, error/reference의 정확한 필드는 Open Decision
- Governance status: 최소 `PASS`, `FAIL`; `MANUAL_REVIEW`, `N/A` 표현의 정확한 Enum spelling은 첫 Schema 구현에서 고정
- Execution status: 최소 `SUCCESS`, `ERROR`
- Validation: 실제 Rule/Version/Source/Enum을 검증한다. Tool/Agent 오류는 `evaluation_status = null`, `execution_status = ERROR`로 표현하며 `FAIL`을 만들지 않는다.
- Versioning: Rule Version과 Assessment 재현성 pin을 따른다.

Unit Disposition의 설계 어휘는 `NA_OUT_OF_SCOPE`, `MANUAL_REVIEW_SCOPE_UNDETERMINED`, `MANUAL_REVIEW_CRITERION_UNAVAILABLE`, `TO_JUDGE_PARTIAL`, `TO_JUDGE`다. 이것을 외부 `evaluation_status`와 어떻게 매핑할지는 Open Decision이다.

## Finding

- Purpose: FAIL AssessmentResult를 사용자 조치와 Remediation에 연결하는 Rule-level Record
- Producer: deterministic Finding 생성 단계
- Consumer: Frontend/Report, Remediation
- Required: `finding_id`, `assessment_id`, `assessment_result_id`, `resource_id`, `control_key`, `rule_id`, `rule_version`, `source_type`, `status`, `severity`
- Status: 현재 생성 조건상 `FAIL`; 해결 Lifecycle Status의 추가 Enum은 Open Decision
- Validation: Finding 하나는 Rule Evaluation 하나를 참조한다. Source가 다르면 동일 Resource × Control이어도 자동 중복 제거하지 않는다.
- Versioning: 연결된 Rule/Assessment를 통해 재현한다. Finding Schema version은 Open Decision이다.

## Report

Report는 별도 Domain Object가 아니다.

- Purpose: 특정 Assessment의 Review/Final 결과 Artifact
- Producer: Assessment Workflow
- Consumer: Frontend, User/Admin, Audit
- Required semantic: 소유 `assessment_id`와 Review/Final Artifact reference
- Validation: Backend 권한 검증 후 제공하고 기존 Artifact를 덮어쓰지 않는다.
- Versioning: 새 평가마다 새 Assessment/Artifact를 만들며 별도 `report_id`는 사용하지 않는다.

Report 본문 Schema와 Score/Coverage 표시 Contract는 Open Decision이다.

## Remediation

- Purpose: 선택된 Finding을 해결하기 위한 수정안 Record
- Producer: Remediation Workflow
- Consumer: GitHub Tool, Deployment, Frontend
- Required: `remediation_id`, `job_id`, `finding_id`, `status`, `patch_s3_key`, `created_at`
- Known status: `GENERATED`; 전체 Lifecycle Enum은 Open Decision
- Validation: MVP는 Finding 1개당 Remediation 1개다. 기존 IaC 전체 재작성 대신 최소 Patch/Diff를 기본으로 하며 Terraform 대상이 아니면 수동 가이드를 제공한다.
- Versioning: PR 수정/재생성 시 Remediation version 또는 새 객체 기준은 Open Decision이다.

PR, Plan, Approval, Apply 결과는 Remediation에 중복 저장하지 않고 Deployment가 소유한다.

## Deployment

- Purpose: PR → Plan → Human Approval → Apply 실행 이력
- Producer: Remediation/Deployment Workflow
- Consumer: Frontend, GitHub Actions 연동, Audit, Post-Deploy Assessment
- Required: `deployment_id`, `job_id`, `remediation_id`, `status`, `created_at`
- Conditional: `pr_url`, `planned_commit_sha`, `plan_s3_key`, `plan_hash`, `approval_status`, `approved_commit_sha`, `approved_plan_hash`, `approved_by`, `approved_at`, `apply_status`
- Known status: `WAITING_APPROVAL`; 전체 Deployment Status Enum은 Open Decision
- Approval decision: `APPROVE`, `REJECT`; stored approval status에는 최소 `PENDING`, `APPROVED`가 확인되며 전체 Enum은 Open Decision
- Validation: 승인은 `planned_commit_sha + plan_hash`에 바인딩한다. Apply 직전 동일성을 다시 검증하며 값이 바뀌면 재Plan/재승인한다.
- Versioning: 같은 Remediation의 재실행은 별도 Deployment 기록으로 보존할 수 있다. Schema version은 Open Decision이다.

Pre/Post Assessment는 자신의 `deployment_id`를 참조한다. Deployment에 Assessment ID를 중복 저장하지 않는다.

## Error

Backend 외부 API 최소 Contract:

```json
{
  "error": {
    "code": "ASSESSMENT_NOT_FOUND",
    "message": "Assessment not found"
  }
}
```

실행 가능한 정본은 `packages.contracts.ApiError`와 `ApiErrorResponse`다. `ApiErrorResponse`는 위 최상위 envelope를 만들고, `JobResponse.error`는 내부에 `ApiError` detail만 포함한다. `code`와 `message`는 non-empty string으로 검증하지만 endpoint별 `code`의 닫힌 Enum은 Open Decision이다.

Agent/Tool/Code 내부 오류에는 안정적인 code, 사용자용 message, retry 가능 여부, source, 선택 details가 필요하다. 내부 필드명 `error_code`와 외부 API `code`는 경계별 Contract로 구분한다. 예외 원문과 Secret을 외부 또는 로그에 노출하지 않는다.

## Scoring과 Coverage Contract

Severity Weight:

```text
CRITICAL = 10
HIGH     = 5
MEDIUM   = 2
LOW      = 1
```

- Unit: `Resource × Effective Rule`
- Weight: 판정 전에 `Effective Rule.severity`로 고정
- Source Score denominator: `PASS + FAIL`
- Rule Evaluation Coverage denominator: `PASS + FAIL + MANUAL_REVIEW`
- Coverage numerator: `PASS + FAIL`
- `N/A`, `EXECUTION_ERROR`: Score/Coverage 분모에서 제외하고 별도 보고
- 계산 경계: Policy Source별 독립 partition
- 금지: Cross-Source Overall Score, Control Group 최고 Severity 병합, Score 단독 배포 Gate

## Artifact Reference

S3 Artifact를 전달하는 공통 개념은 다음과 같다.

```json
{
  "artifact_ref": {
    "type": "S3",
    "bucket": "...",
    "key": "..."
  }
}
```

Bucket 이름을 외부 Contract에 고정하지 않는다. 정확한 공통 타입과 API 노출 방식은 Schema 구현 시 확정한다.

## Domain 관계

```text
Job
├─ Assessment(job_id)
│  ├─ AssessmentResult(assessment_id)
│  ├─ Finding(assessment_id)
│  └─ Review/Final Report artifacts
└─ Remediation(job_id, finding_id)
   └─ Deployment(job_id, remediation_id)
      ├─ PRE_DEPLOY Assessment(deployment_id)
      └─ POST_DEPLOY Assessment(deployment_id)
```

## Initial S3 Closed-loop Candidate

ADR 0002가 승인한 범위는 S3 Public Access Block을 첫 vertical slice로 사용하는 아키텍처와 안전 경계다. 아래 값과 흐름은 구현 계획을 위한 Candidate이며 아직 `packages/contracts/`, Registry, Fixture 또는 Contract Test가 뒷받침하는 실행 Contract가 아니다.

- Governed resource semantic: Terraform `aws_s3_bucket`과 companion `aws_s3_bucket_public_access_block`
- Proposed Rule ID example: `GLOBAL-S3-PAB-001`
- Proposed Control key example: `s3.public_access_block.enabled`
- Intended requirement: companion의 네 Public Access Block 설정이 모두 명시적으로 활성화됨
- Intended evaluation boundary: Initial/Post-Deploy의 IaC 표현과 AWS Actual verification을 별도 축으로 유지
- Intended remediation boundary: companion 추가 또는 필요한 설정만 변경하는 최소 Terraform Patch

위 Rule ID, Control key, version, severity, lifecycle status, evaluation/result Enum과 wire field 이름은 Shared Contract 구현 및 Producer/Consumer 검토 전까지 Proposed 상태다. 이 Candidate를 `ACTIVE` Rule로 등록하거나 평가 정본으로 사용해서는 안 된다.

Candidate source discovery URL은 `https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-control-block-public-access.html`이며 mutable `/latest/` 문서이므로 그 자체는 승인 근거가 아니다. Rule activation 전에 Source Reference는 최소한 다음 의미를 검증 가능한 형태로 보존해야 한다.

- source identity와 source revision/version
- 요구사항의 정확한 locator/section
- retrieval timestamp
- immutable captured artifact reference와 content hash
- 승인 대상 Rule ID/version 및 semantic content hash
- human approver identity와 approval timestamp

정확한 필드명, source version 값, locator, artifact key, hash와 Approval Schema는 실제 evidence capture 및 Shared Contract 구현 시 확정한다. 이 값들이 없거나 승인 대상 semantic content와 binding되지 않으면 Human Approval이 유효하지 않으며 Rule은 ACTIVE가 될 수 없다.

Closed-loop의 architecture invariant는 다음과 같다.

- Initial과 Post-Deploy의 Governance 판정은 각각 평가 대상 Commit의 Terraform 표현을 사용한다.
- Parser/Tool/Agent 오류를 Governance 위반으로 변환하지 않는다.
- AWS Actual Public Access Block 값은 Read-Only AWS Resource Tool이 관찰하고 D 영역 Deployment Workflow가 별도 verification artifact로 소유한다.
- Closed-loop 성공에는 새 Post-Deploy IaC 평가의 준수 결과와 AWS Actual 관찰의 일치가 모두 필요하다.
- Actual 불일치나 수집 오류는 IaC 판정을 바꾸지 않지만 완료를 차단하며 두 결과를 모두 보존한다.
- Pre/Post-Deploy 실행은 새 ID와 Artifact를 만들고 Initial 기록을 덮어쓰지 않는다.
- Apply는 Commit과 Plan에 binding된 별도 Human Approval 이후에만 GitHub Actions가 수행한다.

Assessment, Deployment, Approval, Apply, Verification의 exact 상태 집합, command 이름, API field와 ID 관계는 실행 Shared Contract가 생길 때까지 Open Decision이다.

Producer/Consumer 책임은 기존 Domain 경계를 유지한다.

- A: Job/API/Auth/Data와 Contract 저장·조회
- B: Global Control/Rule Registry, source evidence와 Rule activation approval
- C: Assessment, Result Schema Validation, deterministic Finding 생성
- D: Remediation, 고객 PR/CI/Plan/Approval/Apply, Actual verification, Post-Deploy 연결
- Shared Contract: ID, Enum, Schema 호환성과 Fixture

## Contract 변경 절차

1. Producer, Consumer, 영향 Owner를 식별한다.
2. `docs/CONTRACTS.md`와 `packages/contracts/`를 같은 branch/PR에서 변경한다.
3. API 영향이 있으면 `docs/API.md`, Architecture 영향이 있으면 `docs/DESIGN.md`를 갱신한다.
4. 호환성, Migration, Version 증가와 Fixture 영향을 기록한다.
5. 필요한 Contract Test를 먼저 또는 함께 추가한다.
6. 장기적인 Contract 결정이면 ADR을 작성한다.
7. Required CI와 최소 1명 Review를 통과한다.

Contract 변경 승인 방식, Schema versioning 전략, Python/TypeScript 공유 타입 생성 방식은 Open Decision이다.

## 근거 문서

- [Notion — 03. workflow/contract](https://app.notion.com/p/3c56e3d0b32580d38743ed1e6fd6b02f)
- [Notion — 04. Governance Rule / Policy / Assessment / Scoring](https://app.notion.com/p/3c66e3d0b3258045bc30fcf379a5be02)
