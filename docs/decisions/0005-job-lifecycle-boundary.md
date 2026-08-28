# Job Lifecycle and Ownership Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #22](https://github.com/awsproject-team1/aws-governance-platform/issues/22)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

public Job polling contract는 status와 step을 정의하지만 initial step, 합법적 transition, concurrency, ownership, 영속 상태를 정의하지 않는다. Backend와 workflow producer는 enum 순서, 추측한 Job type, 이후 retry 동작을 product contract로 만들지 않으면서 결정론적 최소값이 필요하다.

## Decision

- `JobResponse`는 public polling projection으로 유지하고, 영속 application 상태를 위한 별도의 immutable Backend Job 모델을 추가한다.
- Job 생성 시 호출자가 명시적 `initial_step`을 제공하도록 요구한다. `JobCurrentStep` 순서에서 기본값을 추론하지 않는다.
- `job_type`과 식별자는 opaque non-empty 문자열로 유지한다. 닫힌 Job type enum이나 식별자 형식을 도입하지 않는다.
- Job은 `QUEUED`, revision `0`, public error 없음, 내부 non-empty `requested_by` subject로 생성한다.
- 다음 transition만 허용한다:
  - `QUEUED → RUNNING | FAILED | CANCELLED`
  - `RUNNING → RUNNING | WAITING_REVIEW | WAITING_APPROVAL | COMPLETED | FAILED | CANCELLED`
  - `WAITING_REVIEW | WAITING_APPROVAL → RUNNING | FAILED | CANCELLED`
  - `COMPLETED`, `FAILED`, `CANCELLED`는 terminal.
- `RUNNING → RUNNING`은 영속 progress 갱신으로 취급한다. progress-only 갱신을 포함해 모든 성공 transition은 revision을 정확히 1 증가시킨다.
- 다음 immutable 상태를 만들기 전에 호출자의 expected revision이 현재 Job과 일치하도록 요구한다. repository는 영속화 시점에 이 검사를 원자적으로 반복한다.
- `FAILED` Job은 `ApiError`를 포함해야 한다. 다른 모든 status는 error가 없어야 한다. error는 이미 sanitized public detail이어야 하며 provider exception text를 절대 복사하지 않는다.
- `assessment_id`, `remediation_id`, `deployment_id`는 한 번만 연결할 수 있다. 연결된 ID는 변경하거나 제거할 수 없다.
- `requested_by`는 내부에만 영속한다. User는 `Principal.subject == requested_by`일 때만 Job을 읽을 수 있고, Admin은 모든 Job을 읽을 수 있다. action-level `READ_JOB` authorization은 별도 전제 조건으로 남는다.
- 기존 `JobResponse` 필드만 projection 한다. `requested_by`나 `revision`을 public polling response로 노출하지 않는다.
- 이 slice에서는 retry, backoff, resume-from-terminal 동작, timestamp, listing, pagination, retention, TTL, schema-version 필드를 추가하지 않는다.

## Consequences

- 동시 workflow writer는 서로를 조용히 덮어쓰지 않고 실패한다.
- Workflow 코드는 실제 initial step을 선택하고 모든 transition에 expected revision을 제공해야 한다.
- Job ownership은 `job_id` 소유나 action-level RBAC만으로 추론할 수 없다.
- 내부 ownership·concurrency 필드가 `JobResponse`에 들어가지 않으므로 public response 호환성이 유지된다.
- 최소 matrix를 넘는 domain-specific lifecycle 규칙은 이후 contract 결정을 요구한다.

## Alternatives considered

- **모든 Job을 `LOAD_IAC`로 기본 설정:** enum 순서와 하나의 assessment flow가 모든 Job type을 정의하지 않으므로 기각.
- **임의 transition 허용:** terminal mutation과 review/approval 경계 건너뛰기가 가능해지므로 기각.
- **무조건 쓰기 사용:** 동시 workflow step이 갱신을 잃을 수 있으므로 기각.
- **revision과 owner를 public으로 노출:** 두 필드 모두 승인된 polling contract의 일부가 아니므로 기각.
- **Domain ID 교체 허용:** 과거 Job-to-domain 관계가 안정적으로 유지되어야 하므로 기각.
- **지금 retry·resume 동작 정의:** workflow-specific 실패 정책이 승인될 때까지 보류.

## References

- [Data and domain contracts](../CONTRACTS.md)
- [API interface](../API.md)
- [Cognito JWT and Backend RBAC boundary](0004-cognito-jwt-rbac-boundary.md)
