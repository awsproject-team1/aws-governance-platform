## What / Why

무엇을 왜 변경하는지 요약합니다.

## Related Issue

- Parent: #
- Related Sub-issue / Bug — 아래 중 정확히 하나만 남기고 다른 줄은 삭제:
  - `Closes #` — 이 PR merge로 모든 Acceptance Criteria를 충족해 Done 처리 가능
  - `Refs #` — 일부 구현·기반 작업·조사이며 Issue를 계속 열어 둠

Parent Issue에는 closing keyword를 사용하지 않습니다. Agent는 사람의 명시적 요청 없이 Issue 상태를 변경하지 않습니다.

## PR Type / Route

- [ ] Sub-issue / Feature → `dev`
- [ ] Bug Fix → `dev`
- [ ] Docs / Refactor / Chore → `dev`
- [ ] Integration / Release: 같은 Repository의 `dev` → `main`

작업 branch는 최신 `dev`에서 만든 `feature|fix|docs|refactor|test|chore/<issue-number>-kebab-case` 형식이어야 합니다. 다른 기능 branch를 base로 하거나 `main`으로 직접 PR하지 않습니다.

## Scope

- Included:
- Out of scope:

## Dependency Status

- Status — 정확히 하나만 기록: `None` / `Blocked` / `Mockable` / `Integrated`
- Dependency / Owner / 해소 조건:
- Fixture/Fake/Mock 경계 또는 실제 통합 결과:

`Blocked`가 하나라도 해소되지 않은 PR은 `Closes`를 사용하거나 Done으로 merge할 수 없습니다.

## Validation

PR 전에 실행한 로컬 명령·수동 확인과 PR 후 CI 결과를 구분해 기록합니다.

- Local:
- CI:
- Not run / reason:

## Architecture / Contract Impact

- [ ] 없음
- [ ] 있음 — Contract Owner:
- [ ] Producer 검토 완료
- [ ] 영향받는 named Consumer / 다른 Owner의 해당 PR revision 승인 완료:
- [ ] ADR 필요 또는 갱신함:

## Documentation / Security

- [ ] 관련 `docs/`, ADR, Fixture, Test를 갱신함
- [ ] Secret, Credential, Access Key, 민감정보를 포함하지 않음
- [ ] 권한/IAM/외부 접근 영향을 확인함

## Review / Merge Checklist

- [ ] Acceptance Criteria를 충족함
- [ ] 적용되는 로컬 Validation과 CI를 확인함
- [ ] 일반 작업 PR의 base가 `dev`임
- [ ] `main` 대상 PR이면 head가 같은 Repository의 `dev`임
- [ ] Required Check와 Review 조건을 우회하지 않음
- [ ] 필요한 Consumer / A / B / C / D Owner의 명시적 승인이 완료됨
- [ ] 해소되지 않은 `Blocked` 의존성이 없음
- [ ] 일반 PR은 Squash Merge, `dev → main` 통합 PR은 Merge Commit 기준을 따름
- [ ] merge 뒤 Issue/Project 상태와 handoff를 사람이 확인함

## Handoff

```markdown
- Completed:
- In Progress:
- Next:
- Blocked:
- Validation:
```
