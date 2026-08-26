# Initial S3 Public Access Block Slice

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #13](https://github.com/awsproject-team1/aws-governance-platform/issues/13)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The MVP succeeds only when one real customer-IaC finding completes Assessment, remediation, approval, apply, and post-deploy verification. Supporting several resources or rules before proving that loop would increase contract and integration risk without proving the product outcome.

## Decision

- The initial governed resource type is `aws_s3_bucket`, with one vulnerable bucket fixture in the demo.
- The first approved rule is `GLOBAL-S3-PAB-001` version 1 for control `s3.public_access_block.enabled`.
- The rule is a `HIGH` severity, Global, IAC evaluation requiring all four S3 Public Access Block properties to be explicitly `true`.
- A missing or incomplete `aws_s3_bucket_public_access_block` produces FAIL after successful evaluation.
- Remediation adds the companion resource or changes only missing/false properties through a minimal Terraform patch.
- The customer remediation path is Finding → customer PR → CI/plan → human approval → GitHub Actions apply → new Post-Deploy Assessment PASS.
- AWS Actual Public Access Block values are owned by Deployment as a referenced verification artifact; closed-loop success requires Post-Deploy IAC `PASS/SUCCESS` and verification `MATCHED`.
- A/B/C/D delivery progress uses GitHub Native Sub-issue relationships, including a final integration-validation Sub-issue so 100% progress means Parent completion.
- Platform development PRs are created after local validation, reviewed and merged by humans, and the Sub-issue is manually closed after merge to `dev`. The next Sub-issue starts after that merge.
- The agent may create Issues, branches, implementation, tests, commits, pushes, and PRs only when requested. It never performs merge.

## Consequences

- The first vertical slice optimizes for closed-loop completion rather than resource coverage.
- Historical FAIL assessments, findings, and reports remain immutable; Post-Deploy PASS creates new records.
- Security Group, IAM, VPC, CloudTrail, additional S3 rules, backend framework, frontend stack, and generic schema generation remain outside this decision.
- B, C, D, and Shared Contract human owners still require explicit team assignment; this ADR does not assign people without consent.
- ADR 0001 must be integrated before or with this ADR because this branch depends on the Python bootstrap commit.

## Alternatives considered

- **Multiple resources and rules in parallel:** Rejected because it increases integration breadth before the first closed loop works.
- **Security Group ingress as the first rule:** Rejected because safe demo networking and source CIDR semantics create more policy variables than S3 Public Access Block.
- **HYBRID evaluation for the first rule:** Rejected because the current `INITIAL` phase selects IAC rules. AWS Actual is retained as separate verification evidence instead.
- **Agent direct apply:** Rejected because it violates the Read-Only Agent and Human Approval boundary.
- **Automatic issue closure:** Deferred; manual close after `dev` merge is simpler and keeps humans responsible for delivery state.
