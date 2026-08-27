## What

무엇을 변경했는지 요약합니다.

## Why

왜 필요한 변경인지 설명합니다.

## Related Issue

- Parent: #
- Refs Sub-issue: #

Sub-issue는 `dev` Merge 확인 후 사람이 수동으로 닫습니다. 자동 종료용 `Closes`를 사용하지 않으며 Parent Issue를 PR에서 닫지 않습니다.

## PR Type

- [ ] Sub-issue / Feature → `dev`
- [ ] Bug Fix → `dev`
- [ ] Docs / Refactor / Chore → `dev`
- [ ] Integration: `dev` → `main`

## Base / Head 확인

- 일반 작업: `작업 branch` → `dev`
- 안정화 통합: 같은 Repository의 `dev` → `main`
- `feature/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, `chore/*` → `main` 직접 PR은 금지

## Changes

-

## Validation

PR 전에 실행한 로컬 명령 또는 수동 확인 절차를 기록합니다. PR 후 Required CI 결과와 구분합니다.

## Test Result

- [ ] Unit Test
- [ ] Contract Test
- [ ] Integration/E2E Test (해당 시)
- [ ] Lint / Build / Terraform Validation (해당 시)

## Architecture Impact

- [ ] 없음
- [ ] 있음 — 영향과 `docs/DESIGN.md`/ADR 변경을 설명함

## Contract Impact

- [ ] 없음
- [ ] 있음 — Producer/Consumer, 호환성, `packages/contracts/`와 `docs/CONTRACTS.md` 변경을 설명함

## Documentation Updated

- [ ] 불필요
- [ ] 관련 PRD/DESIGN/API/CONTRACTS/NAMING/ADR 갱신

## Security / Secret Check

- [ ] Secret, Credential, Access Key, 민감정보를 포함하지 않음
- [ ] 권한/IAM/외부 접근 영향 확인

## Other Owner Review

- [ ] 불필요
- [ ] A
- [ ] B
- [ ] C
- [ ] D

## Checklist

- [ ] Acceptance Criteria를 충족함
- [ ] PR 전 필요한 Test와 Validation을 수행함
- [ ] 적용되는 Required CI가 통과 가능한 상태임
- [ ] 관련 문서를 갱신함
- [ ] Secret이 포함되지 않음
- [ ] `dev` 최신 변경사항과 충돌 여부를 확인함
- [ ] 일반 작업 PR의 base가 `dev`임
- [ ] `main` 대상 PR이면 head가 같은 Repository의 `dev`임
- [ ] Required Check와 Review 조건을 우회하지 않음
- [ ] 다른 팀원 최소 1명의 Review를 받을 준비가 됨
- [ ] Merge는 사람이 수행함
- [ ] `dev` Merge 후 Sub-issue를 사람이 수동 종료함
