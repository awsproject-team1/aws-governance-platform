# Job Lifecycle and Ownership Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #22](https://github.com/awsproject-team1/aws-governance-platform/issues/22)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The public Job polling contract defines statuses and steps but does not define an initial step, legal transitions, concurrency, ownership, or persisted state. Backend and workflow producers need a deterministic minimum without turning enum order, a guessed Job type, or future retry behavior into a product contract.

## Decision

- Keep `JobResponse` as the public polling projection and add a separate immutable Backend Job model for persisted application state.
- Require callers to supply an explicit `initial_step` when creating a Job. Do not infer a default from `JobCurrentStep` order.
- Keep `job_type` and identifiers as opaque non-empty strings. Do not introduce a closed Job type enum or identifier format.
- Create a Job in `QUEUED` with revision `0`, no public error, and an internal non-empty `requested_by` subject.
- Allow only these transitions:
  - `QUEUED → RUNNING | FAILED | CANCELLED`
  - `RUNNING → RUNNING | WAITING_REVIEW | WAITING_APPROVAL | COMPLETED | FAILED | CANCELLED`
  - `WAITING_REVIEW | WAITING_APPROVAL → RUNNING | FAILED | CANCELLED`
  - `COMPLETED`, `FAILED`, and `CANCELLED` are terminal.
- Treat `RUNNING → RUNNING` as a persisted progress update. Every successful transition increments revision exactly once, including a progress-only update.
- Require the caller's expected revision to match the current Job before producing the next immutable state. The repository repeats the check atomically at persistence time.
- Require `FAILED` Jobs to contain an `ApiError`. All other statuses must have no error. The error must already be a sanitized public detail; provider exception text is never copied into it.
- Allow `assessment_id`, `remediation_id`, and `deployment_id` to be linked once. A linked ID cannot be changed or removed.
- Persist `requested_by` only internally. A User may read a Job only when `Principal.subject == requested_by`; an Admin may read every Job. Action-level `READ_JOB` authorization remains a separate prerequisite.
- Project only the existing `JobResponse` fields. Never expose `requested_by` or `revision` through the public polling response.
- Do not add retries, backoff, resume-from-terminal behavior, timestamps, listing, pagination, retention, TTL, or a schema-version field in this slice.

## Consequences

- Concurrent workflow writers fail instead of silently overwriting each other.
- Workflow code must choose a real initial step and provide an expected revision for every transition.
- Job ownership cannot be inferred from possession of a `job_id` or from action-level RBAC alone.
- Public response compatibility is preserved because internal ownership and concurrency fields do not enter `JobResponse`.
- Domain-specific lifecycle rules beyond the minimum matrix require a later contract decision.

## Alternatives considered

- **Default every Job to `LOAD_IAC`:** Rejected because enum order and one assessment flow do not define all Job types.
- **Allow arbitrary transitions:** Rejected because terminal mutation and skipped review/approval boundaries would be possible.
- **Use unconditional writes:** Rejected because concurrent workflow steps could lose updates.
- **Expose revision and owner publicly:** Rejected because neither field is part of the approved polling contract.
- **Allow Domain IDs to be replaced:** Rejected because historical Job-to-domain relationships must remain stable.
- **Define retry and resume behavior now:** Deferred until workflow-specific failure policy is approved.

## References

- [Data and domain contracts](../CONTRACTS.md)
- [API interface](../API.md)
- [Cognito JWT and Backend RBAC boundary](0004-cognito-jwt-rbac-boundary.md)
