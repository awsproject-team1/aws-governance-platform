# AI Evaluator Scoring and RAG Removal

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related Issue/PR/Notion:** PRDv3, DESIGNv3, V3 확인 필요 사항(Q1/Q2/Q3)
- **Supersedes:** [0007 Governance Document Ingestion Boundary](0007-governance-document-ingestion-boundary.md)의 RAG/Knowledge Base 검색 관련 부분
- **Superseded by:** None

## Context / Problem

기존 설계는 (1) LLM이 PASS/FAIL만 판정하고 Score는 결정론적 코드가 고정 산식(Severity Weight `CRITICAL=10/HIGH=5/MEDIUM=2/LOW=1`)으로 계산했고, (2) 정책 근거를 Bedrock Knowledge Base 등 RAG 검색으로 가져오는 방향이었다. ADR 0007은 문서 수집 파이프라인과 `pypdf` 런타임 의존성을 확정했다.

3차 멘토링과 팀 논의에서 두 방향을 재검토했다. MVP는 "Rule 검사 수"보다 "AI가 전문가 평가를 얼마나 대체·보조하는가"를 증명하는 것이 가치이며, 정책 문서량이 Context Window에 직접 넣을 수 있는 수준이면 RAG의 복잡성·재현성 비용이 이득보다 크다는 판단이다.

## Decision

- **AI Evaluator가 판정과 Score를 소유한다.** 코드가 고정 산식으로 Score를 계산하지 않는다. AI Evaluator가 적용 Rule 선택, Evidence 판단, `PASS/FAIL/MANUAL_REVIEW/INSUFFICIENT_EVIDENCE`, Severity, Score를 생성한다.
- **Score는 MVP에서 0–100 연속값으로 생성한다.** Score Anchor 집합(`{0,15,30,50,70,85,100}`) 방식은 초기 구현에 적용하지 않고, 구현 후 반복 편차 테스트 결과를 보고 추후 도입을 검토한다.
- **Code는 평가 내용을 정하지 않고 안전장치만 소유한다:** Customer/Account/Repository/Scope Boundary, 허용 Tool·Read 권한, Output Schema Validation, Score 범위(0–100) 검증, Evidence Reference 유효성, Prompt/Model/Rubric/Rule Version 기록, Evaluation Coverage 기계 계산.
- **Evaluation Harness를 필수로 함께 둔다.** AI Score의 재현성·일관성 리스크를 Golden Dataset과 반복 실행으로 검증한다. 지표: Correctness, Evidence Reference Accuracy, Self-Agreement, Invariance, Sensitivity, 과대평가 여부, Remediation 후 Finding Resolution/Score 변화.
- **MVP에서 RAG/Vector DB/Bedrock Knowledge Base를 사용하지 않는다.** 정책 원문은 S3에 두고, 승인된 Rule/Source Reference를 구조화한 Policy Context를 AI에 직접 전달한다.
- **단, "검색(RAG)"과 "근거 추적(Source Reference/locator/content hash)"은 분리한다.** RAG를 제거해도 "어느 문서의 어느 부분을 근거로 평가했는가"를 보장하는 Frozen Document/Evidence locator 구조는 유지한다.

## Consequences

- 저장소 CONTRACTS의 결정론적 Scoring 계약(Severity Weight, `scoring_version` 고정 산식)은 이 결정으로 Score 산출의 정본에서 물러난다. CONTRACTS의 Scoring 절을 AI Score + Code 검증 구조로 갱신해야 한다.
- ADR 0007의 문서 수집 경계 자체(업로드 검증 → Loader → Canonical → Segmentation → Frozen → Index)와 locator/content hash 근거 추적은 유지한다. **RAG/Knowledge Base 검색 계층만 폐기**한다. `pypdf`는 업로드 문서 파싱에 여전히 필요하면 유지하고, 문서 수집 범위가 축소되면 재검토한다.
- AI Score 도입으로 재현성이 약해지므로 Evaluation Harness(Golden Dataset)가 성공 기준의 전제 조건이 된다. Golden Dataset 소유·생성 계획을 정해야 한다(V3 확인 필요 Q13).
- 정책 문서량이 Context Window를 초과하는 수준으로 커지면 RAG 도입을 확장안으로 다시 검토한다.

## Alternatives considered

- **판정=AI, Score=코드 고정 산식 유지:** 재현성은 높지만 "AI가 전문가 평가를 대체"하는 제품 가치와 유연한 의미 평가(보완통제·Evidence 강도)를 반영하기 어렵다. 기각.
- **AI Score를 Anchor 집합으로 즉시 도입:** 반복 편차를 줄이는 장점이 있으나, 초기에 Anchor 의미·Rubric을 고정하는 비용이 크고 아직 편차 데이터가 없다. MVP는 0–100 연속으로 시작하고 테스트 후 Anchor를 검토하기로 함. 기각(추후 재검토).
- **RAG/Knowledge Base 유지:** 문서량이 많을 때 유리하나, MVP 정책량에선 Context Window 직접 전달로 충분하고 검색 계층은 재현성·비용·복잡도를 늘린다. 기각(문서량 증가 시 재도입 검토).
- **ADR 0007 전체 폐기:** 근거 추적(locator/content hash)까지 버리면 "무엇을 근거로 평가했는가"를 잃는다. RAG 검색만 폐기하고 근거 추적은 유지. 기각.
