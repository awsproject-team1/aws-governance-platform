# System Design

이 문서는 Cloud Governance & Compliance Agent의 구현 구조와 책임 경계를 설명한다. 제품 범위는 [PRD.md](PRD.md), Endpoint는 [API.md](API.md), 필드와 상태는 [CONTRACTS.md](CONTRACTS.md)를 정본으로 사용한다.

## System Context

```text
Customer User / Admin
  → React Web Application
  → API Gateway + Lambda Backend
  → LangGraph Parent Graph
      ├─ Policy Subgraph
      ├─ Assessment Subgraph
      └─ Remediation / Deployment Subgraph
  → Agent / deterministic Code Node / Tool
  → Customer Policy, Customer GitHub IaC, AWS Control Plane
```

플랫폼은 고객 AWS Account 내부에 회사 단위로 배포된다. 고객 정책, IaC Snapshot, 평가 결과, Audit 데이터는 고객 환경에 보존한다. 고객 Workload Terraform은 별도 고객 Repository의 정본이며 이 Monorepo에는 포함하지 않는다.

## Customer-Deployed Architecture

- 배포: 공급자가 버전 고정한 CloudFormation 패키지, 고객의 Change Set 검토 후 설치
- MVP Region: `us-east-1`
- Frontend/Backend/Agent/Data/IAM: 고객 AWS Account에 배포
- 격리: 서비스와 Customer Workload를 IAM Role, Terraform State, Naming/Tag로 논리 분리
- Multi-Tenancy: 고객사별 독립 배포이므로 MVP 내부 `tenant_id` 격리는 필수가 아님

### VPC 원칙

MVP의 Backend Lambda와 Agent Runtime은 고객 기존 VPC/Subnet에 연결하지 않는다. AWS Resource 평가는 Read-Only IAM Role로 AWS Control Plane API를 호출한다. Existing VPC Integration, NAT/VPC Endpoint, Route/DNS, Private API/DB/On-Prem 접근은 확장 범위이며 필요 조건을 확인한 뒤 별도 결정한다.

## Frontend

하나의 React Application이 Admin/User 화면을 Role에 따라 노출한다. Login, 공통 Layout/Router, API Client, Job 상태 표시와 Policy, Assessment, Finding/Report, Remediation/Deployment, GitHub, User/Role, Audit 화면을 제공한다.

Frontend의 역할은 사용자 입력, 명시적 기능 선택, Job Polling, 결과 표시다. 권한 판단의 정본이 아니며 Backend가 JWT/RBAC를 재검증한다. Streaming은 MVP 범위가 아니므로 장시간 작업은 Polling한다.

## API Gateway와 Lambda Backend

API Gateway + Lambda 중심의 서버리스 Backend를 사용한다. Backend의 책임은 다음과 같다.

- API Gateway JWT Authorizer가 검증한 Cognito claim의 목적·필수 identity 확인과 action별 Admin/User RBAC
- Request/Response/Error Contract 적용
- Repository/Profile/Scope 등 명시적 Context 검증
- Job 생성·조회·상태 전이
- LangGraph Workflow 시작·재개
- DynamoDB/S3 공통 접근
- Human Review와 Approval 요청 처리

Backend는 정책 의미, Resource × Rule 판정, Terraform 수정·배포 로직을 소유하지 않는다. 자연어 의미 분류는 Parent Graph Router가 담당하며 명시적 기능 API는 Router를 생략한다.

### Backend Python Package와 Lambda 경계

초기 Backend는 Python 3.14의 Framework-free 경계를 사용한다. `apps.backend`가 Backend package이고 제품 Lambda Handler는 `apps.backend.handlers` 아래에 위치한다. #49는 `apps.backend.handlers.http_transport`에 API Gateway HTTP API v2 event extraction과 JSON proxy response의 순수 helper만 둔다. 실제 Lambda entry point, route binding, Repository/use-case composition은 후속 Handler Sub-issue에서 추가한다.

`apps.backend.handlers._bootstrap_probe`는 package staging과 호출 가능성만 확인하는 private non-deployable probe다. Infrastructure의 Lambda Handler로 연결하지 않으며 event/context 내용을 읽거나 기록하지 않는다.

Backend Runtime의 직접 Dependency는 `apps/backend/requirements.txt`에 정확한 Version으로 고정하고 개발 Tool은 root `requirements-dev.txt`에 둔다. Lambda ZIP stage root에는 `apps/backend`와 승인된 first-party import closure만 같은 package 경로로 배치하고 third-party dependency는 stage root에 설치한다. 전체 Monorepo, Test, 문서, Frontend를 Artifact에 복사하지 않는다. Lambda Layer, Python build backend, 실제 ZIP 생성 자동화는 첫 제품 Handler와 배포 경계가 확정될 때 재검토한다.

### Job Application과 Repository 경계

`apps.backend.jobs`는 immutable 내부 Job, 닫힌 최소 상태 전이, revision 증가, write-once Domain ID, 소유권 검사와 public error sanitation을 담당한다. 공개 `JobResponse`에는 내부 `requested_by`와 `revision`을 투영하지 않는다. 상세 lifecycle은 [ADR 0005](decisions/0005-job-lifecycle-boundary.md)를 따른다.

`apps.backend.repositories`는 AWS-independent Job/Artifact port와 injected DynamoDB/S3 adapter를 제공한다. Application은 Boto3 응답, DynamoDB item map, S3 URL 또는 provider exception을 받지 않는다. DynamoDB Job update는 저장 revision 조건을 원자적으로 재검사하고 S3 Artifact는 raw bytes의 SHA-256 주소와 `If-None-Match: *`로 overwrite를 막는다. Adapter는 client와 resource를 생성하거나 환경변수에서 찾지 않고 호출자가 주입한다. 현재 SDK를 직접 import하는 composition root가 없으므로 runtime dependency는 추가하지 않으며, 실제 Lambda consumer는 SDK를 정확한 version으로 package해야 한다. 상세 결정은 [ADR 0006](decisions/0006-dynamodb-s3-repository-boundary.md)를 따른다.

제품 Handler, table/bucket 이름, 환경변수, GSI, 목록/페이지네이션, TTL, retry/backoff, presigned URL과 Artifact type prefix는 Open Decision이다.

## Cognito

Admin과 User는 동일 Cognito User Pool과 로그인 화면을 사용한다. API Gateway HTTP API JWT Authorizer가 서명, issuer, token 시간 유효성과 구성된 audience/client binding을 검증한 뒤 Backend를 호출한다. 실제 User Pool, App Client, issuer, audience와 Route/Scope 배포 설정은 Infrastructure 구현 전에 확정해야 한다.

Backend는 Authorizer가 검증한 claim에서 `token_use == "access"`, 비어 있지 않은 `sub`와 `client_id`, `cognito:groups`를 다시 확인한다. Group 이름은 정확히 `Admin`과 `User`만 Product Role로 해석하고, Request Body나 임의 Custom Claim의 Role은 사용하지 않는다. `Admin`은 User 기능을 포함한다. 현재 Action 정본은 `START_ASSESSMENT`와 `READ_JOB`이며 두 Role 모두 허용한다. 등록되지 않은 Action, 잘못된 Token 용도, 유효한 Product Role이 없는 Principal은 거부한다.

Auth 모듈은 API Gateway event shape와 분리하고 cryptographic JWT 검증이나 JWKS 조회를 반복하지 않는다. #49는 `requestContext.authorizer.jwt.claims`를 유일한 claim 입력 경로로 고정하고, `cognito:groups`가 JSON array로 보존되지 않으면 fail-closed 한다. transport는 malformed verified-claim event를 `401 UNAUTHORIZED`로 변환하며 Request Body나 임의 custom claim의 Role을 사용하지 않는다. 상세 결정은 [ADR 0004](decisions/0004-cognito-jwt-rbac-boundary.md)를 따른다. 사용자 초대, MFA, Token revocation, Scope와 나머지 Endpoint Role Matrix는 Open Decision이다.

## LangGraph와 Agent Runtime

### Parent Graph

Parent Graph는 자연어 request type을 분류하고 기능별 Subgraph를 선택하며 Domain ID와 최소 실행 Context를 연결한다. 상세 Domain 데이터와 큰 Artifact를 Graph State에 복제하지 않는다.

### Policy Subgraph

Policy Q&A, 정책 원문 해석, Rule Candidate 생성 보조, Policy Evidence 설명을 담당한다. Terraform/AWS 평가는 수행하지 않는다.

### Assessment Subgraph

IaC Snapshot, Policy Profile, Effective Rule Set, Evidence, 필요 시 AWS Actual State를 조합해 Structured AssessmentResult를 생성한다. deterministic Code Node가 Phase/Scope/Rule 후보와 평가 가능 여부를 먼저 확정한다.

### Remediation Subgraph

선택된 Finding, 현재 IaC, Rule/Evidence를 사용해 최소 Patch/Diff와 영향 설명을 만든다. 이후 GitHub PR, CI, Pre-Deploy, Plan, Approval, Apply, Post-Deploy 연결을 오케스트레이션하되 Agent가 직접 Apply하지 않는다.

### Agent Runtime

Agent Runtime은 Policy Q&A, IaC 의미 비교, Remediation 생성 같은 추론을 수행하며 허용된 Tool만 호출한다. Customer Workload에 대한 AWS Write 권한을 갖지 않는다. 저비용/고성능 모델 라우팅 기준과 Skill 구현 방식은 PoC 후 확정한다.

## Tool Layer

외부 시스템 조회·Action은 Tool, 결정론적 형식·권한·상태 처리는 Code/Schema, 의미 해석·추론·생성은 Agent가 담당한다.

### Policy Knowledge Tool

고객 정책 원문을 S3에 저장하고 관리형 Retrieval 계층을 통해 관련 Chunk와 Source Metadata를 반환한다. 내부 Evidence가 없다는 상태와 Tool 실행 오류를 구분한다.

현재 B 구현은 `tools/policy-knowledge/port.py`에 검증 경계와 Fixture Adapter만 둔다. 결과 Evidence의 Source ID/version/section/content hash를 Registry와 대조하며 실제 Retrieval 저장소와 Vendor는 확정하지 않는다.

고객이 업로드하는 사내 규정은 서식이 고정되어 있지 않으므로 파일을 그대로 LLM에 넣지 않고 형식 지식을 Loader 한 곳에 가둔다. 경계는 `업로드 보안 검사 → Format별 Document Loader → Canonical Policy Document → 결정론적 Segmentation → Frozen Document → Knowledge Index`다.

- `sources/upload.py`: 확장자 allowlist, 실제 signature 확인, Macro/암호화/압축폭탄 차단, 파일명 재생성. Parser에 검사되지 않은 바이트가 닿지 않게 한다.
- `sources/loaders/`: MD/TXT, HTML, DOCX, 텍스트 PDF Loader와 XLSX Control Matrix Loader. HTML은 DOM 중첩 상한을 두어 깊게 중첩된 몇 KB짜리 파일이 `RecursionError`로 Loader를 죽이지 않고 `ExtractionError`가 되게 한다. DOCX/XLSX의 XML part는 `loaders/office_xml.py` 한 곳을 거치며, DTD/Entity 선언을 거부하기 전에 인코딩을 UTF-8로 고정한다. 원시 byte에서만 선언을 찾으면 UTF-16 part가 그대로 통과하기 때문이다. 형식별 위치 정보를 `locator`에 보존한다. PDF는 실제 객체를 열어 압축 Object Stream도 처리하며, 이미지 전용 페이지가 섞이면 부분 추출 대신 OCR 필요 상태로 실패한다. XLSX는 header와 데이터 행을 TABLE Block으로 만들고 수식을 실행하지 않은 채 수식 문자열과 캐시값을 함께 보존한다.
- `sources/canonical_document.py`: 형식 비종속 Block 표현. 이후 단계는 어떤 형식에서 왔는지 몰라도 동작한다.
- `sources/segmentation.py`: 교체 가능한 Structure Profile과 문서 비종속 정규화·해시.
- `sources/ingestion.py`: `document_version` 단위 동결. Parser/Profile 정체성을 동결 기준에 포함해 Parser 변경이 조용한 근거 변경이 되지 않게 한다.
- `sources/index.py`: 동결 항목만 담는 Knowledge Index. Policy Q&A가 업로드 문서를 원문 locator와 함께 답할 수 있게 한다.

결정론적 Profile이 없는 문서는 Rule Candidate 경로를 지원하지 않으며 조용히 빈 결과를 내지 않고 명시적으로 실패한다. 텍스트 PDF는 글꼴 크기로 heading을 복원할 수 있을 때 `CanonicalHeadingProfile`을 사용한다. heading 구조를 복원할 수 없는 PDF는 다른 Structure Profile이 필요하다고 명시적으로 실패하며, 스캔 PDF는 빈 문서가 아니라 OCR 필요 상태로 분기한다. XLSX는 일반 문서 Profile로 흡수하지 않고 `XlsxControlMatrixProfile`이 데이터 행 단위로 동결한다. 숨김 시트·행·열과 병합·필터 상태는 데이터를 누락하는 조건으로 쓰지 않고 Review warning으로 보존한다.

### External Evidence Tool

내부 Knowledge가 부족할 때 AWS 공식 문서와 허용된 공식 Governance Source를 검색한다. 외부 검색 실패가 기존 정책 판정을 자동으로 뒤집지 않는다. 구체 관리형 검색 구현은 가용성과 PoC 결과를 확인한다.

현재 B 구현은 `tools/external-evidence/port.py`의 명시적 Source/identifier-prefix allowlist와 Fixture Adapter까지만 제공한다. 실제 네트워크 호출은 하지 않으며 `NOT_FOUND`와 Tool `ERROR`를 분리한다.

### GitHub Tool

GitHub App Installation Token으로 고객이 승인한 Repository만 접근한다. IaC 파일과 Commit SHA를 조회하여 Snapshot을 만들고 Remediation Branch/Commit/PR을 생성한다. Terraform Apply 권한은 갖지 않는다.

### AWS Resource Tool

`Describe*`, `List*`, `Get*` 기반으로 AWS Actual State 사실을 수집·정규화한다. Compliance를 판정하지 않으며 Tool 실패를 Governance `FAIL`로 변환하지 않는다.

### 내부 Code Node

Terraform Parser, Schema Validation, Rule Filtering, Effective Rule Set 구성, Job 상태 전이, Data Access, Score 계산은 결정론적 Code로 구현한다. Parser는 구조적 사실만 추출하며 정책 의미 판정은 Assessment Agent가 담당한다.

## Governance Domain

```text
Policy Source
  → Control Registry / Source Mapping
  → Rule + Approval(rule_id, version)
  → Policy Profile
  → Phase별 Effective Rule Set
  → Resource × Rule Evaluation
  → FAIL Rule Finding
  → Resource × Control Grouping
  → Policy Source별 Score / Coverage
```

같은 Control의 여러 Source Rule은 독립 평가한다. `Resource × Rule`이 판정 정본이고 `Resource × Control`은 비교·표시 Grouping이다. Cross-Source 최종 Status/Severity/Overall Score를 자동 생성하지 않는다. 세부 계약은 [CONTRACTS.md](CONTRACTS.md)를 따른다.

결정론적 B 구현은 `packages/governance/`의 Source/Control/Mapping/Rule/Profile Registry, 승인 content-hash binding, Phase filter, Source별 scoring으로 구성된다. Scoring은 Severity 가중치를 Effective Rule Set에서 직접 읽고 Consumer가 보낸 값과 다르면 거부하므로, 판정 전 가중치 고정 규칙이 신뢰 경계 밖 입력으로 우회되지 않는다. `packages/contracts/governance.py`는 B→C Rule/Evidence/Metric 형식만 검증하고 판정 로직을 포함하지 않는다. `apps/frontend/src/policy/PolicyGovernancePanel.jsx`는 공통 Router/Auth/API를 소유하지 않고 Props와 callback만 공개한다. Policy Agent 경계는 `agent/prompts/policy_agent.md`에 고정한다.

Rule Candidate는 원문이나 LLM이 정체성을 만드는 경로가 아니다. Structured proposal은 의미 필드와 limitation만 내고, Domain Service가 서버 보유 Frozen section을 Source Reference로 결합한다. Rule ID와 승인자는 Area A의 인증/RBAC 및 서버 ID 할당 경계에서 들어오며 Domain이 version을 계산하고 exact semantic snapshot 승인과 ACTIVE 등록을 함께 수행한다. 승인 semantic hash에서 identity와 lifecycle status를 분리하고 승인 당시 ACTIVE snapshot을 별도로 보존해 DEPRECATED 뒤에도 과거 Profile/Effective Rule Set을 재현한다.

Policy Source Registry와 Frozen Index는 `(source_id, source_version)`을 identity로 사용한다. 새 Assessment는 ACTIVE Rule만 선택하고, 과거 재현은 immutable approved snapshot을 사용한다. Scoring은 기존 `(resource_id, rule_id, rule_version, source_id)`를 입력 identity로 사용해 재전송 중복을 거부한다. 이 구현은 실제 PASS/FAIL 판정, Check Registry, Terraform/AWS Fact Schema를 소유하지 않는다.

Global Source는 `packages/governance/sources/catalog.py`에서 두 단계로 관리한다.

1. `GlobalSourceDefinition`: 공식 Publisher/Reference/version과 제품 역할을 검증한 catalog entry
2. `FrozenGlobalSourceSnapshot`: 선택 Control, 제외 사유, canonical content hash, mapping version, control-set hash를 가진 평가 입력 snapshot

Reference만 확인된 Source를 scored/evaluable로 승격하지 않는다. Snapshot 변경 비교는 추가/제외 Control과 content/mapping 변경을 보고하며 기존 snapshot을 덮어쓰지 않는다. FSBP만 기본 Source 후보이고 CIS/Tagging은 명시 선택, Control Tower는 Customer Capability 확인 후 선택, ISMS-P는 Profile이 아닌 Mapping View다.

FSBP S3는 `sources/official_snapshot.py`에서 공식 문서 전문이 아닌 검토 가능한 metadata projection으로 동결한다. 관찰한 S3 Control Set 전체를 선택/제외로 분할하고 선택 Control evidence hash를 다시 계산한다. 기존 승인 Rule의 의미가 같더라도 Source Reference가 새 snapshot과 다르면 Rule을 변형하거나 자동 승인하지 않고 새 version과 Human Approval을 요구한다. SG/VPC는 `fixtures/rules/fsbp-sg-vpc-source-inventory.json`에 공식 Control inventory만 기록하며 B→C evaluator/fact 계약이 공동 승인되기 전에는 Rule Candidate로 승격하지 않는다.

`packages/governance/compliance/readiness.py`는 ISMS-P 항목에서 Project Control → Rule pin → Evidence/Finding/Remediation 추적과 Mapping Coverage/Evidence 상태 분포를 만든다. Assessment PASS/FAIL과 Compliance Score는 만들지 않는다.

## Assessment

### Initial S3 IaC Assessment

최초 Slice는 Human Approval을 거친 S3 Public Access Block Rule candidate를 IaC 방식으로 평가하는 아키텍처를 검증한다. `GLOBAL-S3-PAB-001`과 `s3.public_access_block.enabled`는 현재 Proposed label이며, source revision/locator/content hash와 승인 대상 semantic hash가 binding된 Rule Approval 및 Shared Contract가 생기기 전에는 ACTIVE Rule이나 실행 정본이 아니다.

Initial Assessment는 지정 Repository Commit의 Terraform Snapshot에서 대상 `aws_s3_bucket`과 companion `aws_s3_bucket_public_access_block`을 정규화한다. 의도한 criterion은 companion과 네 차단 설정이 모두 활성화되는 것이지만 정확한 Rule version, severity, status와 result Enum은 Open Decision이다.

Initial 판정은 AWS Actual 조회를 요구하지 않는다. Parser/Tool/Agent 오류는 Governance 위반으로 변환하지 않고 별도 실행 오류로 보존한다.

### Pre/Post-Deploy Assessment

Pre-Deploy는 Remediation PR의 최신 IaC, AWS Actual State, `terraform plan`을 사용해 Drift와 Apply 가능성을 검증하고 새 Assessment/Result/Artifact를 Deployment에 연결한다. Post-Deploy는 승인된 Apply 이후 새 Assessment와 Result를 생성하고 같은 승인된 S3 Rule 기준으로 배포된 Commit의 Terraform 표현을 다시 평가한다.

AWS S3 Public Access Block 실제값은 D 영역 Deployment가 소유하는 별도 verification artifact로 저장한다. Closed-loop 완료에는 Post-Deploy IaC의 준수 결과와 AWS Actual 관찰의 일치가 모두 필요하다. Actual 값 불일치나 수집 오류는 IaC Result를 바꾸지 않지만 완료를 차단한다. Exact verification field와 status vocabulary는 Shared Contract 구현 전까지 Open Decision이다.

Post-Deploy의 새 준수 결과는 과거 Initial 위반, Finding, Report를 수정하거나 삭제하지 않는다.

### Finding과 Report

AssessmentResult는 Resource × Rule 정본이다. 위반 결과는 Source별 Finding으로 연결한다. Report는 별도 Domain Object가 아니라 Assessment에 귀속된 Review/Final S3 Artifact다. 과거 결과는 덮어쓰지 않는다.

## Remediation과 배포 Closed-loop

최초 Slice는 다음 architecture flow의 완주를 목표로 한다. Rule activation, exact status/field와 wire schema가 Shared Contract와 Fixture로 승인되기 전에는 실행 흐름으로 취급하지 않는다.

1. User가 승인된 S3 Public Access Block Rule의 Finding 하나를 선택한다.
2. Remediation Agent가 companion resource가 없으면 추가하고, 있으면 비활성 또는 누락된 설정만 활성화하는 최소 Terraform Patch와 영향 분석을 만든다.
3. GitHub Tool이 고객 기준 branch에서 Remediation branch, Commit, PR을 만든다.
4. 고객 Repository GitHub Actions가 `terraform fmt -check`, `terraform validate`, TFLint, Checkov를 실행한다.
5. 최신 IaC와 AWS Actual로 Pre-Deploy Assessment를 수행한다.
6. GitHub Actions가 OIDC로 TerraformPlanRole을 사용해 고객 기존 State/Backend 기준 `terraform plan`을 만든다.
7. Deployment에 평가 대상 Commit과 Plan hash를 저장한다.
8. 사람은 Plan과 검증 결과를 보고 승인 또는 거절한다.
9. Apply 직전 승인 Commit/Plan 동일성을 재검증한다.
10. GitHub Actions가 OIDC로 TerraformDeploymentRole을 사용해 승인된 Plan을 Apply한다.
11. 최신 IaC를 재평가해 새 Post-Deploy 결과와 Report를 만들고, AWS Actual Public Access Block 값을 별도 verification evidence로 보존한다.

CI/Plan 실패 또는 Reject 시 Apply로 진행하지 않는다. 위 고객 Remediation PR은 Platform Repository의 개발 PR과 별개다. Platform 개발 PR은 Sub-issue 구현과 로컬 검증 후 `dev` 대상으로 만들고, Required CI와 사람 Review를 거쳐 Merge한다.

## IAM과 Security Boundary

- Web User: Cognito + Backend RBAC
- Agent Runtime: Application Data 권한 + Customer Workload Read
- GitHub Integration: 승인 Repository의 필요한 최소 Metadata/Contents/PR 권한
- TerraformPlanRole: AWS/State Read 및 필요한 Lock 권한, Workload Write 금지
- TerraformDeploymentRole: 승인된 Apply에 필요한 제한된 Infrastructure/State Write
- GitHub Actions: OIDC Federation을 통한 임시 자격증명

OIDC Trust는 고객 Organization/Repository와 Branch 또는 Environment 및 `aud`를 제한해야 한다. 정확한 Subject 조건은 고객 GitHub 운영 방식과 실제 Token을 확인한 뒤 확정한다.

LLM 출력, 검색 문서, Terraform Patch는 신뢰하지 않는다. Structured Schema, Registry/ID, Authorization, CI, Plan, Human Approval을 순차 적용한다.

## Data Storage

- DynamoDB: Job, Assessment, AssessmentResult, Finding, Remediation, Deployment, Repository/Profile Metadata, Audit Event
- S3: IaC Snapshot, Policy Evidence, Raw AWS Result, Report, Patch/Diff, Plan, Apply Result
- LangGraph Checkpoint: 실행 위치와 interrupt/resume용 최소 상태; Application Data 정본이 아님

DynamoDB는 ID/상태/관계/조회 메타데이터, S3는 큰 원본·Artifact를 담당한다. Job item은 `job_id` key와 내부 revision을 사용하며 생성은 ID 부재, 갱신은 expected revision 일치를 조건으로 한다. Adapter는 현재 Job과 lifecycle이 산출할 수 있는 next state를 대조해 owner, job type, write-once ID와 terminal 상태 우회를 거부한 뒤 전체 Job item을 교체한다. condition failure는 duplicate 또는 revision conflict로 변환한다.

Artifact port는 raw bytes를 `sha256:<digest>`로 식별하고 S3 adapter 내부에서 `sha256/<digest>` key로 변환한다. Put은 `If-None-Match: *`를 사용하며 precondition failure 시 기존 bytes의 digest를 재검증해 같은 내용만 idempotent success로 처리한다. Bucket, S3 key와 provider 응답은 public contract가 아니다.

Table/bucket 이름과 환경변수, GSI, 목록/페이지네이션, TTL/보존, retry, presigned URL, artifact-type prefix는 Open Decision이다. 상세 persistence 결정은 [ADR 0006](decisions/0006-dynamodb-s3-repository-boundary.md)를 따른다.

## Observability

CloudWatch Logs/Metrics는 API latency, Job, Graph/Subgraph, Agent/Model Routing, Tool 결과, Schema 실패, Retry, Assessment/Deployment 상태를 기록한다. 원문 Prompt, 정책 전문, IaC 전체를 무조건 기록하지 않고 `request_id`, `job_id`, Domain ID, Rule/Repository 식별자 중심으로 상관 분석한다.

CloudTrail은 AWS API, AssumeRole/OIDC, DeploymentRole, Apply 변경을 감사한다. Application Audit Log는 Rule 승인, Profile/Settings 변경, Assessment, Review, Remediation 선택, PR, Approval/Reject, Apply, Post-Deploy 결과를 보존한다. 구체 보존기간은 Open Decision이다.

## Deployment와 CloudFormation

`infrastructure/`는 Governance Platform 자체의 API Gateway, Lambda, Cognito, DynamoDB, S3, Agent Runtime, CloudWatch, IAM 등을 고객 계정에 배포하는 CloudFormation/IAM/Parameter를 관리한다. 고객 Workload Terraform이나 고객 State는 포함하지 않는다.

Marketplace Quick Launch, Offline/Mirrored 설치와 Existing VPC Integration은 MVP 밖이다.

## 주요 데이터 흐름

```text
Request → Job(DynamoDB) → Workflow
  → IaC/Policy/AWS raw artifact(S3)
  → Assessment + Result + Finding(DynamoDB)
  → Review/Final Report(S3)
  → Remediation(DynamoDB) + Patch(S3)
  → Deployment(DynamoDB) + Plan/Apply result(S3)
  → Post-Deploy Assessment(new records/artifacts)
```

## Repository 책임 경계

`apps`, `packages`, `agent`, `tools`, `infrastructure`, `ci`, `fixtures`, `tests`, `docs`의 세부 Owner 경계는 [AGENTS.md](../AGENTS.md)를 따른다. 공통 Contract와 Fixture를 먼저 고정해 A/B/C/D가 다른 영역 완료를 기다리지 않고 개발할 수 있어야 한다.

## Open Decisions

- Backend/Agent 장시간 실행의 구체 Runtime 전환 조건
- 모델 라우팅과 Skill 구현 방식
- 최초 S3 Slice 이후 확장할 Resource와 Rule Set
- AWS Resource Naming/Tagging 최종안
- Terraform State Backend/Locking의 팀 개발환경 운영 규칙
- OIDC Subject/Environment 조건
- 데이터별 보존기간과 SLO

## 근거 문서

- [Notion — 02. 서비스 아키텍처 · 배포 · Tool 구조](https://app.notion.com/p/3c66e3d0b32581c38a77f1e9d5346c22)
- [Notion — 03. workflow/contract](https://app.notion.com/p/3c56e3d0b32580d38743ed1e6fd6b02f)
- [Notion — 04. Governance Rule / Policy / Assessment / Scoring](https://app.notion.com/p/3c66e3d0b3258045bc30fcf379a5be02)
- [Notion — 05. Remediation · GitHub · CI/CD · 보안](https://app.notion.com/p/3c66e3d0b32581229260d95b7a449863)
- [Notion — 06. 운영 · Observability · 검증 · 테스트](https://app.notion.com/p/3c66e3d0b3258114a489f7f87adec967)
