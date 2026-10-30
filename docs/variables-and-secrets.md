# Variables e Secrets por Environment

O workflow usa dois GitHub Environments: `homolog`, selecionado exclusivamente por `develop`, e `production`, selecionado exclusivamente por `main`. Plan e Apply são vinculados ao Environment selecionado antes de carregar suas configurações AWS. Pull Requests e pushes em branches de feature executam apenas CI, sem credenciais AWS, Plan ou Apply.

Cadastre os mesmos nomes de Variables e Secrets nos dois Environments, com valores independentes. Restrinja `homolog` somente a `develop` e `production` somente a `main`, configure Required reviewers para os Applies e mantenha `TERRAFORM_APPLY_APPROVAL_CONFIGURED` sem o valor `true` até confirmar que os gates estão efetivamente configurados. O workflow consulta Required reviewers e a política de branches da API do GitHub antes de permitir Apply; ausência, erro ou branch extra bloqueiam a operação.

## Variables do GitHub Environment

| Nome | Uso | Requisitos |
|---|---|---|
| `AWS_REGION` | Região do provider, backend e consultas AWS | Obrigatória; `us-east-1` nos dois Environments. |
| `AWS_EXPECTED_ACCOUNT_ID` | Conta esperada para o guard e para a lista de contas permitidas do provider | Obrigatória; exatamente 12 dígitos. Deve corresponder à identidade STS das credenciais do mesmo Environment. Não fixar o valor no código ou documentação. |
| `AWS_TERRAFORM_STATE_BUCKET` | Bucket do state RDS e do state remoto de VPC/EKS | Obrigatória; o owner do bucket precisa corresponder a `AWS_EXPECTED_ACCOUNT_ID`. |
| `AWS_TF_STATE_KEY` | Key do state deste root RDS | Obrigatória; usar o prefixo do Environment e uma key exclusiva do root RDS. |
| `AWS_INFRA_STATE_KEY` | Key do state VPC/EKS consumido pelo root RDS | Obrigatória; usar o mesmo prefixo de Environment e uma key distinta do state RDS. |
| `TERRAFORM_APPLY_APPROVAL_CONFIGURED` | Gate adicional para Apply | Não definir como `true` até Required reviewers estarem configurados e confirmados no Environment. A variável não substitui a proteção do próprio Environment. |

Use keys separadas por ambiente e por root, por exemplo `homolog/<root>/terraform.tfstate` e `production/<root>/terraform.tfstate`. No mesmo Environment, as keys de `AWS_TF_STATE_KEY` e `AWS_INFRA_STATE_KEY` não podem ser iguais. Se os ambientes estiverem na mesma conta, podem compartilhar bucket apenas com keys diferentes. Se estiverem em contas distintas, cada Environment deve apontar para bucket e States pertencentes à sua própria conta. O workflow valida o owner do bucket com `AWS_EXPECTED_ACCOUNT_ID` antes de inicializar o backend ou ler o State remoto.

Não altere keys existentes para apontar a um State vazio sem reconciliação e autorização próprias. O root continua consumindo `AWS_INFRA_STATE_KEY` do mesmo bucket e da mesma conta configurados no Environment selecionado; nenhum State de homologação é usado pela produção.

## Secrets do GitHub Environment

| Nome | Uso | Requisitos |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Credencial temporária AWS | Obrigatória; pertence à sessão configurada para aquele Environment. |
| `AWS_SECRET_ACCESS_KEY` | Credencial temporária AWS | Obrigatória; deve pertencer à mesma sessão que `AWS_ACCESS_KEY_ID`. |
| `AWS_SESSION_TOKEN` | Token temporário AWS | Obrigatório; deve pertencer à mesma sessão que as demais credenciais. |
| `DATABASE_USERNAME` | Usuário configurado no RDS | Obrigatório; valor próprio do banco/ambiente. |
| `DATABASE_PASSWORD` | Senha configurada no RDS | Obrigatório; valor próprio do banco/ambiente e sensível no Terraform. |

Não reutilize credenciais AWS ou credenciais do banco entre ambientes sem decisão operacional explícita. Os três Secrets AWS devem ser renovados juntos quando a sessão temporária expirar. Antes de configurar acesso AWS, o workflow consulta a API do GitHub e exige que os nomes de Variables e Secrets obrigatórios estejam cadastrados no Environment selecionado. Assim, valores apenas no nível de repositório ou organização não substituem configuração ausente no Environment; o workflow falha fechado sem usar essas credenciais.

## Seleção de ambiente e nomes de recursos

| Branch | GitHub Environment | `project_name` | Prefixo exigido nas keys |
|---|---|---|---|
| `develop` | `homolog` | `autoflow` | `homolog/` |
| `main` | `production` | `autoflow-production` | `production/` |

`project_name` já existe em `infra/vars.tf`; o workflow define seu valor por branch sem criar variável Terraform redundante. Ele compõe os nomes do RDS, DB Subnet Group, snapshot final e Security Groups. O nome `autoflow` mantém os nomes atuais de homologação; o prefixo `autoflow-production` evita colisão quando os ambientes compartilham uma conta.

O workflow valida `AWS_EXPECTED_ACCOUNT_ID` como 12 dígitos antes de configurar o acesso AWS e compara a identidade retornada por STS antes de consultar recursos ou inicializar Terraform. O backend S3 recebe o owner esperado; o State remoto de infraestrutura também é verificado com esse owner. Assim, o código pode ser reutilizado em diferentes Learner Labs alterando somente as configurações de cada Environment. A portabilidade não comprova permissões IAM, limites ou disponibilidade de serviços na conta de destino.

## Inputs Terraform observados

| Input | Tipo / finalidade | Obrigatoriedade / default | Origem |
|---|---|---|---|
| `project_name` | Prefixo dos nomes dos recursos | Opcional; `autoflow`; o workflow seleciona `autoflow` ou `autoflow-production` | Derivado da branch pelo workflow. |
| `region_default` | Região do provider AWS | Opcional; `us-east-1` | `AWS_REGION`. |
| `aws_profile` | Perfil AWS para execução local | Opcional; `null` | Configuração local; não enviado pelo workflow. |
| `aws_allowed_account_ids` | Contas permitidas pelo provider | Obrigatório; lista não vazia de IDs de 12 dígitos | Derivado de `AWS_EXPECTED_ACCOUNT_ID` pelo workflow. |
| `cidr_vpc` | CIDR VPC | Opcional; `10.0.0.0/16` | Default Terraform. |
| `instance_type` | Classe de instância definida no root | Opcional; `t3.medium` | Default Terraform. |
| `database_password` | Senha do usuário RDS | Obrigatório; sensível | Secret `DATABASE_PASSWORD`. |
| `database_username` | Usuário RDS | Obrigatório | Secret `DATABASE_USERNAME`. |
| `terraform_state_bucket` | Bucket do State remoto consumido | Obrigatório | Variable `AWS_TERRAFORM_STATE_BUCKET`. |
| `infra_state_key` | Key do State VPC/EKS | Opcional; valor padrão local em `infra/vars.tf` | Variable `AWS_INFRA_STATE_KEY` no workflow. |

O backend S3 não fixa bucket, key ou região no código. O workflow inicializa o State com os parâmetros do Environment, `encrypt=true`, `use_lockfile=true` e `expected_bucket_owner`. O input `infra_state_key` mantém a referência ao State VPC/EKS daquele mesmo ambiente.

## CI, Plan e Apply

O CI executa testes Python, `terraform fmt -check -recursive`, `terraform init -backend=false` e `terraform validate` sem credenciais AWS. O Plan e o Apply são habilitados somente por push ou `workflow_dispatch` nas branches `develop` e `main`. A mera execução em Pull Request ou em branch de feature não pode acessar AWS.

Em cada execução autorizada, o Plan valida configuração, conta, bucket e State remoto, impede a inicialização de State vazio quando detecta recursos já existentes sem State e gera um artefato de plano confidencial. O Apply fica associado ao mesmo GitHub Environment, revalida os Required reviewers e a política que permite exclusivamente `develop` em `homolog` ou `main` em `production`, a conta via STS, owner/key do bucket e o fingerprint de Environment, conta, bucket, keys, região e `project_name`. O hash do arquivo também é conferido, e o Apply consome exatamente o plano produzido na execução. A política `scripts/review_rds_plan.py` bloqueia qualquer ação `delete`, inclusive substituições, sem opção de bypass.

Para validação exclusivamente local, `terraform init -backend=false` e `terraform validate` não acessam AWS nem backend remoto. Não execute `terraform plan`, `apply` ou `destroy` como parte da validação local desta alteração.

**Fontes:** `.github/workflows/pipeline.yml`, `infra/vars.tf`, `infra/backend.tf`, `infra/rds-postgresql.tf`, `infra/sg.tf`, `scripts/verify_aws_account.py`, `scripts/state_resource_guard.py` e `scripts/review_rds_plan.py`.
