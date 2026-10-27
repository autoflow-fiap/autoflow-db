# Variables e secrets

Após reset do Learner Lab, mantenha as credenciais temporárias, `AWS_REGION`, `AWS_EXPECTED_ACCOUNT_ID`, bucket e keys dos states, além dos secrets de banco. O pipeline valida conta/região e reutiliza os states existentes; não é necessário cadastrar identificadores de recursos RDS manualmente.

Inventário observado nos workflows e Terraform. PRs e pushes em `main` executam somente CI. Push em `develop` executa Plan e, após aprovação, Apply no `environment: homolog`. CI executa sem credenciais AWS. O Plan precisa acessar credenciais e variáveis antes da aprovação do Environment, portanto esses itens devem estar disponíveis como secrets/variables do repositório. O Apply usa os valores do Environment `homolog`. A existência e as proteções reais do Environment não foram verificadas localmente.

## GitHub Actions — Secrets

| Nome | Tipo / finalidade | Onde configurar; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN` | Secrets; credenciais temporárias AWS da mesma sessão | Repositório para Plan; Environment `homolog` para Apply. Sessão AWS Academy Learner Lab | CD | Não aplicável | `.github/workflows/pipeline.yml`; obrigatórios, sem defaults. Devem pertencer à mesma sessão temporária. |
| `DATABASE_USERNAME` | Secret; usuário RDS entregue ao Terraform | Repositório para Plan; Environment `homolog` para Apply | CD | Não aplicável | Workflow mapeia `TF_VAR_database_username`; sem default. |
| `DATABASE_PASSWORD` | Secret; senha RDS | Repositório para Plan; Environment `homolog` para Apply | CD | Não aplicável | Workflow mapeia `TF_VAR_database_password`; sem default; sensível no Terraform. |

## GitHub Actions — Variables

| Nome | Finalidade | Onde; origem | CI / CD | Exemplo seguro | Consumidor; default/ausência |
|---|---|---|---|---|---|
| `AWS_REGION` | Região AWS explícita | Repositório para Plan; Environment `homolog` para Apply | CD | `us-east-1` | Workflow/provider/backend; obrigatória, sem default. |
| `AWS_EXPECTED_ACCOUNT_ID` | Conta AWS validada pelo guard | Repositório para Plan; Environment `homolog` para Apply | CD | Não aplicável | Workflow/scripts; obrigatória, sem default. Não fixar account ID no código. |
| `AWS_TERRAFORM_STATE_BUCKET` | Bucket S3 preexistente | Repositório para Plan; Environment `homolog` para Apply | CD | Não aplicável | Workflow/backend/input; obrigatória, sem default. |
| `AWS_TF_STATE_KEY` | Key state RDS | Repositório para Plan; Environment `homolog` para Apply | CD | `rds/terraform.tfstate` | Workflow/backend; obrigatória, sem default. |
| `AWS_INFRA_STATE_KEY` | Key state VPC/EKS consumida pelo RDS | Repositório para Plan; Environment `homolog` para Apply | CD | `eks/terraform.tfstate` | Workflow/state remoto; obrigatória, sem default. |
| `TERRAFORM_APPLY_APPROVAL_CONFIGURED` | Guard adicional para Apply | Environment `homolog`; `true` somente após Required reviewers | CD | `true` | Workflow também consulta a API e bloqueia se não houver Required reviewers. Guard não substitui a proteção GitHub. |

## Terraform inputs — `infra/vars.tf`

`TF_VAR_*` pode vir do workflow, shell local ou mecanismo seguro. Backend S3 também recebe `-backend-config` explicitamente no workflow.

| Input | Tipo / finalidade | Obrigatoriedade / default | Origem/consumidor |
|---|---|---|---|
| `project_name` | Prefixo de recursos | Opcional; `autoflow` | Configuração local/Terraform. |
| `region_default` | Região padrão | Opcional; `us-east-1` | GitHub `AWS_REGION`; provider. |
| `aws_profile` | Perfil AWS local | Opcional; `null` | Configuração local; não enviado pelo workflow. |
| `aws_allowed_account_ids` | Lista de contas permitidas | Obrigatório; sem default; lista não vazia de IDs com 12 dígitos | Workflow converte `AWS_EXPECTED_ACCOUNT_ID` em JSON list. |
| `cidr_vpc` | CIDR VPC | Opcional; `10.0.0.0/16` | Terraform. |
| `instance_type` | Classe de instância | Opcional; `t3.medium` | Terraform. |
| `database_password` | Senha do banco | Obrigatório; sem default; `sensitive=true` | Secret `DATABASE_PASSWORD` → `TF_VAR_database_password`. |
| `database_username` | Usuário do banco | Obrigatório; sem default | Secret `DATABASE_USERNAME` → `TF_VAR_database_username`. |
| `terraform_state_bucket` | Bucket de states consumidos | Obrigatório; sem default | `AWS_TERRAFORM_STATE_BUCKET`. |
| `infra_state_key` | Key state VPC/EKS | Opcional; `eks/terraform.tfstate` | `AWS_INFRA_STATE_KEY` no workflow. |

## Configuração local e fluxo

`AWS_PROFILE`, `AWS_REGION`, `AWS_EXPECTED_ACCOUNT_ID` e as variáveis `TF_VAR_*` são configuração local externa; backend requer bucket/key/região e lock S3. Não versionar tfvars com credenciais. PRs e pushes em `main` executam somente CI. Push em `develop` executa Plan com o state remoto e envia por um dia o binário confidencial `rds.tfplan` e seu SHA-256; logs não exibem a saída do Plan. O Apply em `homolog` confere o hash e revalida a política antes de aplicar exatamente esse binário. A política bloqueia toda ação `delete`, inclusive replace, sem exceção ou override; Plan sem mudanças é aprovado. CD valida conta/região, bucket e existência dos states RDS/infra antes do Plan e Apply; o cluster é selecionado pelo output Terraform `eks_cluster_name`, não por variable adicional. Um grupo de concorrência serializa operações no mesmo state. O workflow não executa SQL nem migrations Flyway.

**Divergências de nomes:** GitHub `DATABASE_USERNAME/PASSWORD` alimentam inputs Terraform homônimos; workflow os converte em `TF_VAR_database_username/password`. `AWS_TF_STATE_KEY` é backend do state RDS, enquanto `AWS_INFRA_STATE_KEY` alimenta `infra_state_key`. A documentação local de `infra/README.md` registra defaults de key/região distintos de alguns valores usados pelo workflow; para CD prevalece o mapeamento explícito do workflow.

**Fontes:** `.github/workflows/pipeline.yml`, `infra/vars.tf`, `infra/backend.tf`, `infra/rds-postgresql.tf`, `infra/README.md`, `scripts/verify_aws_account.py`, `scripts/review_rds_plan.py`.
