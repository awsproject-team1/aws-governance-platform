# Initial S3 Public Access Block Slice

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #13](https://github.com/awsproject-team1/aws-governance-platform/issues/13)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

MVP는 실제 고객 IaC finding 하나가 Assessment, remediation, approval, apply, post-deploy verification까지 완주할 때만 성공한다. 그 loop를 증명하기 전에 여러 resource나 rule을 지원하면 product 성과를 증명하지 못한 채 contract·integration 리스크만 커진다.

## Decision

- 이 ADR의 승인 범위는 vertical-slice architecture와 그 safety 경계다. 실행 가능한 Rule registry record, wire schema, lifecycle enum, ACTIVE Rule을 승인하지 않는다.
- 초기 governed resource type은 `aws_s3_bucket`이며, demo용 취약한 bucket fixture 하나를 계획한다.
- 첫 Rule candidate는 S3 Public Access Block을 대상으로 한다. `GLOBAL-S3-PAB-001`과 `s3.public_access_block.enabled`은 proposed planning label이며 예약되거나 active한 registry 식별자가 아니다.
- 의도한 criterion은 companion `aws_s3_bucket_public_access_block`과 네 Public Access Block 속성이 모두 명시적으로 활성화되는 것이다. 정확한 Rule version, severity, status, result 어휘는 Shared Contract 결정으로 남는다.
- mutable AWS 문서 URL은 discovery 입력일 뿐이다. Activation은 captured source revision/version, 정확한 locator, retrieval timestamp, immutable artifact와 content hash, 그리고 Rule identity/version과 semantic content hash에 binding된 Human Approval을 요구한다.
- 정확한 Source Reference와 Rule Approval 필드 이름·값은 evidence capture와 Shared Contract 구현 전까지 Open이다. candidate는 그 record가 존재하고 검토되기 전에 ACTIVE로 취급해서는 안 된다.
- Remediation은 companion resource를 추가하거나 누락/비활성 속성만 minimal Terraform patch로 변경하는 것으로 제한한다.
- 고객 remediation 경로는 Finding → 고객 PR → CI/plan → human approval → GitHub Actions apply → 새 Post-Deploy Assessment다.
- AWS Actual Public Access Block 값은 Deployment가 별도의 referenced verification evidence로 소유한다. Closed-loop 성공은 준수하는 Post-Deploy IaC evaluation과 일치하는 AWS Actual observation을 모두 요구하며, 정확한 status·필드 이름은 Open이다.
- A/B/C/D 진행은 GitHub Native Sub-issue 관계를 사용하며, 100% 진행이 Parent 완료를 뜻하도록 마지막 integration-validation Sub-issue를 포함한다.
- Platform 개발 PR은 로컬 검증 후 생성하고 사람이 review·merge 한다. 기본 `dev` branch를 대상으로 하는 완료된 Sub-issue 또는 Bug PR은 `Closes #N`을 사용하며, merge 후 GitHub가 Agent close API 호출 없이 연결된 Issue를 닫는다. 부분 PR은 `Refs #N`을 사용하고 Parent Issue는 종합 검증 후 사람이 닫는다. 다음 Sub-issue는 자동 종료 확인 후 시작한다.
- Agent는 요청받은 경우에만 Issue, branch, 구현, test, commit, push, PR을 만든다. merge는 절대 수행하지 않는다.

> 참고: 이 ADR의 Sub-issue/Parent Issue 기반 진행 서술은 2026-08-26 결정 당시 기록이다. 이후 팀은 v3에서 GitHub Issue를 사용하지 않기로 했다(Collaboration v3, AGENTS/CONTRIBUTING 참고). 이 ADR은 과거 이력으로 원문 결정을 보존한다.

## Consequences

- 첫 vertical slice는 resource coverage보다 closed-loop 완료에 최적화한다.
- 과거 noncompliant assessment, finding, report는 immutable로 남고, 준수하는 Post-Deploy 결과는 새 record를 만든다.
- Rule candidate가 evaluation 정본이 되려면 source evidence capture, Rule activation approval, 실행 가능한 Shared Contract type, fixture, Contract Test가 필요하다.
- Security Group, IAM, VPC, CloudTrail, 추가 S3 rule, backend framework, frontend stack, generic schema 생성은 이 결정 밖이다.
- B, C, D, Shared Contract의 사람 owner는 명시적 팀 배정이 필요하며, 이 ADR은 동의 없이 사람을 배정하지 않는다.
- 이 branch가 Python bootstrap commit에 의존하므로 ADR 0001은 이 ADR 이전 또는 함께 integrate되어야 한다.

## Alternatives considered

- **여러 resource와 rule을 병렬로:** 첫 closed loop가 동작하기 전에 integration 범위를 넓히므로 기각.
- **Security Group ingress를 첫 rule로:** 안전한 demo networking과 source CIDR 의미가 S3 Public Access Block보다 policy 변수를 더 많이 만들므로 기각.
- **첫 rule에 HYBRID evaluation:** 의도한 초기 assessment가 IaC 기반이므로 기각. AWS Actual은 별도 verification evidence로 유지한다.
- **mutable URL만으로 Rule 활성화:** approval을 정확한 source revision, locator, semantic content hash에 binding할 수 없으므로 기각.
- **Agent 직접 apply:** Read-Only Agent와 Human Approval 경계를 위반하므로 기각.
- **Agent 또는 custom-workflow의 issue 종료:** 기본 `dev` branch가 이미 GitHub native closing keyword를 지원하므로 기각. 사람이 review·merge하고 GitHub가 `Closes #N`으로 연결된 완료 Sub-issue/Bug를 닫으며, Agent는 Issue close API를 호출하지 않고 Parent Issue는 종합 검증 후 사람이 닫는다.
