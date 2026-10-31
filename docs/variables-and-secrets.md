# Variables e Secrets por Environment

O workflow usa dois GitHub Environments: `homolog`, selecionado por `develop`, e `production`, selecionado por `main`. Plan e Apply são vinculados ao Environment selecionado. Pull Requests e pushes em branches de feature executam apenas CI. Pushes em `develop`/`main` iniciam Plan automático somente com a Repository Variable correspondente (`AUTO_CD_ENABLED_HOMOLOG` ou `AUTO_CD_ENABLED_PRODUCTION`) igual a `true` e CI bem-sucedida para o mesmo SHA; não executam Apply.

Cadastre os mesmos nomes de Variables e Secrets nos dois Environments, com valores independentes. Restrinja `homolog` somente a `develop` e `production` somente a `main`, configure Required reviewers para os Applies e mantenha `TERRAFORM_APPLY_APPROVAL_CONFIGURED` sem o valor `true` até confirmar que os gates estão efetivamente configurados. O GitHub aplica as proteções nativas do Environment ao iniciar os jobs; o workflow também consulta Required reviewers e a política de branches antes de permitir Apply.

## Variables do GitHub Environment

| Nome | Uso | Requisitos |
|---|---|---|
| `AWS_REGION` | Região do provider, backend e consultas AWS | Obrigatória; `us-east-1` nos dois Environments. |
| `AWS_EXPECTED_ACCOUNT_ID` | Conta esperada para o guard e para a lista de contas permitidas do provider | Obrigatória; exatamente 12 dígitos. Deve corresponder à identidade STS das credenciais do mesmo Environment. Não fixar o valor no código ou documentação. |
| `AWS_TERRAFORM_STATE_BUCKET` | Bucket do state RDS e do state remoto de VPC/EKS | Obrigatória; o owner do bucket precisa corresponder a `AWS_EXPECTED_ACCOUNT_ID`. |
| `AWS_TF_STATE_KEY` | Key do State deste root RDS | Obrigatória, sem default; precisa começar pelo prefixo do Environment. O sufixo é definido externamente. |
| `AWS_INFRA_STATE_KEY` | Key do State VPC/EKS consumido pelo root RDS | Obrigatória, sem default; precisa usar o mesmo prefixo e ser idêntica a `AWS_TF_STATE_KEY_INFRA` do Environment produtor. |
| `TERRAFORM_APPLY_APPROVAL_CONFIGURED` | Gate adicional para Apply | Defina `true` após configurar Required reviewers e políticas de branch. A variável não substitui a aprovação nativa do Environment. |

## Repository Variables

| Nome | Uso | Requisitos |
|---|---|---|
| `AUTO_CD_ENABLED_HOMOLOG` | Habilita Plan automático após CI em `develop`/`homolog` | Configure como Repository Variable; somente o valor literal `true` habilita o Plan. Ausência ou outro valor mantém o CD desabilitado. Não autoriza Apply. |
| `AUTO_CD_ENABLED_PRODUCTION` | Habilita Plan automático após CI em `main`/`production` | Configure como Repository Variable; somente o valor literal `true` habilita o Plan. Ausência ou outro valor mantém o CD desabilitado. Não autoriza Apply. |

## Contrato de State e isolamento

| Environment | Convenção aplicada a ambas as keys | Consumo |
|---|---|---|
| `homolog` | Prefixo obrigatório `homolog/`; sufixos fornecidos externamente | A key VPC/EKS precisa corresponder ao Environment `homolog` do produtor. |
| `production` | Prefixo obrigatório `production/`; sufixos fornecidos externamente | A key VPC/EKS precisa corresponder ao Environment `production` do produtor. |

As duas keys devem ser distintas, conter segmentos de caminho válidos e referir-se ao Environment selecionado. O workflow valida que os valores resolvidos por `vars.*` e `secrets.*` não estão vazios; não consulta a API para determinar o escopo de origem desses valores. Configure valores independentes em cada GitHub Environment e não use Repository Variables, Organization Variables ou Secrets como fallback para configuração AWS. As duas flags de CD documentadas acima são a exceção não sensível e ficam no escopo Repository. Nenhuma key final é definida na documentação ou no código. A igualdade de todas as seis keys e a correspondência global de conta, bucket e região são verificadas pelo teste integrado em `autoflow-infra/scripts/terraform_state_contract.py`; consulte a documentação desse repositório para executar a verificação com valores externos.

Antes de inicializar o backend, confirme bucket, owner, key e State autoritativo. Não aponte uma key existente para um State
vazio nem copie ou migre State sem procedimento de reconciliação e autorização próprios.

## Secrets do GitHub Environment

| Nome | Uso | Requisitos |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | Credencial temporária AWS | Obrigatória; pertence à sessão configurada para aquele Environment. |
| `AWS_SECRET_ACCESS_KEY` | Credencial temporária AWS | Obrigatória; deve pertencer à mesma sessão que `AWS_ACCESS_KEY_ID`. |
| `AWS_SESSION_TOKEN` | Token temporário AWS | Obrigatório; deve pertencer à mesma sessão que as demais credenciais. |
| `DATABASE_USERNAME` | Usuário configurado no RDS | Obrigatório; valor próprio do banco/ambiente. |
| `DATABASE_PASSWORD` | Senha configurada no RDS | Obrigatório; valor próprio do banco/ambiente e sensível no Terraform. |
| `TF_PLAN_ENCRYPTION_KEY` | Chave de criptografia do artifact Terraform Plan | Obrigatória no Environment; usada somente pelos jobs Plan/Apply, não versionada nem impressa nos logs. |

Não reutilize credenciais AWS ou credenciais do banco entre ambientes sem decisão operacional explícita. Os três Secrets AWS devem ser renovados juntos quando a sessão temporária expirar. Antes de configurar acesso AWS, o workflow verifica diretamente se os valores obrigatórios de Variables e Secrets resolvidos no job estão presentes. Os conteúdos sensíveis não são impressos nos logs; ausência de valor interrompe a execução antes do acesso AWS.

## Seleção de ambiente e nomes de recursos

| Branch | GitHub Environment | `project_name` | Keys |
|---|---|---|---|
| `develop` | `homolog` | `autoflow` | Keys fornecidas externamente, ambas sob `homolog/`. |
| `main` | `production` | `autoflow-production` | Keys fornecidas externamente, ambas sob `production/`. |

`project_name` já existe em `infra/vars.tf`; o workflow define seu valor por branch sem criar variável Terraform redundante. Ele compõe os nomes do RDS, DB Subnet Group, snapshot final e Security Groups. O nome `autoflow` mantém os nomes atuais de homologação; o prefixo `autoflow-production` evita colisão quando os ambientes compartilham uma conta.

O workflow valida `AWS_EXPECTED_ACCOUNT_ID` como 12 dígitos e compara a identidade STS antes de consultar recursos ou
inicializar Terraform. O backend S3 e o `terraform_remote_state` usam `allowed_account_ids` derivado dessa variável. Antes
do init, o workflow valida o bucket e o State remoto VPC/EKS com `head-bucket`/`head-object --expected-bucket-owner`.
Ao usar outra conta, configure as permissões IAM, quotas e recursos necessários nesse Environment.

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
| `infra_state_key` | Key do State VPC/EKS | Obrigatória; sem default | Variable `AWS_INFRA_STATE_KEY` no Environment. |

O backend S3 não fixa bucket, key ou região no código. O workflow deriva `allowed_account_ids` de `AWS_EXPECTED_ACCOUNT_ID` e inicializa o State com os parâmetros do Environment, `encrypt=true` e `use_lockfile=true`. O mesmo allowlist é usado pelo `terraform_remote_state`; as chamadas AWS CLI mantêm `--expected-bucket-owner` para validar o owner do bucket e dos objetos antes do `terraform init`. O input `infra_state_key` mantém a referência ao State VPC/EKS daquele mesmo ambiente.

## CI, Plan e Apply

O CI executa testes Python, `terraform fmt -check -recursive`, `terraform init -backend=false` e `terraform validate` sem credenciais AWS. O CD recebe `push` e `workflow_dispatch` em `develop`/`main`. No caminho automático, o gate exige a Repository Variable correspondente com valor literal `true` e sucesso da CI do mesmo SHA; esse caminho executa Plan, não Apply. Apply é exclusivo de dispatch com `apply=true`, `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true` e aprovação do Environment. Em produção, os jobs também exigem `github.ref_protected=true`.

Em cada execução autorizada, o Plan valida configuração, conta, bucket e State remoto, impede a inicialização de State vazio quando detecta recursos já existentes sem State e gera um artefato de plano confidencial. O Apply fica associado ao mesmo GitHub Environment, consulta os Required reviewers e a política que permite exclusivamente `develop` em `homolog` ou `main` em `production`, revalida a conta via STS, owner/key do bucket e o fingerprint de Environment, conta, bucket, keys, região e `project_name`. O hash do arquivo também é conferido, e o Apply consome exatamente o plano produzido na execução. A política `scripts/review_rds_plan.py` bloqueia qualquer ação `delete`, inclusive substituições, sem opção de bypass.

Para validação local, use `terraform init -backend=false` e `terraform validate`; esses comandos não acessam AWS nem backend remoto. Plan, Apply e Destroy são operações remotas e exigem os controles e autorizações aplicáveis.

**Fontes:** `.github/workflows/pipeline.yml`, `infra/vars.tf`, `infra/backend.tf`, `infra/rds-postgresql.tf`, `infra/sg.tf`, `scripts/state_key_policy.py`, `scripts/verify_aws_account.py`, `scripts/state_resource_guard.py` e `scripts/review_rds_plan.py`.
