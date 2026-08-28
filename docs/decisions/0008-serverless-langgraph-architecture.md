# Serverless + LangGraph + Bedrock Architecture and Stack Selection

- **Status:** Accepted
- **Date:** 2026-08-28
- **Related Issue/PR/Notion:** DESIGNv3, V3 확인 필요 사항(Q14 C4/기술선택 ADR)
- **Supersedes:** None
- **Superseded by:** None

## Context / Problem

DESIGN/DESIGNv3는 Customer-Deployed 방식으로 고객 AWS Account에 배포되는 Governance Platform의 기술 스택(React+S3/CloudFront, Cognito, API Gateway, 기능별 Lambda, LangGraph, Bedrock, DynamoDB, S3, GitHub Actions+OIDC, Terraform)을 제시한다. 그러나 지금까지 ADR은 bootstrap·slice·boundary 위주였고 "왜 이 스택인가"를 설명하는 기술선택 근거가 없었다. 이 결정은 이후 구현 방향을 지속적으로 고정하므로 대안과 함께 기록한다.

판단 기준은 프로젝트 제약이다: Customer-Deployed(고객 계정 설치 단순성), 상시 과금 최소화(Cost), Read-Only Agent + Human Approval(권한 분리), 짧은 개발 기간의 운영 부담 최소화.

## Decision

MVP 아키텍처를 다음 스택으로 확정한다. 각 선택의 대안 비교는 아래 "Alternatives considered"에 있다.

- **Backend Compute: AWS Lambda (기능별 분리).** 상시 과금 없는 이벤트 기반. API Gateway·Cognito·DynamoDB·S3와 IAM으로 통합. 15분 실행 제한은 장시간 워크플로우에서 재검토 대상(아래 Consequences).
- **Workflow Orchestration: LangGraph.** Parent Graph + Subgraph. Assessment/Remediation/Deployment의 상태·중단/재개·Human-in-loop를 Graph+Checkpoint로 표현. LLM Agent·Tool 호출 루프와의 결합도가 높다.
- **Metadata Store: DynamoDB.** 서버리스·사용량 기반. 접근 패턴이 ID/상태/관계 중심이고 조건부 쓰기(CAS)로 Job revision·Artifact 멱등성을 구현한다.
- **Artifact Store: S3.** 대용량 원본·결과물, content-hash 주소화(`sha256:`).
- **Auth: Amazon Cognito.** 고객 Account 내 배포, API Gateway JWT Authorizer 통합, `Admin/User` Group RBAC.
- **API: API Gateway HTTP API + JWT Authorizer.** REST 진입점, 서버리스, 장시간 작업은 202 + Job Polling.
- **LLM: Amazon Bedrock.** 고객 Account 내 IAM 호출로 데이터 경계 유지.
- **Frontend Hosting: S3 + CloudFront.** 정적 SPA 호스팅, 상시 과금 최소.
- **IaC 배포: GitHub Actions + OIDC.** 고객 GitHub/PR 운영과 직결, 임시 자격증명(장기 키 금지), Plan/Deploy Role 분리.
- **Customer IaC: Terraform.** 고객 Workload가 Terraform 기반이라는 전제.

## Consequences

- 상시 과금 리소스를 최소화하고 고객 계정 설치를 단순화한다.
- **Lambda 15분 실행 제한**이 리스크로 남는다. LangGraph 실행 + 다중 LLM 호출 + `terraform plan`이 이를 초과할 수 있다. "Lambda 우선, 초과 시 Container(예: ECS/Fargate) 또는 Step Functions로 일부 분리"를 확장안으로 두되, 실제 한계선은 구현 중 실측으로 확정한다(V3 확인 필요 Q9).
- 기능별 Lambda의 분리 단위(개수)는 콜드스타트·배포 복잡도와 트레이드오프가 있어 구현 시 조정한다.
- DynamoDB는 복잡한 Ad-hoc 집계에 약하므로, Source별 Score/Coverage 같은 집계는 응용 계층에서 처리하고 GSI/접근 패턴을 선고정한다.
- Bedrock 모델·리전 가용성에 종속된다. AgentCore/Guardrails 등 세부 채택은 PoC 후 확정한다.

## Alternatives considered

- **Compute를 ECS/Fargate로:** 장시간 실행·15분 제한 없음이 강점이나, 고객 계정 설치 시 네트워크/클러스터 관리 부담과 상시 과금이 커진다. 서버리스 우선 원칙과 멀어 기각. 단, Lambda 한계 초과 구간의 확장안으로는 유지.
- **Compute를 EC2로:** 가장 유연하나 패치·스케일링·상시 과금 부담이 가장 크다. 기각.
- **Workflow를 AWS Step Functions로:** 관리형·시각화·재시도가 강점이나 LLM Agent의 동적 분기·Tool 루프·부분 상태 유지 표현이 경직되고 Agent 생태계 결합도가 낮다. 기각(장시간 구간 보조 수단으로는 검토 가능).
- **Workflow를 Temporal로:** 내구성 있는 장기 Workflow에 강력하나 별도 서버·운영 부담이 커 Customer-Deployed 설치가 무거워진다. 기각.
- **Workflow를 Framework 없이 직접 구현:** 초기엔 가볍지만 Human-in-loop 중단/재개·체크포인트를 직접 만들면 금방 복잡해진다. 기각.
- **Metadata를 RDS/Aurora로:** 복잡 조인·Ad-hoc 쿼리에 강하나 상시 가동 인스턴스 과금과 운영 부담, 설치 복잡도가 늘어난다. Aurora Serverless v2도 최소 용량 과금이 있다. 기각.
- **Auth를 Auth0/외부 IdP로:** 기능은 풍부하나 고객 Account 내부 배포 모델에서 외부 의존·데이터 경계·과금 이슈가 생긴다. 기각.
- **자체 JWT 구현:** 서명·키 회전·탈취 대응을 직접 만들면 보안 리스크가 크다. 기각.
- **API를 ALB+Lambda / AppSync로:** ALB는 상시 과금, AppSync(GraphQL)는 MVP의 REST+Polling 요구에 과하다. 기각.
- **LLM을 OpenAI/Anthropic 직접 API로:** 모델 선택폭은 넓으나 고객 AWS Account 밖으로 데이터가 나가는 경계 문제와 별도 자격증명 관리가 생겨 Customer-Deployed와 충돌. 기각.
- **Frontend를 Amplify Hosting / EC2로:** Amplify는 편리하나 설정 자유도·배포 투명성 제약, EC2는 상시 과금·관리 부담. S3+CloudFront가 정적 SPA에 최적. 기각.
- **IaC 배포를 CodePipeline / 장기 Access Key로:** 고객 IaC가 GitHub·PR 중심이라 GitHub Actions가 자연스럽고, 장기 키는 보안 원칙 위반. 기각.
