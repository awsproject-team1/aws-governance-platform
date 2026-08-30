# Architecture Decision Records

## 목적

ADR은 구현에 지속적인 영향을 주는 확정 기술 결정과 그 Context, 선택 이유, 결과를 코드와 함께 버전 관리하기 위한 기록이다.

## ADR을 작성해야 하는 경우

- 시스템 Architecture 또는 책임 경계 변경
- IAM, 인증/인가, Secret, Trust Boundary 등 Security 결정
- API/Data/Domain Contract의 장기 호환성 결정
- 배포 모델, Runtime, State, Region, VPC, CI/CD 결정
- 장기간 영향을 주고 향후 다시 검토할 가능성이 높은 운영 결정

변수명, 사소한 코드 스타일, 국소적인 내부 구현, 쉽게 되돌릴 수 있는 작은 변경은 ADR 대상이 아니다. 이런 결정은 Issue, PR, 코드에서 관리한다.

## 상태

- `Proposed`: 검토 중이며 구현 정본으로 확정되지 않음
- `Accepted`: 합의되어 현재 구현이 따라야 함
- `Superseded`: 새 ADR이 대체함; 대체 ADR을 명시해야 함

필요한 추가 상태를 도입하는 규칙은 첫 ADR 작성 전에 합의한다.

## 파일 Naming

ADR 파일은 생성 순서를 나타내는 4자리 번호와 kebab-case 설명을 조합한 `NNNN-kebab-case.md` 형식을 사용한다.

- 번호는 `0001`부터 순차적으로 부여한다.
- 번호는 재사용하거나 기존 ADR의 의미를 바꾸기 위해 변경하지 않는다.
- ADR을 대체할 때는 새 번호로 작성하고 양쪽 문서에 대체 관계를 기록한다.
- 파일명 예시: `0001-python-bootstrap.md`

## 최소 내용

ADR에는 최소한 다음을 기록한다.

- Title
- Status
- Context / Problem
- Decision
- Consequences
- Alternatives considered
- 관련 GitHub Issue/PR 및 필요한 Notion 논의 링크 (Notion은 배경 기록이며 구현 정본은 아님)
- 대체하거나 대체되는 ADR

## Notion과 Repository ADR의 차이

- Notion `Issues & Decisions`: 논의 과정, 배경, 회의, 상위 의사결정과 프로젝트 맥락
- Repository ADR: 구현에 직접 영향을 주는 확정 기술 결정의 버전 관리 정본

논의는 Notion에서 시작할 수 있지만 구현에 지속적인 영향을 주는 확정 결정은 ADR로 남긴다. 상위 제품 결정까지 바뀌면 정본인 `docs/PRD.md`, `docs/DESIGN.md`와 관련 Repository 문서를 갱신한다. Notion 최종 계획서를 정본으로 함께 갱신하지 않는다.
