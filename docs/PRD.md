# Product Requirements Document

## Product Overview

Cloud Governance & Compliance Agent는 기업의 실제 운영 Terraform/IaC와 조직 정책을 AI Agent가 해석해 Governance/Compliance를 평가하고, Finding에 대한 최소 Terraform 개선안과 Pull Request를 생성하며, 배포 전·후 AWS Actual State까지 검증하는 고객사 내부 배포형 플랫폼이다.

핵심 원칙은 Customer-Deployed, Actual IaC First, Deterministic Boundary + LLM Reasoning, Structured Contract, Read-Only Agent, Human Approval, Auditability다.

## Problem Statement

기업의 AWS Governance 기준은 사내 정책, AWS 권장사항, 보안·Compliance Framework에 분산되어 있다. 이를 실제 IaC 및 현재 AWS 상태에 대조하고, 판정 근거와 버전을 보존하며, 안전한 개선과 재검증까지 연결하는 과정은 수작업 비용과 일관성 문제가 크다.

이 제품은 LLM이 임의의 정책 기준을 만들게 하지 않는다. Code와 Schema가 평가 대상·Rule·상태 전이를 고정하고, LLM은 고정된 경계 안에서 의미 해석과 개선안 생성을 담당한다.

## Target Customer

다음 특성을 가진 기업을 대상으로 한다.

- 자체 보안·Cloud Governance 정책을 보유한다.
- AWS를 Terraform 기반 IaC로 운영한다.
- 사내 정책과 여러 외부 보안·Compliance 기준을 IaC 및 실제 AWS 상태와 함께 평가하려 한다.
- 고객 내부 전문가가 직접 운영하는 Self-Managed 방식 또는 선택적인 Provider Expert Assistance를 사용할 수 있다.

Provider Expert Assistance는 Policy Mapping과 Rule/Finding/Remediation 방향 검토를 지원한다. 최종 Rule 승인, Remediation 승인, Apply 결정은 고객 책임이며 Provider의 고객 AWS Account 상시 접근을 전제하지 않는다.

## 사용자와 Role

하나의 React Application과 Cognito User Pool을 사용하고 Backend가 JWT Group/Role을 검증한다.

- `Admin`: User 기능, Policy Source/Rule/Policy Profile 관리, GitHub 연결, 사용자·권한 및 배포·감사 설정 관리
- `User`: Policy Q&A, IaC Assessment 요청, Finding/Report 확인, Remediation 요청, 평가 이력 조회

Frontend에서 메뉴를 숨기는 것만으로 권한을 통제하지 않으며 Backend/API에서 RBAC를 다시 검증한다. MVP는 고객사별 독립 배포이므로 `tenant_id` 기반 SaaS Multi-Tenant 격리를 요구하지 않는다.

## Goals

- 실제 고객 IaC Repository와 Commit SHA를 기준으로 재현 가능한 Assessment를 수행한다.
- Policy Profile과 Effective Rule Set을 통해 평가 기준을 명시적으로 고정한다.
- `Resource × Rule` 단위 결과와 FAIL Finding을 근거·Severity·Version과 함께 보존한다.
- 선택된 Finding을 최소 Terraform Patch/Diff, PR, 검증, 승인, Apply, 재평가까지 연결한다.
- Agent의 AWS Write 권한을 제거하고 사람의 명시적 승인에 변경 권한을 묶는다.
- Source별 Score/Coverage와 전체 상태 요약을 감사 가능하게 제공한다.

## Non-Goals

- LLM이 Governance 기준이나 Threshold를 즉석에서 창작하는 범용 Rule Engine
- Agent Runtime의 직접 `terraform apply` 또는 AWS Resource 변경
- 모든 AWS Resource, Region, Compliance Framework의 완전 지원
- Cross-Source 단일 최종 Status/Severity/Overall Score 생성
- 고객 Terraform State의 소유·대체·자동 Import
- 자연어만으로 신규 Infrastructure Desired Model 생성

## MVP Scope

- GitHub App 기반 승인 Repository 연결과 IaC Snapshot 조회
- 고객 정책 저장·검색, Policy Q&A, 허용된 외부 공식 근거 검색
- Global/Customer Rule, Rule 승인, Policy Profile, Effective Rule Set, Admin Settings Snapshot
- IaC 중심 Initial Assessment, AssessmentResult, Finding, Report, Source별 Score/Coverage
- Finding 1개당 Remediation 1개와 최소 Terraform Patch/Diff
- Branch/Commit/PR 및 Terraform CI Validation
- 최신 IaC와 AWS Actual State를 사용하는 Pre-Deploy Validation 및 `terraform plan`
- `commit_sha + plan_hash`에 바인딩된 Human Approval
- GitHub Actions OIDC와 TerraformDeploymentRole을 통한 Apply
- Post-Deploy Assessment와 Before/After 검증
- Cognito Admin/User RBAC, Read-Only Agent, Structured Output Validation, Audit/Observability

### Initial Vertical Slice

최초 구현과 최종 데모는 지원 폭보다 Closed-loop 완주를 우선해 S3 Public Access Block 문제 하나로 제한한다. 이 절이 고정하는 것은 제품 목표와 architecture boundary이며 실행 Rule/Control 식별자, lifecycle, Enum 또는 wire Contract가 아니다.

- Governed Resource semantic: Terraform `aws_s3_bucket`과 Public Access Block companion
- Demo fixture: 취약한 S3 Bucket instance 1개 계획
- Rule candidate: S3 Public Access Block 네 설정을 모두 활성화해야 한다는 Global requirement
- Proposed planning labels: `GLOBAL-S3-PAB-001`, `s3.public_access_block.enabled`
- Remediation intent: companion resource 추가 또는 필요한 설정만 변경하는 최소 Terraform Patch

Proposed label은 Shared Contract/Registry에 예약되지 않았고 ACTIVE Rule이 아니다. Source revision/version, 정확한 locator, retrieval timestamp, immutable content hash와 승인 대상 semantic hash가 Human Approval에 binding된 뒤에만 실행 Rule로 등록할 수 있다. 정확한 Source Reference와 Approval field는 구현 시 Producer/Consumer review로 확정한다.

`aws_s3_bucket_public_access_block`은 별도 평가 대상 Resource가 아니라 S3 Bucket Rule candidate의 companion Terraform construct이자 Remediation target이다. Security Group, IAM, VPC, CloudTrail과 추가 Rule은 첫 Closed-loop가 통합 검증된 후 확장한다.

## 주요 User Flow

### Policy Q&A

사용자가 정책을 질문하면 Policy Agent가 사내 Policy Knowledge와 필요한 공식 근거를 조회해 답변한다. Terraform 또는 AWS Resource 평가는 수행하지 않는다.

### Assessment

Admin이 관리한 Policy Profile과 고객 Repository를 User가 선택한다. 시스템은 Phase에 맞는 Effective Rule Set과 Scope를 결정하고 IaC를 평가하여 Rule별 결과, Finding, Report, Source별 Score/Coverage를 생성한다.

최초 Slice의 Initial Assessment는 지정 Commit의 Terraform 표현을 평가한다. 정상적으로 평가된 Governance 위반과 Parser/Tool/Agent 실행 오류는 서로 다른 상태 축으로 보존하며, 실행 오류를 Governance 위반으로 변환하지 않는다. 정확한 field 이름과 Enum spelling은 Shared Contract 구현 시 확정한다.

### Remediation과 Deployment

User가 Finding 하나를 선택하면 시스템이 최소 Patch/Diff와 영향 설명을 생성하고 고객 Repository에 PR을 만든다. CI와 Pre-Deploy 검증 및 Plan이 성공한 뒤 Human Approval을 받고, GitHub Actions가 Apply한다. 이후 최신 IaC와 AWS 상태를 다시 확인하고 새 Post-Deploy Assessment를 생성한다.

## Functional Requirements

- 고객이 승인한 Repository만 조회·변경 제안 대상으로 사용해야 한다.
- 평가 요청은 Repository, Policy Profile, Scope를 구조화된 입력으로 받아야 한다.
- 장시간 작업은 Job으로 추적하고 현재 상태와 단계를 조회할 수 있어야 한다.
- Initial, Pre-Deploy, Post-Deploy 평가를 동일 Assessment 개념과 `phase`로 구분해야 한다.
- 실행 오류와 Governance `FAIL`을 서로 다른 상태 축으로 관리해야 한다.
- FAIL Rule Evaluation은 Source별 Finding으로 유지해야 한다.
- 같은 Resource × Control의 결과는 비교 표시할 수 있지만 하나의 최종 판정으로 병합하지 않아야 한다.
- 미확정 Scope/Threshold는 추측하지 않고 Review 또는 Manual 상태로 남겨야 한다.
- Remediation은 사용자가 선택한 Finding에 대해서만 생성해야 한다.
- Apply 전 승인 대상 Commit과 Plan을 고정하고 Apply 직전에 동일성을 재검증해야 한다.
- 과거 Assessment와 Report를 덮어쓰지 않아야 한다.

## Non-Functional Requirements

- Auditability: 요청, Rule Version, Evidence, 판정, 승인, 배포 결과를 연결해 추적한다.
- Reproducibility: Commit/IaC Snapshot, Policy Profile Version, Effective Rule Set, Admin Settings Snapshot, Phase, Scoring Version을 보존한다.
- Reliability: 비동기 Job, 오류 상태 분리, 승인 기반 중단·재개, Post-Deploy 검증을 지원한다.
- Security: 최소 권한, RBAC, OIDC, Structured Validation, CI/Plan/Approval의 계층적 방어를 적용한다.
- Cost: 관리형 서비스를 우선하고 실제 AWS 조회와 고비용 Resource 사용을 필요한 시점으로 제한한다.
- Observability: 공통 Identifier로 API, Workflow, Agent, Tool, Assessment, Deployment를 상관 분석할 수 있어야 한다.

구체 성능 목표, 데이터 보존기간, 가용성 SLO는 Open Decision이다.

## Security Principles

- Agent Runtime은 고객 Workload에 Read-Only 권한만 가진다.
- 실제 Apply는 Human Approval 이후 GitHub Actions가 OIDC 임시 자격증명으로 수행한다.
- TerraformPlanRole과 TerraformDeploymentRole을 분리한다.
- Cognito 인증과 Backend RBAC를 사용한다.
- LLM 출력과 검색 문서는 신뢰 경계 밖의 입력으로 취급한다.
- Secret과 장기 AWS Access Key를 Repository나 GitHub Actions에 저장하지 않는다.

## Deployment Model

MVP는 공급자가 버전을 고정한 CloudFormation 기반 Connected Customer-Deployed 방식이다. 고객은 Change Set을 검토한 뒤 자신의 AWS Account에 직접 설치한다. 공식 MVP Region은 `us-east-1`이다.

Backend와 Agent Runtime은 고객의 기존 VPC/Subnet에 연결하지 않는 서버리스/관리형 구성을 기본으로 한다. Marketplace Quick Launch, Customer-Mirrored/Offline 설치, Existing VPC Integration은 확장 범위다.

## Out of Scope

- 파일 업로드 기반 가상 Terraform 분석을 핵심 경로로 제공
- 자동 Terraform 역생성, State Import, Console 변경 자동 동기화
- Batch Remediation과 다단계·다수 승인자 Workflow
- 실시간 SSE/WebSocket 상태 Push
- Private API/DB/On-Prem 직접 연결과 VPN/Direct Connect 통합
- 서비스 전용 VPC/Subnet 자동 생성
- 복잡한 Cross-Account SaaS Multi-Tenant 운영
- 공식 인증기관 또는 전체 Framework 인증의 대체

## Success Criteria

최초 S3 Slice에서 다음 E2E 흐름이 실제로 동작해야 한다.

```text
Public Access Block이 없거나 불완전한 S3 Terraform
  → 승인된 S3 Public Access Block Rule로 Initial Assessment 위반 확인
  → Rule Finding / Report
  → aws_s3_bucket_public_access_block 최소 Terraform Remediation
  → Customer Remediation PR / CI 성공
  → Pre-Deploy Validation / Plan
  → Human Approval
  → GitHub Actions Apply
  → Post-Deploy IaC 준수 확인
  → AWS Actual Public Access Block 관찰 일치 확인
```

최종 IaC 준수 결과와 Actual verification은 새 Assessment/Deployment Artifact로 기록하고 과거 위반과 Finding을 덮어쓰지 않는다. Actual 불일치 또는 수집 오류는 IaC Governance 판정을 바꾸지 않지만 Closed-loop 완료를 차단한다. 정확한 result/verification Enum spelling은 Shared Contract 구현 전까지 Open Decision이다. 단순 Policy Q&A나 Mock 연결만으로는 MVP 성공으로 보지 않는다.

## Open Decisions

- 최초 S3 Slice 이후 확장할 Resource와 Rule 우선순위
- Agent Model Routing 기준
- Policy/Assessment/Remediation Skill 구현 방식
- 결정론적 Check Registry로 분리할 추가 Rule 범위
- 구체 SLO와 데이터 보존기간

## 근거 문서

- [Notion — 최종 계획서](https://app.notion.com/p/3c66e3d0b32581048803f9c4ac214a10)
- [Notion — 01. 프로젝트 개요 · 범위 · 사용자 구조](https://app.notion.com/p/3c66e3d0b3258108807fd0feba897264)
- [Notion — 07. MVP · 구현 우선순위 · 미결정사항](https://app.notion.com/p/3c66e3d0b3258140a9f3c1b85045f60e)
