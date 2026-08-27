# DynamoDB and S3 Repository Boundary

- **Status:** Accepted
- **Date:** 2026-08-26
- **Related Issue/PR/Notion:** [GitHub Issue #23](https://github.com/awsproject-team1/aws-governance-platform/issues/23)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

The Backend owns common DynamoDB and S3 access, but the repository has no application ports, optimistic concurrency behavior, immutable artifact write rule, or provider-error boundary. Choosing table names, bucket names, indexes, retention, or public S3 references now would freeze unresolved infrastructure and product contracts.

## Decision

- Define AWS-independent Job repository and artifact-store ports. Domain/application callers exchange Job models, opaque content-digest references, bytes, and provider-neutral exceptions only.
- Inject a DynamoDB table-like client and an S3 client plus bucket name into concrete adapters. Do not discover resources from environment variables or create SDK clients inside adapters.
- Keep adapters free of direct `boto3` or `botocore` imports in this slice. The future Lambda composition root must package an exact SDK version rather than depend silently on the runtime copy; its version is selected when that consumer exists.
- Store one Job item keyed by `job_id`. Persist `job_type`, `status`, `current_step`, `requested_by`, `revision`, optional write-once Domain IDs, and optional sanitized error detail.
- Create with revision `0` and a condition that `job_id` does not exist. Translate a failed create condition to a provider-neutral duplicate error.
- Read a Job by `job_id` with a consistent read. Return absence as `None`; reject malformed stored data with a provider-neutral data error.
- Before an update, read and validate the current Job, then require the candidate to equal the state that the approved lifecycle policy would produce. This prevents direct model construction from changing `requested_by`, `job_type`, write-once Domain IDs, or terminal state.
- Replace the complete Job item only when stored `revision` equals the caller's expected revision. Require the candidate revision to equal `expected_revision + 1`. Translate a failed condition to a provider-neutral revision conflict.
- Do not add table names, environment-variable names, GSIs, listing, pagination, TTL, timestamps, retry policy, or migration automation in this slice.
- Address artifact bytes by lowercase SHA-256. The port reference is `sha256:<64 lowercase hexadecimal characters>` and does not expose a bucket or S3 URL.
- Map the digest to the internal S3 key `sha256/<hex digest>`. Write raw bytes with `If-None-Match: *` so an existing key cannot be overwritten.
- On a precondition failure, read and hash the existing bytes. Equal bytes make the operation idempotent; different bytes at the same digest key raise a collision error. Never overwrite either case.
- Translate provider failures to fixed provider-neutral exceptions without copying response bodies, request IDs, resource names, or exception messages.
- Do not add artifact-type prefixes, presigned URLs, multipart behavior, retention, encryption configuration, lifecycle rules, or public artifact-reference fields in this slice.

## Consequences

- Domain and handler code can be tested without AWS and cannot depend on DynamoDB maps, S3 URLs, or SDK exceptions.
- DynamoDB condition expressions provide a second concurrency check after lifecycle validation.
- S3 writes are immutable even when bucket versioning is absent, and repeated writes of identical bytes are idempotent.
- Idempotent duplicate confirmation requires `s3:GetObject` in addition to `s3:PutObject`.
- Infrastructure still must supply the table, bucket, IAM policy, SDK composition, encryption, retention, and final resource naming.

## Alternatives considered

- **Unconditional DynamoDB put/update:** Rejected because it permits lost updates and duplicate replacement.
- **Expose Boto3 responses and exceptions through ports:** Rejected because it couples application logic and tests to AWS SDK details.
- **Use mutable semantic artifact keys:** Rejected because retries or later runs could overwrite historical evidence.
- **Treat every S3 precondition failure as success:** Rejected because an unexpected object at a digest key must be checked before accepting idempotency.
- **Add artifact-type prefixes and presigned URLs now:** Deferred because their access patterns and public API contract are unresolved.
- **Rely on the Lambda-provided AWS SDK:** Rejected for the future product package because SDK behavior must be reproducible; no pin is added now because this slice imports no SDK.

## References

- [DynamoDB optimistic locking](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_OptimisticLocking.html)
- [Amazon S3 conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
- [AWS Lambda Python ZIP packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Backend Lambda bootstrap](0003-backend-lambda-bootstrap.md)
- [System design](../DESIGN.md)
