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

실행 가능한 공개 정본은 `packages.contracts.JobStatus`, `JobCurrentStep`, `JobResponse`다. `job_type`과 ID는 별도 Prefix나 닫힌 Enum을 강제하지 않는 opaque non-empty string이다. `JobResponse.error`는 `ApiError` detail 또는 `null`이며 내부 Tool 오류 세부정보를 포함하지 않는다. `job_type`의 닫힌 집합, `QUEUED`의 기본 `current_step`, Job Schema version은 Open Decision으로 유지한다.

Backend 내부 정본은 `apps.backend.jobs.Job`이며 공개 응답과 분리한다. 생성자는 Workflow가 `initial_step`을 명시하도록 요구하고 `QUEUED`, revision `0`에서 시작한다. 내부 `requested_by`는 Cognito subject를 보존하지만 `JobResponse`에는 노출하지 않는다. User는 자신의 Job만 읽고 Admin은 모든 Job을 읽을 수 있으며, 이 resource ownership 검사는 action-level `READ_JOB` 권한 검사와 함께 적용한다.

최소 상태 전이는 다음으로 닫는다.

```text
QUEUED          → RUNNING | FAILED | CANCELLED
RUNNING         → RUNNING | WAITING_REVIEW | WAITING_APPROVAL | COMPLETED | FAILED | CANCELLED
WAITING_REVIEW  → RUNNING | FAILED | CANCELLED
WAITING_APPROVAL→ RUNNING | FAILED | CANCELLED
COMPLETED | FAILED | CANCELLED → terminal
```

모든 성공 전이는 revision을 정확히 1 증가시키며 `RUNNING → RUNNING`은 진행 단계 갱신에 사용한다. `FAILED`는 sanitized `ApiError`가 필수이고 다른 상태는 error를 가질 수 없다. `assessment_id`, `remediation_id`, `deployment_id`는 최초 연결 후 변경하거나 제거할 수 없다. Repository update는 저장된 현재 Job에서 lifecycle next state를 다시 산출해 직접 생성한 모델이 owner, job type, write-once ID 또는 terminal 상태를 우회하지 못하게 한다. retry/backoff, terminal resume, timestamp, 보존기간은 Open Decision이다. 상세 결정은 [ADR 0005](decisions/0005-job-lifecycle-boundary.md)를 따른다.

## Control

- Purpose: 서로 다른 Policy Source가 공유할 수 있는 Governance 통제 어휘와 Grouping Key
- Producer/Owner: Governance Domain의 Control Registry
- Consumer: Rule, AssessmentResult, Finding, UI/Report Grouping
- Executable Contract: `packages/contracts/governance.py::Control`
- Required: `control_key`
- Validation: Source Mapping이 등록된 Control을 참조해야 한다.
- Versioning: Control Schema와 key 변경 정책은 Open Decision이다.

`Resource × Control`은 표시 묶음일 뿐 `final_status`, `final_severity`, Cross-Source Overall Score를 소유하지 않는다. 첫 실행 Contract는 미확정 metadata를 만들지 않고 `control_key`만 고정한다. Registry가 key 존재 여부를, Source/Resource/Control Mapping Registry가 원문 `document_id + document_version + section + content_hash`와 `resource_type + control_key` 조합을 검증한다.

## PolicySource / SourceControlMapping

- Executable Contract: `PolicySource`, `SourceReference`, `SourceControlMapping`
- `PolicySource` Required: `source_id`, `source_type`, `source_version`
- `SourceReference` Required: `document_id`, `document_version`, `section`, `content_hash`
- `SourceControlMapping` Required: `source_reference`, `resource_type`, `control_key`
- Validation: Source Registry의 `(source_id, source_version)`, Control Registry의 key, 등록된 Source/Resource/Control 조합을 모두 검증한다. 동일 Source의 여러 version은 함께 보존하며 한 `source_id`의 `source_type`은 version 사이에서 바뀌지 않는다. Policy Source의 상세 metadata와 관리 API Schema는 Open Decision이다.

### Global Governance Source Catalog

공식 Reference를 찾은 상태와 평가 가능한 Frozen Snapshot을 구분한다. `GlobalSourceDefinition`은 Publisher, framework version, 공식 URL, 검증 시점, 권장 역할과 결과 종류만 기록한다. 이 정의만으로 Rule, Finding, Score를 생성할 수 없다.

`FrozenGlobalSourceSnapshot`은 실제 적용 Control Set을 고정할 때 사용한다. Required metadata는 `source_id`, immutable `source_version`, `framework_version`, `snapshot_date`, `collected_at`, 공식 Reference URL, canonical content hash, `selected_control_ids`, 제외 Control과 이유, `mapping_version`, 서버 계산 `control_set_hash`다. 정상 수집 경로는 서버가 보유한 `FrozenDocument`에서 Source identity와 section content hash 집합을 가져오며 외부 입력이 canonical hash를 정하지 않는다. 같은 framework version에 Control이 추가될 수 있으므로 snapshot version과 Control Set hash를 함께 보존한다. 빈 Control Set은 scored Source로 동결할 수 없다.

| Source | 검증한 framework version | 역할 | 결과 | 기본 Profile |
| --- | --- | --- | --- | --- |
| AWS FSBP | `1.0.0` | Security Baseline | Source Score/Coverage | 후보 |
| CIS AWS Foundations | `5.0.0` | 두 번째 Security Baseline | 독립 Source Score/Coverage | 아님 |
| AWS Resource Tagging | `1.0.0` | Governance Hygiene | 독립 Source Score/Coverage | 아님 |
| AWS Control Tower Controls | 단일 고정 version 없음 | 조건부 Governance | Control 상태/조건부 Coverage | 금지 |
| ISMS-P | 인증기준 안내서 `2023.11.23` | Mapping/Evidence | Mapping Coverage/Evidence Readiness | 금지 |

CIS Publisher는 `CIS`이며 AWS Security Hub 문서는 delivery/mapping reference다. Control Tower는 `AWS Organizations`, `AWS Control Tower`, Landing Zone/OU Context와 필요한 AWS Config/Security Hub 사용 조건을 확인하기 전에는 Profile Source로 선택할 수 없다. Preventive/Detective/Proactive 의미를 하나의 IAC PASS/FAIL로 바꾸지 않는다.

Tagging Global Source는 지원 Resource의 Tag 지원 여부와 Tag 존재 여부까지만 소유한다. 필수 Tag Key, Value 형식, Environment, Owner, CostCenter, Project 규칙은 승인된 Customer Policy가 소유한다.

`select_global_profile_sources`는 개념적 Source 조합만 검증한다. 실제 `PolicyProfile`은 계속 승인 Rule version을 pin하며 production Profile ID/이름은 Naming 합의 전 확정하지 않는다. ISMS-P처럼 Mapping/Evidence 전용 Source는 Assessment Profile에 넣지 않는다.

현재 공식 Reference 정의 fixture는 `fixtures/policy/global-source-catalog.json`이다. `not_a_frozen_snapshot = true`이므로 CIS/Tagging/Control Tower/ISMS-P 지원 완료를 뜻하지 않는다. 실제 Source 전문 또는 허용된 control metadata를 수집하고 Control Set을 승인한 뒤 별도 snapshot fixture를 만들어야 한다.

FSBP S3의 첫 공식-reference metadata snapshot은 `fixtures/policy/aws-fsbp-s3-official-snapshot.json`이다. 이는 AWS 문서 전문 복제본이 아니라 공식 URL, 관찰한 FSBP v1.0.0 S3 Control ID 12개, 선택 `S3.8`, 나머지 11개 제외 사유, 검토에 필요한 S3.8 metadata를 동결한 최소 projection이다. `FrozenOfficialControlSet`은 관찰 집합이 선택/제외 집합으로 정확히 분할되는지 확인하고 evidence content hash, canonical content hash, control-set hash를 서버에서 다시 계산한다.

기존 `GLOBAL-S3-PAB-001@1`의 requirement/severity/evaluation type은 공식 S3.8 metadata와 의미상 일치하지만 승인된 `SourceReference`는 새 공식 snapshot에서 파생된 reference와 일치하지 않는다. 따라서 기존 ACTIVE content를 자동 수정하지 않으며, 공식 snapshot을 pin하는 새 Rule version과 Human Approval 전에는 이를 공식 재검증 완료 Rule로 Effective Rule Set에 전달하지 않는다.

### 임의 문서로부터의 Source Reference 생성

고객이 업로드하는 사내 규정은 서식이 정해져 있지 않으므로 `SourceReference`를 손으로 작성하지 않고 원문에서 생성한다. 여러 파일을 그대로 LLM에 넣지 않고 다음 경계를 지난다.

```text
Uploaded File
  -> 보안 검사 및 실제 파일 형식 확인   packages/governance/sources/upload.py
  -> Format별 Document Loader           packages/governance/sources/loaders/
  -> Canonical Policy Document          packages/governance/sources/canonical_document.py
  -> 결정론적 Segmentation              packages/governance/sources/segmentation.py
  -> Frozen Document + Source Reference packages/governance/sources/ingestion.py
  -> Knowledge Index / Policy Q&A       packages/governance/sources/index.py
  -> 제한된 Rule Candidate 제안          packages/governance/rules/candidates.py
  -> 서버 소유 Reference/ID/version 결합 packages/governance/services/
  -> Human Review / Approval
```

형식 지식은 Loader에만, anchor·해시·동결 규칙은 그 뒤 단계에만 둔다. 이 분리가 없으면 DOCX 표, XLSX 셀, PDF 페이지, HTML DOM 위치가 추출 시점에 문자열로 평탄화되어 Evidence가 원문 어디를 가리키는지 되돌릴 수 없다.

**Canonical Policy Document**는 Contract가 아니라 Domain 내부 자료구조다. `document_id`, `document_version`, `detected_format`, `source_hash`, `parser_profile`, `parser_version`, `blocks[]`, `extraction_warnings[]`를 갖는다. `CanonicalBlock`은 `block_id`, `block_type`(heading/paragraph/list_item/table/cell/code/quote), `text`, `heading_path`, `locator`, `content_hash`를 갖는다.

`locator`는 형식별 원문 위치를 보존하되 안정적인 canonical 문자열로만 노출한다.

| 형식 | locator 예시 |
| --- | --- |
| Markdown | `md:line=12` |
| HTML | `html:dom=body>div[2]>h2[1]` |
| DOCX | `docx:body=7`, `docx:body=9/row=2/cell=1` |
| PDF | `pdf:page=3/block=2` |
| XLSX | `xlsx:sheet=Controls/range=A3:D3` |

`SourceReference.section`은 지금 형태(heading 경로 anchor)를 그대로 유지한다. 구조화된 locator metadata를 Contract 필드로 올릴지는 Open Decision이며 Contract Review 대상이다. 현재 locator는 `DocumentSection.locator`와 `PolicyEvidence.locator`로만 전달한다.

- `section`은 문서 안에서 유일한 안정적 주소다. 같은 heading 경로가 반복되면 문서 순서로 결정론적으로 구분한다.
- `content_hash`는 정규화된 원문 구간의 sha256이다. 정규화는 줄바꿈 표기와 줄 끝 공백만 정리하고 문자를 치환하지 않는다. 원문에 충실해야 Evidence로 쓸 수 있기 때문이다.
- 항목별 추출 신뢰도가 `HIGH`가 아니면 Rule Candidate로 넘기기 전에 Human Review를 요구한다.

**형식 지원 상태**

| 형식 | 상태 | 처리 |
| --- | --- | --- |
| Markdown / TXT | 지원 | heading, 목록, 표, 코드, 인용을 결정론적으로 구분 |
| DOCX | 지원 | Style(`Heading n`, `제목 n`)/`outlineLvl` 제목, `numPr` 목록, `gridSpan`/`vMerge` 표 |
| HTML | 지원 | 실행 요소 제거 후 heading/목록/표 중심 DOM 변환 |
| 텍스트 PDF | 지원 | 실제 PDF 객체의 텍스트 계층을 좌표 순서로 추출, 글꼴 크기 기반 heading, `pdf:page=N/block=M` 보존 |
| 스캔 PDF | 미지원 | 이미지 전용 페이지가 하나라도 있으면 부분 추출하지 않고 OCR 필요 상태로 실패 |
| XLSX | 지원 | Control Matrix 전용. header 뒤 데이터 행 1개를 1항목으로 동결하고 `xlsx:sheet=…/range=A3:D3` 보존 |

XLSX는 일반 heading 문서로 처리하지 않는다. 각 시트에서 값이 두 칸 이상 있는 첫 행을 header로 확정하고, 그 뒤의 비어 있지 않은 데이터 행마다 header와 값을 하나의 TABLE Block으로 만든다. Section anchor는 `<sheet-slug>/row-<행 번호>`이며 `XlsxControlMatrixProfile`만 이 Block을 항목으로 동결한다.

- 수식은 실행하지 않는다. 수식 문자열과 OOXML에 저장된 계산 캐시값을 `[formula:=…; cached:…]`로 함께 보존하며 캐시값이 없거나 오류이면 실패한다.
- 병합 셀은 시작 셀만 값을 유지하고 continuation은 빈 칸으로 남긴다.
- 숨김 시트·행·열도 누락하지 않고 읽으며, 병합 범위와 AutoFilter를 포함해 `extraction_warnings`에 남긴다.
- header 앞의 비어 있지 않은 행은 preamble으로 제외하고 경고한다. 빈 header 이름, 중복 header 이름, header 범위 밖 데이터는 의미를 추측하지 않고 실패한다.

**Segmentation 동결**: 수집이 성공하면 해당 `document_version`의 항목 집합을 즉시 동결한다. 동결된 version을 재수집하면 항목 경계와 `content_hash`를 비교해 동일함을 확인하고, 다르면 덮어쓰지 않고 실패한다. 동결 기준값(`snapshot_hash`)에는 Parser 정체성(`parser_profile`, `parser_version`)과 Profile 정체성이 포함된다. Parser가 바뀌어 Block 경계가 달라졌는데 같은 version이 통과하면 과거 Finding의 근거가 조용히 달라지기 때문이다. 반대로 원문 바이트 해시(`source_hash`)는 포함하지 않는다. 줄바꿈이나 문서 말미 공백 변화까지 동결 위반으로 만들지 않기 위해서다. 원문이 개정되면 기존 version을 수정하지 않고 새 `document_version`을 발급하며 과거 Finding은 계속 이전 version의 동결된 항목을 참조한다.

결정론적 Profile이 없는 문서(제목 구조가 없는 평문 등)는 아직 Rule Candidate 생성과 Finding의 `source_reference` 앵커를 지원하지 않는다. 이 경우 항목 0개를 반환하지 않고 명시적으로 실패한다. XLSX는 heading 구조가 아니라 전용 `XlsxControlMatrixProfile`을 사용한다. 미구현을 성공으로 위장하면 어디서 막혔는지 드러나지 않기 때문이다.

### 업로드 파일 보안 경계

업로드 파일은 신뢰할 수 없는 입력이며 Parser는 그 자체가 공격 표면이다. `validate_upload`가 Loader보다 먼저 실행되며 안정적인 `reason` 코드로 거부한다.

| reason | 대상 |
| --- | --- |
| `EXTENSION_NOT_ALLOWED` | 확장자 allowlist(`md`, `markdown`, `txt`, `html`, `htm`, `docx`, `xlsx`, `pdf`) 밖 |
| `MACRO_ENABLED_FORMAT` | `docm`/`xlsm`/`pptm`, 컨테이너 내부 `vbaProject.bin` |
| `LEGACY_BINARY_FORMAT` | `doc`/`xls`/`ppt`/`rtf` |
| `ARCHIVE_NOT_ALLOWED` | `zip`/`7z`/`gz`/`tar` 등 일반 압축파일 |
| `SIGNATURE_MISMATCH` | 확장자와 실제 파일 signature/구조 불일치 |
| `ENCRYPTED_DOCUMENT` | 암호화 OOXML(`EncryptedPackage`, OLE header), `/Encrypt` PDF |
| `ARCHIVE_LIMIT_EXCEEDED` | entry 수, 해제 크기, 압축비 한도 초과 |
| `ARCHIVE_UNSAFE_ENTRY` | 컨테이너 내부 경로 탈출 entry |
| `INVALID_TEXT_ENCODING` | UTF-8이 아니거나 NUL 포함 |
| `EMPTY_FILE` / `FILE_TOO_LARGE` | 빈 파일, 최대 크기 초과 |
| `MALWARE_DETECTED` / `SCAN_UNAVAILABLE` | 악성코드 검사 거부 및 검사 미완료 |

- 선언된 `Content-Type`은 신뢰하지 않는다. metadata로만 보존하고 형식 판정은 signature로 한다.
- 저장 key는 업로드 파일명을 재사용하지 않고 내용 해시로 새로 만든다. 원본 파일명은 표시용으로만 정제해 보존한다.
- 악성코드 Scanner는 주입 대상이며, 없으면 조용히 통과하지 않고 `extraction_warnings`에 남는다. 운영 배포 전에 Scanner 연결과 Parser 실행 격리가 필요하다.

### Policy Knowledge Index

`FrozenDocumentIndex`는 동결된 항목만 담고 `document_id + document_version` 범위로 검색해 `PolicyEvidence`를 만든다. Policy Knowledge Tool은 Adapter 결과의 Source Reference가 다음 중 하나일 때만 통과시킨다.

1. Control에 Mapping된 Source Reference
2. 동결 Index가 `section + content_hash`까지 동일하다고 확인한 항목

두 번째 경로가 없으면 업로드한 사내 규정은 Rule로 승격되기 전까지 Q&A에 쓸 수 없고, 검증 없이 통과시키면 Adapter가 만들어낸 section/hash가 그대로 Evidence가 된다.

LLM에 맡기지 않는 것: 실제 파일 형식 판별, 원문 hash 생성, Source Reference locator 생성, 승인 없는 `ACTIVE` Rule 생성, 실제 PASS/FAIL 판정.

## Rule

- Executable Contract: `Rule`, `RuleApproval`; deterministic Registry: `packages/governance/rules/`
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

`RuleApproval`은 `rule_id`, `version`, canonical semantic content의 `rule_content_hash`, `approved_by`, `approved_at`을 보존한다. Semantic content는 `source_type`, `source_references`, `resource_type`, `control_key`, `evaluation_type`, `severity`, `requirement`, `remediation_type`이며 identity인 `rule_id + version`과 lifecycle metadata인 `status`는 hash 입력에서 분리한다. 따라서 `DEPRECATED` 이후에도 승인 당시 의미 hash와 ACTIVE snapshot을 재현할 수 있다. `ACTIVE` 등록 시 ID/version과 content hash가 모두 일치해야 한다.

Rule Candidate의 Structured Output은 `resource_type`, `control_key`, `evaluation_type`, `severity`, `requirement`, `remediation_type`과 선택 `limitations[]`만 제안한다. `rule_id`, `version`, `status`, `source_type`, Source Reference/locator/hash, approval 필드는 서버 소유이며 Candidate 입력에 있으면 거부한다. Source Reference는 서버가 보유한 `FrozenDocument` section에서만 결합하고 등록된 Mapping과 대조한다. Candidate는 항상 Human Review 대상이고 unresolved limitation 또는 확인되지 않은 추출 confidence가 있으면 ACTIVE로 승인할 수 없다. Candidate 전체 상태 Enum은 계속 Open Decision이다.

`RuleCandidateApplicationService`는 인증/RBAC를 구현하지 않는다. Area A가 인증한 사람과 서버가 할당한 Rule ID를 전달하면 Domain이 다음 version을 부여하고 exact approval snapshot과 ACTIVE 등록을 한 작업으로 처리한다. In-memory Registry는 reference implementation이며 DB/Endpoint는 확정하지 않는다. Rule 폐기 시 actor, 시각, 사유와 승인 content hash를 Audit Entry로 보존한다.

## PolicyProfile

- Executable Contract: `PolicyProfile`, `RulePin`
- Purpose: 조직이 실제 Assessment에 활성화할 Source/Rule과 Version Pin 집합 확정
- Producer: Admin
- Consumer: Backend, Governance Domain, Assessment
- Required: `policy_profile_id`, `policy_profile_version`, `rule_pins[]`의 `rule_id + version`
- Optional/conditional: Default Profile 표시와 Admin Settings 연결 방식
- Validation: User는 Admin이 등록한 Profile 중 선택하며 Profile 자체를 수정하지 않는다. 동일 Control의 여러 활성 Source Rule을 모두 유지하고 승자를 고르지 않는다.
- Versioning: Assessment는 사용한 Profile Version을 저장한다. Default 표시와 Profile 상태 Enum은 Open Decision이다.

새 Assessment는 현재 `ACTIVE`인 pin만 사용한다. 과거 Assessment 재현은 Rule의 현재 lifecycle 상태가 아니라 immutable approval snapshot을 사용하므로, pin된 Rule이 나중에 `DEPRECATED`되어도 당시 Effective Rule Set hash가 바뀌지 않는다. User의 Profile 선택은 identity/version 선택일 뿐 Profile 내용 수정 권한을 의미하지 않는다.

## EffectiveRuleSet

- Executable Contract: `EffectiveRuleSet`, `AdminSettingsSnapshotReference`
- Purpose: Policy Profile에서 현재 Phase에 실제 평가할 Rule 집합 확정
- Producer: deterministic Governance Code
- Consumer: Assessment Agent, Coverage/Scoring, Audit
- Required: Profile ID/version, Phase, `admin_settings_snapshot_hash`, ACTIVE Rule records, canonical `rule_set_hash`
- Rule Set Phase: `INITIAL`, `PRE_DEPLOY`, `POST_DEPLOY`, `MANUAL_REVIEW`
- Validation: `INITIAL → IAC`, `PRE_DEPLOY/POST_DEPLOY → IAC + AWS + HYBRID`, `MANUAL_REVIEW → MANUAL` 기준으로 결정론적으로 필터링한다.
- Versioning: 독립 객체 version보다 포함 Rule Version Pin Set과 `rule_set_hash`를 재현성 기준으로 사용한다. 별도 Schema version은 Open Decision이다.

`EffectiveRuleSet.phase`는 `RuleSetPhase`이고 `Assessment.phase`는 `AssessmentPhase`다. 두 Enum을 분리해서 쓴다. `RuleSetPhase`는 `AssessmentPhase`의 상위 집합이며 `MANUAL_REVIEW`만 추가로 갖는다. `MANUAL_REVIEW`는 사람이 IaC/AWS 평가 경로 밖에서 판정할 Rule을 선별하는 모드이므로 Assessment 실행 Phase가 아니고 `Assessment.phase`에 저장하지 않는다. 두 어휘의 변환은 `RuleSetPhase.for_assessment()`와 `RuleSetPhase.assessment_phase`가 담당하며, 후자는 `MANUAL_REVIEW`에서 `None`을 반환한다.

## PolicyEvidence와 Policy Q&A

- Executable Contract: `PolicyEvidence`, `EvidenceQueryResult`, `PolicyQuestion`, `PolicyAnswer`
- `PolicyEvidence` Required: `evidence_id`, 검증된 `source_reference`, `locator`, `excerpt`
- Query Result Status: `FOUND`, `NOT_FOUND`, `ERROR`
- Validation: `FOUND`는 Evidence가 필요하고 `NOT_FOUND`는 Evidence/Error를 갖지 않으며 `ERROR`는 안정적인 `error_code`가 필요하다. 원문, 검색 결과, excerpt는 신뢰할 수 없는 입력으로 취급한다.
- Boundary: Policy Q&A, 원문 해석, Candidate 생성 보조, Evidence 설명만 허용한다. Resource × Rule 판정과 Remediation 생성은 포함하지 않는다.
- Open Decision: 실제 Retrieval/Vendor, 외부 API field naming, locator의 영속 저장 방식

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
- Phase: `INITIAL`, `PRE_DEPLOY`, `POST_DEPLOY` (`AssessmentPhase`; Effective Rule Set 선별 모드인 `MANUAL_REVIEW`는 포함하지 않는다)
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
- Governance status: `PASS`, `FAIL`, `MANUAL_REVIEW`, `N/A`; 실행 오류일 때는 `null`
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

`apps.backend.jobs.sanitize_public_error`는 exception message를 복사하지 않고 신뢰된 category만 고정 응답으로 변환한다. lifecycle/CAS/duplicate 충돌은 `INVALID_STATE`, repository provider 실패는 `EXTERNAL_SERVICE_ERROR`, 그 밖의 예외는 `INTERNAL_ERROR`로 정제한다. 이 최소 mapping은 Handler별 닫힌 error code 집합을 확정하지 않으며 provider response, request ID, table/bucket/key, credential-like 값을 공개 detail에 포함하지 않는다.

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
- Source Score numerator: `PASS` 단위의 Severity Weight 합
- Source Score denominator: `PASS + FAIL` 단위의 Severity Weight 합
- Rule Evaluation Coverage denominator: `PASS + FAIL + MANUAL_REVIEW`
- Coverage numerator: `PASS + FAIL`
- `N/A`, `EXECUTION_ERROR`: Score/Coverage 분모에서 제외하고 별도 보고
- 계산 경계: Policy Source별 독립 partition
- 금지: Cross-Source Overall Score, Control Group 최고 Severity 병합, Score 단독 배포 Gate

실행 Contract는 `(RuleEvaluationMetric[], EffectiveRuleSet) → SourceScoreCoverage[]`다. 입력은 `resource_id`, pin된 `rule_id + rule_version`, `source_id`, `source_type`, Rule의 `severity`, `evaluation_status`, `execution_status`를 전달한다. 출력은 Source별 `score`, `coverage`, status별 count, `scoring_version = "1"`을 보존한다. 결과 배열 자체에는 Overall field를 두지 않는다. `source_id`는 C가 Rule의 검증된 Source Reference에서 전달해야 하는 B→C 필드다.

가중치의 정본은 Consumer payload가 아니라 Effective Rule Set이다. Scoring은 각 Metric을 `(rule_id, rule_version)`으로 Effective Rule에 bind하고 그 Rule의 `severity`로 가중한다. Effective Rule Set 밖의 Rule을 참조하거나, `severity`·`source_type`이 pin된 Rule과 다르거나, `source_id`가 그 Rule의 검증된 Source Reference가 아니면 Score를 계산하지 않고 Validation Error를 낸다. 판정 전에 가중치를 고정한다는 규칙이 Consumer 입력을 신뢰하는 방식으로 우회되지 않게 하기 위해서다.

Metric 재전송에 의한 이중 집계를 막기 위해 기존 필드 `(resource_id, rule_id, rule_version, source_id)`를 한 계산 입력 안의 identity로 사용한다. 같은 identity가 두 번 오면 계산하지 않고 Validation Error를 낸다. 새 Contract 필드는 추가하지 않는다. Scoring dispatcher는 지원하는 과거 version만 허용하며 현재 지원 version은 `1`이다.

S3 B→C 제안 fixture는 `fixtures/assessments/s3-fsbp-b-to-c-proposal.json`이다. 기존 executable shape의 positive/negative/tool-error 예시는 검증되지만, 이는 Area C의 evaluator 연결 완료를 뜻하지 않는다. `check_id`, `check_version`, 새 Fact Schema를 일방적으로 필수화하지 않았으며 다음 항목은 Area C Owner acceptance가 필요하다: 결정론적 evaluator binding, 네 가지 S3.8 observation 표현과 누락 처리, 예정된 `Resource × Rule × Source`마다 terminal metric 하나가 반드시 생성되는 completeness 규칙. 마지막 규칙이 없으면 누락 metric이 Coverage 분모에서 사라질 수 있으므로 운영 평가 전 공동 확정이 필요하다.

Global Source 화면 명칭은 내부 결정론적 산식을 명확히 드러내는 `FSBP 기반 Governance Score`, `CIS 기반 Governance Score`, `AWS Resource Tagging Score`를 사용한다. AWS Security Hub의 공식 산식을 그대로 구현하고 동일 입력을 사용하지 않는 한 `AWS Security Hub Score`, `공식 FSBP/CIS Score`라고 부르지 않는다.

### ISMS-P Mapping Coverage / Evidence Readiness

ISMS-P는 `calculate_source_metrics` 입력이 아니며 독립 Compliance Score를 만들지 않는다. `ComplianceItemMapping`은 항목 ID/제목/적용 범위, Project Control, Rule pin, 자동 Evidence, 누락 Evidence, Finding/Remediation 식별자와 다음 상태 중 하나를 보존한다.

- `AUTOMATED_EVIDENCE`
- `PARTIAL_EVIDENCE`
- `EVIDENCE_MISSING`
- `MANUAL_REVIEW`
- `OUT_OF_SCOPE`

Mapping Coverage는 선택한 ISMS-P 항목 중 하나 이상의 Project Control에 연결된 항목 비율이다. PASS 비율, 준수율, 인증 점수 또는 인증 가능성 예측이 아니다. Evidence Readiness는 위 상태의 건수 분포로만 표시한다. `fixtures/policy/isms-readiness-golden.json`은 계산과 추적 Contract용 비권위 제안 Mapping이며, 공식 Mapping 승인을 의미하지 않는다.

## Rule 지원 Coverage 보고 용어

다음은 보고 용어이며 Domain Enum이나 Rule lifecycle status가 아니다.

- `Defined`: Rule metadata와 Source 근거가 fixture/registry에 정의됨
- `Governance-ready`: 승인 Source Reference/version/locator, Mapping, scope 또는 limitation, requirement/severity/evaluation type, Rule version/approval snapshot, B→C fixture가 Area B Gate를 통과함
- `Assessment-executable`: Area C의 실제 Resource × Rule 판정 경로 연결이 확인됨
- `Remediation/deployable`: Area D의 선택 Finding → Patch/PR/Plan/승인/Apply/Post-Deploy 경로가 확인됨

Area B는 앞의 두 수준만 단독으로 주장할 수 있다. metadata-only Rule을 뒤의 두 수준으로 집계하지 않는다. 현재 Resource별 수치는 `fixtures/rules/governance-coverage.json`에 고정하며 C/D 구현이 연결될 때 해당 Owner의 Contract Test 근거로만 상향한다.

## Artifact Reference

Backend 내부 Artifact port는 S3 위치 대신 content digest를 전달한다.

```json
{
  "content_digest": "sha256:<64-lowercase-hex>"
}
```

Digest는 raw bytes의 SHA-256이며 S3 adapter만 이를 `sha256/<hex>` object key로 변환한다. 새 object는 `If-None-Match: *` 조건으로 작성해 overwrite를 금지한다. 같은 bytes의 재시도는 기존 object를 읽어 digest가 일치할 때만 idempotent success이며, 다른 bytes가 있으면 collision으로 거부한다. 정확한 실행 정본은 `apps.backend.repositories.ArtifactReference`와 `ArtifactStore`다.

이 내부 reference는 공개 Report API 응답을 확정하지 않는다. Bucket 이름, S3 key, URL을 외부 Contract에 고정하지 않으며 presigned URL과 artifact-type prefix는 Open Decision이다.

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
