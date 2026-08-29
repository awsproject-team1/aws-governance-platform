# Governance Document Ingestion Boundary

- **Status:** Accepted (RAG/Knowledge Base 검색 부분은 [ADR 0009](0009-ai-evaluator-scoring-and-rag-removal.md)가 대체)
- **Date:** 2026-08-27
- **Related Issue/PR/Notion:** [GitHub Issue #3](https://github.com/awsproject-team1/aws-governance-platform/issues/3), [GitHub Issue #14](https://github.com/awsproject-team1/aws-governance-platform/issues/14)
- **Supersedes:** None
- **Superseded by:** [ADR 0009](0009-ai-evaluator-scoring-and-rag-removal.md) — RAG/Knowledge Base 검색 계층만. 문서 수집 경계와 locator/content hash 근거 추적은 유효.

## Context / Problem

Area B는 고객 policy 문서를 Rule Candidate와 Policy Q&A를 위한 재현 가능한 evidence로 바꿔야 한다. 이 문서들은 플랫폼이 통제하지 않는 형식(MD, TXT, HTML, DOCX, PDF, XLSX)으로 들어오며 신뢰 경계 밖의 untrusted 입력이다.

여기서 이 변경보다 오래 가는 두 결정이 나온다. 첫째, untrusted 업로드 bytes를 parsing하는 것은 trust-boundary 활동이므로, 형식 지식이 어디에 있고 parser가 byte를 보기 전에 무엇이 실행되는지를 고정해야 한다. 둘째, ADR-0001은 저장소를 개발 의존성 하나로 유지하고 application 의존성을 첫 실행 가능한 slice까지 미뤘다. PDF 경로가 그 slice이며, text-layer PDF는 object와 object-stream decoding을 요구하므로 표준 라이브러리만으로는 구현할 수 없다.

## Decision

- ingestion 경계를 `upload validation -> format loader -> canonical document -> deterministic segmentation -> frozen document -> knowledge index`로 고정한다. 모든 형식 지식을 loader 단계에 가두고, 이후 모든 단계는 형식 비종속 canonical 표현으로 동작한다.
- 어떤 parser보다 먼저 upload validation을 실행한다: 확장자 allowlist, 실제 file-signature 검증, macro/encrypted/zip-bomb 거부, 파일명 재생성. 검증되지 않은 bytes가 parser에 닿아서는 안 된다.
- evidence를 `document_version` 단위로 동결하고 parser와 structure-profile 정체성을 동결 기준에 포함해, parser 변경이 조용히 기존 evidence를 바꾸지 못하게 한다.
- 문서에 결정론적 structure profile이 없으면 명시적으로 실패하고, scanned PDF는 OCR-required 상태로 분기한다. 추출이 성공한 것처럼 0개 항목을 반환하지 않는다.
- `pypdf`를 첫 Governance runtime 의존성으로 채택하고 `packages/governance/requirements.txt`에 정확히 pin한다. `requirements-dev.txt`에는 두지 않는다. 개발 도구가 아니라 product runtime 코드이기 때문이다.
- `apps/backend/requirements.txt`와 마찬가지로 배포 단위별 runtime manifest를 유지한다. 이 변경에서 공유 application 의존성 파일이나 transitive lock 전략을 도입하지 않는다.
- 이 변경에서 OCR engine, managed retrieval vendor, malware scanner를 채택하지 않는다. malware scanner는 주입 지점이며, 없을 때는 조용히 통과하지 않고 `extraction_warnings`에 부재를 기록한다.

## Consequences

- Governance runtime 코드는 이제 외부 의존성 하나를 가진다. CI는 기존 개발·Backend manifest와 함께 `packages/governance/requirements.txt`를 설치한다.
- `pypdf` 버전 상향은 untrusted 고객 입력을 parsing하므로 보안 관련 변경으로 검토한다.
- 새 문서 형식 추가는 loader와 structure profile만 추가하는 것을 뜻하며, 이후 단계는 바뀌지 않는다.
- scanned PDF와 profile 없는 문서는 조용히 비는 대신 눈에 보이게 미지원 처리되어 누락 coverage를 감지할 수 있다.
- production 배포 전에 malware scanner와 parser 실행 격리가 여전히 필요하다. 그전까지는 warning trail이 유일한 기록이다.
- runtime 의존성 수가 늘어날 것이므로 첫 고객 배포 전에 transitive lock 전략을 재검토해야 한다.

## Alternatives considered

- **업로드 파일을 LLM에 직접 전달:** 기각. evidence를 재현 불가하게 만들고, Finding의 `source_reference`에 안정적 locator를 주지 못하며, untrusted 문서 내용에 model로 가는 매개 없는 경로를 준다.
- **표준 라이브러리만으로 PDF 처리:** 기각. text-layer PDF는 object와 object-stream decoding이 필요하며, 직접 만든 decoder는 pin되고 널리 검토된 라이브러리보다 더 보안에 민감한 코드를 떠안게 된다.
- **`pypdf`를 `requirements-dev.txt`에 배치:** 기각. product runtime 코드를 개발 도구로 잘못 표현하고, manifest로 만드는 배포 package에서 의존성을 누락시킨다.
- **공유 application requirements 파일 하나:** 보류. `apps/backend`와 `packages/governance`는 다른 runtime으로 배포되며, 지금 합치면 무관한 의존성 집합을 함께 pin하게 된다.
- **XLSX를 일반 heading profile로 흡수:** 기각. control matrix는 heading 구조가 아니라 row 정체성을 가지며, heading segmentation에 강제하면 mapping evidence에 필요한 row 단위 동결 granularity를 잃는다.

## References

- [Python Bootstrap Toolchain](0001-python-bootstrap.md)
- [Initial S3 Public Access Block Slice](0002-initial-s3-public-access-block-slice.md)
- [Backend Lambda Bootstrap](0003-backend-lambda-bootstrap.md)
- [Technical design](../DESIGN.md)
- [Data contracts](../CONTRACTS.md)
