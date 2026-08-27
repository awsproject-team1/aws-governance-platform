# Initial S3 Public Access Block Slice

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #13](https://github.com/awsproject-team1/aws-governance-platform/issues/13)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The MVP succeeds only when one real customer-IaC finding completes Assessment, remediation, approval, apply, and post-deploy verification. Supporting several resources or rules before proving that loop would increase contract and integration risk without proving the product outcome.

## Decision

- The accepted scope of this ADR is the vertical-slice architecture and its safety boundaries. It does not approve an executable Rule registry record, wire schema, lifecycle enum, or ACTIVE Rule.
- The initial governed resource type is `aws_s3_bucket`, with one vulnerable bucket fixture planned for the demo.
- The first Rule candidate targets S3 Public Access Block. `GLOBAL-S3-PAB-001` and `s3.public_access_block.enabled` are proposed planning labels, not reserved or active registry identifiers.
- The intended criterion requires the companion `aws_s3_bucket_public_access_block` and all four Public Access Block properties to be explicitly enabled. Exact Rule version, severity, status and result vocabulary remain Shared Contract decisions.
- The mutable AWS documentation URL is discovery input only. Activation requires captured source revision/version, an exact locator, retrieval timestamp, immutable artifact and content hash, plus Human Approval bound to the Rule identity/version and semantic content hash.
- Exact Source Reference and Rule Approval field names and values remain open until evidence capture and Shared Contract implementation. The candidate must not be treated as ACTIVE before those records exist and are reviewed.
- Remediation is limited to adding the companion resource or changing only missing/disabled properties through a minimal Terraform patch.
- The customer remediation path is Finding → customer PR → CI/plan → human approval → GitHub Actions apply → new Post-Deploy Assessment.
- AWS Actual Public Access Block values are owned by Deployment as separate referenced verification evidence. Closed-loop success requires both a compliant Post-Deploy IaC evaluation and matching AWS Actual observation; exact status and field names remain open.
- A/B/C/D delivery progress uses GitHub Native Sub-issue relationships, including a final integration-validation Sub-issue so 100% progress means Parent completion.
- Platform development PRs are created after local validation and reviewed and merged by humans. A completed Sub-issue or Bug PR targeting the default `dev` branch uses `Closes #N`; GitHub closes the linked Issue after merge without an Agent close API call. Partial PRs use `Refs #N`, and Parent Issues remain human-closed after aggregate validation. The next Sub-issue starts after automatic closure is confirmed.
- The agent may create Issues, branches, implementation, tests, commits, pushes, and PRs only when requested. It never performs merge.

## Consequences

- The first vertical slice optimizes for closed-loop completion rather than resource coverage.
- Historical noncompliant assessments, findings, and reports remain immutable; a compliant Post-Deploy result creates new records.
- Source evidence capture, Rule activation approval, executable Shared Contract types, fixtures and Contract Tests are required before the Rule candidate can become an evaluation source of truth.
- Security Group, IAM, VPC, CloudTrail, additional S3 rules, backend framework, frontend stack, and generic schema generation remain outside this decision.
- B, C, D, and Shared Contract human owners still require explicit team assignment; this ADR does not assign people without consent.
- ADR 0001 must be integrated before or with this ADR because this branch depends on the Python bootstrap commit.

## Alternatives considered

- **Multiple resources and rules in parallel:** Rejected because it increases integration breadth before the first closed loop works.
- **Security Group ingress as the first rule:** Rejected because safe demo networking and source CIDR semantics create more policy variables than S3 Public Access Block.
- **HYBRID evaluation for the first rule:** Rejected because the intended initial assessment is IaC-based. AWS Actual is retained as separate verification evidence instead.
- **Activating the Rule from a mutable URL alone:** Rejected because it cannot bind approval to an exact source revision, locator and semantic content hash.
- **Agent direct apply:** Rejected because it violates the Read-Only Agent and Human Approval boundary.
- **Agent or custom-workflow issue closure:** Rejected because the default `dev` branch already supports GitHub native closing keywords. Humans still review and merge; GitHub closes completed Sub-issues and Bugs linked with `Closes #N`, while the Agent never calls the Issue close API and Parent Issues remain human-closed after aggregate validation.
