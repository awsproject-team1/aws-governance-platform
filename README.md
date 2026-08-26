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
  → Post-Deploy IaC 준수와 AWS Actual 일치 확인
```

### Initial Demo Slice

최초 데모는 취약한 Terraform S3 Bucket 1개와 S3 Public Access Block Rule candidate 1개로 제한합니다. Public Access Block 누락을 Initial Assessment에서 발견하고, 최소 Terraform Remediation PR과 사람의 승인·Apply를 거쳐 새 Post-Deploy Assessment와 AWS Actual verification으로 개선을 확인합니다. Rule ID, Control key, lifecycle status와 판정 Enum은 Shared Contract 구현과 Rule 근거 승인 전까지 Proposed 상태이며 ACTIVE 정본으로 사용하지 않습니다.

## Architecture 개요

React Frontend와 API Gateway/Lambda Backend가 Cognito 인증을 사용합니다. LangGraph Parent Graph가 Policy, Assessment, Remediation Subgraph를 연결하고, Agent는 제한된 Tool을 통해 정책 근거, 고객 IaC, AWS Actual State를 조회합니다. 메타데이터는 DynamoDB, 큰 Artifact는 S3에 보존하며, Platform은 CloudFormation으로 고객 AWS Account에 배포하는 방향입니다.

## Repository 구조

- `apps/`: Frontend와 Backend 실행 영역
- `packages/contracts/`: 향후 API/Domain/Structured Output Contract 코드의 실행 정본; 현재는 placeholder
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

현재 단계는 Repository/문서/Python/Backend Package Bootstrap까지 완료됐습니다. 실행 가능한 제품 Application, Shared Contract, 제품 Lambda Handler, Agent, Tool, AWS Resource는 아직 없습니다. `_bootstrap_probe`는 배포 대상이 아닌 Package 검증용입니다.

1. [제품 요구사항](docs/PRD.md)과 [기술 설계](docs/DESIGN.md)를 읽습니다.
2. [Contract](docs/CONTRACTS.md), [API](docs/API.md), [Naming](docs/NAMING.md)을 확인합니다.
3. 사람 개발자는 [CONTRIBUTING.md](CONTRIBUTING.md), Coding Agent는 [AGENTS.md](AGENTS.md)를 따릅니다.
4. GitHub Issue를 만들고 `dev`에서 short-lived feature branch를 생성해 작업합니다.

Python 개발 명령은 아래 기술 Bootstrap으로 확정했습니다. 제품 Runtime 환경변수와 Application별 배포 명령은 해당 구현이 결정될 때 각 정본 문서와 `.env.example`에 추가합니다.

## Python 개발 환경

초기 Python 도구 체계는 Python 3.14, 표준 `pip`, `unittest`, Ruff를 사용합니다. 결정 배경과 제외 범위는 [ADR 0001](docs/decisions/0001-python-bootstrap.md)을 확인합니다.

PowerShell에서 Python 3.14를 명시해 로컬 환경을 준비합니다.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip install --requirement requirements-dev.txt --requirement apps/backend/requirements.txt
```

변경사항을 검증합니다.

```powershell
python -m ruff check .
python -m ruff format --check .
python -m unittest discover --start-directory tests/unit --pattern "test_*.py" --verbose
python -m unittest discover --start-directory tests/contract --pattern "test_*.py" --verbose
```

Python CI는 동일한 명령을 실행하며, 모든 Pull Request에는 별도 Secret Scan이 실행됩니다. 현재 Contract discovery는 실행 Contract가 없음을 확인하는 bootstrap guard 1건을 실행합니다. 실행 Contract가 추가되는 PR은 이 guard를 실제 Producer/Consumer Contract Test로 교체해야 합니다. 현재 Bootstrap은 제품 API Contract, Frontend Toolchain 또는 AWS Resource를 선택하지 않습니다.

## Backend Lambda Bootstrap

Backend는 [ADR 0003](docs/decisions/0003-backend-lambda-bootstrap.md)에 따라 Framework-free Python package 경계를 사용합니다.

```text
apps/backend/
├─ __init__.py
├─ handlers/
│  ├─ __init__.py
│  └─ _bootstrap_probe.py  # private, non-deployable
└─ requirements.txt       # exact runtime dependency pins
```

`_bootstrap_probe`는 제품 Lambda Handler가 아닙니다. 다음 명령은 API Gateway Contract 없이 import/invocation 경계만 확인합니다.

```powershell
python -c "from apps.backend.handlers._bootstrap_probe import invoke; invoke(object(), object())"
```

Unit Test는 `apps/backend`만 임시 ZIP stage root에 복사한 뒤 별도 Python Process에서 동일한 import/invocation을 수행합니다. 실제 ZIP 생성·Lambda 배포·제품 Handler 구성은 첫 제품 API Handler의 Contract와 Infrastructure가 승인된 후 추가합니다.

## 주요 문서

- Product: [docs/PRD.md](docs/PRD.md)
- Architecture: [docs/DESIGN.md](docs/DESIGN.md)
- API: [docs/API.md](docs/API.md)
- Data Contract: [docs/CONTRACTS.md](docs/CONTRACTS.md)
- Naming: [docs/NAMING.md](docs/NAMING.md)
- Collaboration: [CONTRIBUTING.md](CONTRIBUTING.md), [AGENTS.md](AGENTS.md)
- Architecture Decisions: [docs/decisions/README.md](docs/decisions/README.md)
