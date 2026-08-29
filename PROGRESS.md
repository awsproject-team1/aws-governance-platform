# PROGRESS

팀 공용 진행 관리 문서다. GitHub Issue/Project를 사용하지 않으므로 이 파일이 팀 공용 진행·마일스톤·의존성의 정본이다. Current / Completed / Next / Blocked / Milestone과 주요 Validation 상태만 짧게 유지한다.

- 개인/Agent 세부 작업은 `.ai/task/taskN.md`(Git 미추적)로 관리하고, 여기에는 팀이 알아야 할 항목만 요약한다.
- 기능 완료 시 담당자가 `dev` Merge 후 이 파일의 Completed에 핵심 결정·결과를 한 줄로 올린다.
- 서술은 한국어로 작성하고 식별자·경로·기술 용어·`Status`·URL은 원문을 유지한다.

## 최초 1회 초기화 (V3 도입 backfill — 완료 후 이 절 삭제)

> 이것은 앞으로 매번 지키는 규칙이 아니라 **V3 전환 시 딱 한 번만** 하는 작업이다. GitHub Issue/Project를 쓰던 시절에 이미 진행·완료한 작업이 이 파일에 없으므로, 각 Owner가 자기 기존 작업을 아래에 한 번 채워 넣는다. 모두 채우면 이 절을 지운다.

- [ ] A (Platform/API/Auth/Data): 기존 완료·진행 작업을 아래 Completed/Current에 요약 기록
- [ ] B (Governance/Policy/Knowledge): 동일
- [ ] C (Agent Platform/Assessment): 동일
- [ ] D (Remediation/IaC/GitHub/Deployment): 동일

기록 방법: 완료분은 `Completed`에 한 줄씩(날짜·영역·완료 항목·핵심 결정), 진행 중이면 `Current`에, 막힌 것은 `Blocked`에 넣는다. 세부는 개인 `.ai/task/`에 두고 여기에는 팀이 알아야 할 요약만 남긴다. 과거 GitHub Issue 번호는 이력 참고로만 적고 새 작업 관리에는 쓰지 않는다.

## Current

| 영역 | 기능 | Owner | Branch / PR | 상태 |
| --- | --- | --- | --- | --- |
| 공유 | V3 문서 정비(협업 방식 전환, ADR 한국어화, C4/ADR 0008-0009) | - | `docs/v3-collaboration-issueless-workflow` / PR #53 | Review 대기 |

## Completed

| 날짜 | 영역 | 완료 항목 | 핵심 결정·결과 |
| --- | --- | --- | --- |
| - | - | (첫 기능 Merge 후 담당자가 기록) | - |

## Next

- V3 협업 방식(Issue 미사용, `.ai/task` 누적, 기능별 새 Session)을 팀이 확인하고 각 영역 Owner가 첫 기능 `taskN.md`를 정의한다.
- Notion `V3 확인 필요 사항`의 Q15~Q20(Observability/Cloud 보강, 권한·자동화 경계, 새 기능 시작 자동화 수준, 코드 리뷰 자동화, Milestone 확정)을 팀 논의로 확정한다.

## Blocked

| 항목 | 의존 대상 | 사유 |
| --- | --- | --- |
| - | - | - |

## Milestone

> 아래는 **범위 위주 초안**이다. 기간(날짜)과 Owner 간 우선순위는 사람이 종합 판단해 채운다(`TODO`). 전체 순서는 Notion `V3 확인 필요 사항` Q15~Q20 결정과 연결되므로, 그 항목을 먼저 정리한 뒤 확정하는 것을 권장한다.

| Milestone | 범위(초안) | 관여 영역 | 완료 기준(Acceptance) | 기간 | 상태 |
| --- | --- | --- | --- | --- | --- |
| M0 V3 전환 확정 | 협업 방식(Issue 미사용, `.ai/task`+`PROGRESS.md`, 새 Session) 문서·규칙 정비 merge | 공유 | 구현문서 PR(#53) merge, 각 Owner PROGRESS backfill 완료 | TODO | 진행 중 |
| M1 첫 기능 슬라이스 | S3 IaC Assessment closed-loop(Finding → PR → CI/plan → Human Approval → apply → Post-Deploy) 1건 | A/B/C/D | 실제 취약 S3 fixture 1건이 평가·개선·승인·배포·재검증 완주 | TODO | 대기 |
| M2 Resource·Rule 확장 | 대상 Resource/Rule 확대, Policy Source(사내정책+ISMS-P) 반영 | B/C/D | 확정된 Rule 집합이 ACTIVE로 평가되고 Contract Test 통과 | TODO | 대기 |
| M3 통합·E2E·Release | 전체 통합, E2E/Release 검증 후 `dev → main` 1회 | 공유 | E2E 통과, 사람이 `dev → main` 통합 PR 1회 수행 | TODO | 대기 |

의존: M1 범위는 Q17(S3 단일 슬라이스 vs Resource 확장)·ADR 0002와, M2 범위는 Q(AI Score/RAG/ISMS-P Enum/Resource) 결정과 연결된다. 확정 전에는 초안 상태로 둔다.

## Validation 상태

- Python 검증: `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/python-checks.yml`(Ruff Lint/Format, Unit, Contract). 변경 경로에 해당하면 실행한다.
- Frontend 검증: `.github/workflows/frontend-checks.yml`.
- 공통 PR Gate: `validate-pr-source`(head/base 조합). 변경 영역별 공통 PR Gate는 아직 미구현(`CONTRIBUTING.md`의 blocker 참고).
