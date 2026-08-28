# PROGRESS

팀 공용 진행 관리 문서다. GitHub Issue/Project를 사용하지 않으므로 이 파일이 팀 공용 진행·마일스톤·의존성의 정본이다. Current / Completed / Next / Blocked / Milestone과 주요 Validation 상태만 짧게 유지한다.

- 개인/Agent 세부 작업은 `.ai/task/taskN.md`(Git 미추적)로 관리하고, 여기에는 팀이 알아야 할 항목만 요약한다.
- 기능 완료 시 담당자가 `dev` Merge 후 이 파일의 Completed에 핵심 결정·결과를 한 줄로 올린다.
- 서술은 한국어로 작성하고 식별자·경로·기술 용어·`Status`·URL은 원문을 유지한다.

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
- Notion `V3 확인 필요 사항`의 Q15~Q18(Observability/Cloud 보강, 권한·자동화 경계, 새 기능 시작 자동화 수준)을 팀 논의로 확정한다.

## Blocked

| 항목 | 의존 대상 | 사유 |
| --- | --- | --- |
| - | - | - |

## Milestone

| Milestone | 범위 | 상태 |
| --- | --- | --- |
| (사람이 종합 판단해 기간·범위·우선순위를 채운다) | - | - |

## Validation 상태

- Python 검증: `pyproject.toml`, `requirements-dev.txt`, `.github/workflows/python-checks.yml`(Ruff Lint/Format, Unit, Contract). 변경 경로에 해당하면 실행한다.
- Frontend 검증: `.github/workflows/frontend-checks.yml`.
- 공통 PR Gate: `validate-pr-source`(head/base 조합). 변경 영역별 공통 PR Gate는 아직 미구현(`CONTRIBUTING.md`의 blocker 참고).
