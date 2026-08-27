# Governance Document Ingestion Boundary

- **Status:** Accepted
- **Date:** 2026-08-27
- **Related Issue/PR/Notion:** [GitHub Issue #3](https://github.com/awsproject-team1/aws-governance-platform/issues/3), [GitHub Issue #14](https://github.com/awsproject-team1/aws-governance-platform/issues/14)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

Area B must turn customer policy documents into reproducible evidence for Rule Candidates and Policy Q&A. Those documents arrive in formats the platform does not control (MD, TXT, HTML, DOCX, PDF, XLSX) and are untrusted input from outside the trust boundary.

Two decisions follow from that and outlive this change. First, parsing untrusted uploaded bytes is a trust-boundary activity, so where format knowledge lives and what runs before a parser sees a byte must be fixed. Second, ADR-0001 deliberately kept the repository at one development dependency and deferred application dependencies until the first executable slice; the PDF path is that slice, and it cannot be implemented from the standard library alone because a text-layer PDF requires object and object-stream decoding.

## Decision

- Fix the ingestion boundary as `upload validation -> format loader -> canonical document -> deterministic segmentation -> frozen document -> knowledge index`. Confine all format knowledge to the loader stage; every later stage operates on the format-independent canonical representation.
- Run upload validation before any parser: extension allowlist, real file-signature verification, macro/encrypted/zip-bomb rejection, and filename regeneration. Unvalidated bytes must never reach a parser.
- Freeze evidence at `document_version` granularity and include parser and structure-profile identity in the freeze basis, so a parser change cannot silently change existing evidence.
- Fail explicitly when a document has no deterministic structure profile, and branch a scanned PDF to an OCR-required state. Never return zero items as if extraction succeeded.
- Adopt `pypdf` as the first Governance runtime dependency, pinned exactly, in `packages/governance/requirements.txt`. Keep it out of `requirements-dev.txt`: it is product runtime code, not a development tool.
- Keep per-deployment-unit runtime manifests, matching `apps/backend/requirements.txt`. Do not introduce a shared application dependency file or a transitive lock strategy in this change.
- Do not adopt an OCR engine, a managed retrieval vendor, or a malware scanner in this change. The malware scanner is an injection point; when absent, its absence is recorded in `extraction_warnings` rather than passing silently.

## Consequences

- Governance runtime code now has one external dependency. CI installs `packages/governance/requirements.txt` alongside the existing development and Backend manifests.
- `pypdf` version increases are reviewed as a security-relevant change, because it parses untrusted customer input.
- Adding a new document format means adding a loader and a structure profile only; no later stage changes.
- Scanned PDFs and profile-less documents are visibly unsupported instead of silently empty, which keeps missing coverage detectable.
- A malware scanner and parser execution isolation are still required before production deployment. Until then the warning trail is the only record.
- The number of runtime dependencies is expected to grow, so a transitive lock strategy must be revisited before the first customer deployment.

## Alternatives considered

- **Send uploaded files directly to the LLM:** Rejected. It makes evidence non-reproducible, gives no stable locator for a Finding's `source_reference`, and hands untrusted document content an unmediated path into the model.
- **Standard-library-only PDF handling:** Rejected. A text-layer PDF needs object and object-stream decoding; a hand-rolled decoder would be more security-sensitive code to own than a pinned, widely reviewed library.
- **Put `pypdf` in `requirements-dev.txt`:** Rejected. It would misrepresent product runtime code as a development tool and would omit the dependency from any deployment package built from the manifests.
- **One shared application requirements file:** Deferred. `apps/backend` and `packages/governance` deploy to different runtimes, and merging them now would pin unrelated dependency sets together.
- **Absorb XLSX into the general heading profile:** Rejected. A control matrix has row identity, not heading structure; forcing it into heading segmentation would lose the row-level freeze granularity that mapping evidence needs.

## References

- [Python Bootstrap Toolchain](0001-python-bootstrap.md)
- [Initial S3 Public Access Block Slice](0002-initial-s3-public-access-block-slice.md)
- [Backend Lambda Bootstrap](0003-backend-lambda-bootstrap.md)
- [Technical design](../DESIGN.md)
- [Data contracts](../CONTRACTS.md)
