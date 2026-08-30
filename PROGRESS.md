# PROGRESS

이 문서는 Repository 수준의 통합·릴리스 진행 요약이다. 개별 기능의 Owner, 상태, Parent/Sub-issue 관계, 의존성, Milestone은 GitHub Issue / Project가 정본이며, 세부 운영 규칙은 [docs/COLLABORATION.md](docs/COLLABORATION.md)를 따른다.

- 개인 Agent 조사·세션 메모는 `.ai/`에 둘 수 있으나 Git 추적하지 않으며 팀 공유 상태가 아니다.
- 이 문서에는 `dev → main` 통합, Demo/Release, 여러 Owner에 영향을 주는 장기 차단 요인만 요약한다.
- 서술은 한국어로 작성하고 식별자·경로·기술 용어·`Status`·URL은 원문을 유지한다.

## Current

| 항목 | 관련 Parent / PR | Owner | 상태 |
| --- | --- | --- | --- |
| 협업 운영 정비 | `docs/COLLABORATION.md` 도입 PR | Shared | 진행 중 |

## Integrated / Released

| 날짜 | 항목 | 근거 | 결과 |
| --- | --- | --- | --- |
| - | - | - | - |

## Cross-owner Blocked

| 항목 | Owner | 의존 대상 | 해소 조건 |
| --- | --- | --- | --- |
| 공통 PR Gate와 Required Check 확정 | D / Shared | GitHub Ruleset 관리자 설정 | 항상 완료되는 gate 구현·등록 및 실제 규칙 확인 |
| Terraform CI 기준 | D | workflow 설계·도구 확정 | fmt/validate/TFLint/Checkov workflow와 gate 연동 |

## Release / Demo Milestone

| Milestone | 범위 | 완료 기준 | 상태 |
| --- | --- | --- | --- |
| M0 협업 운영 정비 | Issue·PR·Contract·CI·Agent 기준 정렬 | 중앙 협업 문서와 관련 템플릿·규칙 정렬, GitHub 설정 후속 항목 확인 | 진행 중 |
| M1 첫 기능 슬라이스 | S3 IaC Assessment closed-loop 1건 | Parent Feature Done 및 필요한 통합 검증 | 대기 |
| M2 확장 | Resource/Rule/Policy Source 확대 | 확정 Scope와 Contract 검증 완료 | 대기 |
| M3 Release / Demo | `dev → main` 통합과 demo/release 검증 | Release / Demo Done 기준 충족 | 대기 |
