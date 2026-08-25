# Cloud Governance & Compliance Agent

기업의 실제 Terraform/IaC와 조직 정책을 기준으로 Governance/Compliance를 평가하고, 승인 가능한 개선 흐름을 제공하는 고객사 내부 배포형 플랫폼입니다.

## 해결하려는 문제

기업은 사내 정책, AWS 권장사항, 보안·Compliance 기준을 실제 IaC와 AWS 상태에 일관되게 대조하기 어렵습니다. 이 프로젝트는 평가 근거와 버전을 보존하면서 Finding을 만들고, 선택된 Finding을 최소 Terraform 변경안부터 배포 후 재검증까지 연결합니다.

## 핵심 목표

- 고객이 실제 운영하는 GitHub IaC Repository를 평가의 시작점으로 사용합니다.
- 평가 범위·Rule 선택·Schema·상태 전이는 결정론적으로 통제하고, 의미 해석과 개선안 생성에 Agent를 사용합니다.
- Agent Runtime은 고객 Workload에 Read-Only로 접근하고 실제 변경은 Human Approval 이후 GitHub Actions가 수행합니다.
- Rule, Evidence, Assessment, Finding, Approval, Deployment 결과를 재현·감사할 수 있게 보존합니다.

## MVP Workflow

```text
Policy / Rule / Profile
  → Customer IaC Assessment
  → Finding / Report
  → Selected Finding
  → Terraform Patch / Pull Request
  → CI / Pre-Deploy Validation / terraform plan
  → Human Approval
  → GitHub Actions Apply
  → Post-Deploy Verification
```

## Architecture 개요

React Frontend와 API Gateway/Lambda Backend가 Cognito 인증을 사용합니다. LangGraph Parent Graph가 Policy, Assessment, Remediation Subgraph를 연결하고, Agent는 제한된 Tool을 통해 정책 근거, 고객 IaC, AWS Actual State를 조회합니다. 메타데이터는 DynamoDB, 큰 Artifact는 S3에 보존하며, Platform은 CloudFormation으로 고객 AWS Account에 배포하는 방향입니다.

## Repository 구조

- `apps/`: Frontend와 Backend 실행 영역
- `packages/contracts/`: API/Domain/Structured Output Contract 코드의 정본
- `packages/governance/`: Rule, Control, Profile, Scoring 등 Governance Domain
- `agent/`: LangGraph, Domain Agent, Runtime, Validator
- `tools/`: Policy/Evidence/GitHub/AWS 외부 경계
- `infrastructure/`: Governance Platform 자체의 고객 배포 인프라
- `ci/`: Remediation 이후 Terraform 검증·실행 지원
- `fixtures/`: 병렬 개발 및 테스트용 고정 입력/기대 결과
- `tests/`: Unit, Contract, Integration, E2E, Security Test
- `docs/`: 제품·설계·Interface·Naming 정본

고객 Workload Terraform은 이 Monorepo에 넣지 않습니다. 고객 소유 Repository 또는 별도 Demo IaC Repository가 그 정본입니다.

## 개발 시작점

현재 단계는 Repository Skeleton과 문서 Bootstrap만 완료된 상태이며 실행 가능한 Application, Agent, Tool, AWS Resource는 아직 없습니다.

1. [제품 요구사항](docs/PRD.md)과 [기술 설계](docs/DESIGN.md)를 읽습니다.
2. [Contract](docs/CONTRACTS.md), [API](docs/API.md), [Naming](docs/NAMING.md)을 확인합니다.
3. 사람 개발자는 [CONTRIBUTING.md](CONTRIBUTING.md), Coding Agent는 [AGENTS.md](AGENTS.md)를 따릅니다.
4. GitHub Issue를 만들고 `dev`에서 short-lived feature branch를 생성해 작업합니다.

빌드·테스트 명령과 환경변수는 기술 Bootstrap이 확정될 때 각 정본 문서와 `.env.example`에 추가합니다.

## 주요 문서

- Product: [docs/PRD.md](docs/PRD.md)
- Architecture: [docs/DESIGN.md](docs/DESIGN.md)
- API: [docs/API.md](docs/API.md)
- Data Contract: [docs/CONTRACTS.md](docs/CONTRACTS.md)
- Naming: [docs/NAMING.md](docs/NAMING.md)
- Collaboration: [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md)
- Architecture Decisions: [docs/decisions/README.md](docs/decisions/README.md)
