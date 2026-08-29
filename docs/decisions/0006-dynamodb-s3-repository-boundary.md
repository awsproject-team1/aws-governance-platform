# DynamoDB and S3 Repository Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #23](https://github.com/awsproject-team1/aws-governance-platform/issues/23)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

Backend는 공통 DynamoDB·S3 접근을 소유하지만, 저장소에는 application port, optimistic concurrency 동작, immutable artifact 쓰기 규칙, provider-error 경계가 없다. 지금 table 이름, bucket 이름, index, retention, public S3 reference를 정하면 아직 확정되지 않은 infrastructure·product contract를 고정하게 된다.

## Decision

- AWS-independent Job repository와 artifact-store port를 정의한다. Domain/application 호출자는 Job model, opaque content-digest reference, bytes, provider-neutral exception만 주고받는다.
- 구체 adapter에 DynamoDB table-like client와 S3 client + bucket 이름을 주입한다. 환경변수에서 resource를 찾거나 adapter 안에서 SDK client를 생성하지 않는다.
- 이 slice에서 adapter는 `boto3`나 `botocore`를 직접 import하지 않는다. 이후 Lambda composition root는 runtime 사본에 조용히 의존하지 말고 정확한 SDK version을 package해야 하며, 그 version은 해당 consumer가 존재할 때 선택한다.
- Job item 하나를 `job_id` key로 저장한다. `job_type`, `status`, `current_step`, `requested_by`, `revision`, 선택적 write-once Domain ID, 선택적 sanitized error detail을 영속한다.
- revision `0`과 `job_id`가 존재하지 않는다는 condition으로 생성한다. 실패한 create condition은 provider-neutral duplicate error로 변환한다.
- `job_id`로 consistent read하여 Job을 읽는다. 부재는 `None`으로 반환하고, 잘못된 저장 데이터는 provider-neutral data error로 거부한다.
- update 전에 현재 Job을 읽고 검증한 뒤, 후보가 승인된 lifecycle policy가 만들어낼 상태와 같기를 요구한다. 이는 직접 model 생성으로 `requested_by`, `job_type`, write-once Domain ID, terminal 상태를 바꾸는 것을 막는다.
- 저장된 `revision`이 호출자의 expected revision과 같을 때만 전체 Job item을 교체한다. 후보 revision이 `expected_revision + 1`과 같기를 요구한다. 실패한 condition은 provider-neutral revision conflict로 변환한다.
- 이 slice에서는 table 이름, 환경변수 이름, GSI, listing, pagination, TTL, timestamp, retry policy, migration 자동화를 추가하지 않는다.
- artifact bytes는 lowercase SHA-256으로 주소화한다. port reference는 `sha256:<64 lowercase hexadecimal characters>`이며 bucket이나 S3 URL을 노출하지 않는다.
- digest를 내부 S3 key `sha256/<hex digest>`로 매핑한다. raw bytes를 `If-None-Match: *`로 써서 기존 key를 덮어쓰지 못하게 한다.
- precondition 실패 시 기존 bytes를 읽어 hash한다. 같은 bytes면 idempotent success, 같은 digest key에 다른 bytes면 collision error다. 어느 경우도 덮어쓰지 않는다.
- provider 실패는 response body, request ID, resource 이름, exception message를 복사하지 않고 고정된 provider-neutral exception으로 변환한다.
- 이 slice에서는 artifact-type prefix, presigned URL, multipart 동작, retention, encryption 구성, lifecycle rule, public artifact-reference 필드를 추가하지 않는다.

## Consequences

- Domain·handler 코드는 AWS 없이 test할 수 있고 DynamoDB map, S3 URL, SDK exception에 의존할 수 없다.
- DynamoDB condition expression은 lifecycle 검증 뒤 두 번째 concurrency 검사를 제공한다.
- S3 쓰기는 bucket versioning이 없어도 immutable하며 동일 bytes 반복 쓰기는 idempotent하다.
- idempotent duplicate 확인은 `s3:PutObject` 외에 `s3:GetObject`를 요구한다.
- Infrastructure는 여전히 table, bucket, IAM policy, SDK composition, encryption, retention, 최종 resource naming을 제공해야 한다.

## Alternatives considered

- **무조건 DynamoDB put/update:** lost update와 duplicate 교체를 허용하므로 기각.
- **Boto3 response·exception을 port로 노출:** application 로직과 test를 AWS SDK 세부에 결합시키므로 기각.
- **mutable semantic artifact key 사용:** retry나 이후 실행이 과거 evidence를 덮어쓸 수 있으므로 기각.
- **모든 S3 precondition 실패를 success로 취급:** digest key의 예상치 못한 object를 idempotency 수용 전에 검사해야 하므로 기각.
- **지금 artifact-type prefix·presigned URL 추가:** 접근 패턴과 public API contract가 미확정이므로 보류.
- **Lambda 제공 AWS SDK에 의존:** 이후 product package에는 SDK 동작이 재현 가능해야 하므로 기각. 이 slice는 SDK를 import하지 않으므로 지금 pin을 추가하지 않는다.

## References

- [DynamoDB optimistic locking](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)
- [Amazon S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
- [AWS Lambda Python ZIP packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Backend Lambda bootstrap](0003-backend-lambda-bootstrap.md)
- [System design](../DESIGN.md)
