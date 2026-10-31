# AutoFlow — banco de dados gerenciado

Este repositório provisiona o Amazon RDS PostgreSQL e suas regras de rede. O schema e as migrations Flyway pertencem ao
backend em [`autoflow`](https://github.com/autoflow-fiap/autoflow).

## Arquitetura

O root `infra/` declara RDS PostgreSQL 17 privado, subnet group e Security Groups. Consome VPC e subnets do State de
`autoflow-infra`; o backend Spring Boot e a Lambda de autenticação acessam o banco pela rede privada.

| Configuração declarada em Terraform | Valor |
|---|---|
| Instância e armazenamento | `db.t3.micro`, 20 GB `gp3` |
| Acesso público | Desativado |
| Criptografia | Ativada |
| Retenção de backup | 1 dia |
| Snapshot final | Obrigatório |
| Proteção contra remoção | Ativada |
| Enhanced Monitoring | Desativado |

O modelo relacional está no [diagrama ER](docs/diagrama-er.md); a justificativa para PostgreSQL e a separação entre
infraestrutura e schema estão em [RFC-001](docs/RFC-001.md). O contrato de API e autenticação está no
[guia OpenAPI](https://github.com/autoflow-fiap/autoflow/blob/develop/docs/openapi/README.md) e na
[coleção Postman](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/postman/autoflow-serverless-auth.postman_collection.json).

## Validar localmente

Com Terraform 1.16.5 e Python:

```bash
terraform fmt -check -recursive infra
terraform -chdir=infra init -backend=false -input=false
terraform -chdir=infra validate
python -m unittest discover -s scripts -p 'test_*.py' -v
```

Esses comandos não acessam a AWS. Um Plan remoto usa as credenciais e os Terraform States configurados para o ambiente;
consulte [Variables e Secrets](docs/variables-and-secrets.md).

## CI/CD e ambientes

- `ci.yml` executa testes e validação Terraform em Pull Requests para `develop`/`main` e pushes para essas branches e
  `feature/**`, sem credenciais AWS.
- `pr-automatico.yaml` solicita Pull Request para `develop` após pushes em branches diferentes de `develop`.
- `pipeline.yml` recebe `push` e `workflow_dispatch` em `develop`/`main`. O gate valida a CI do mesmo repositório, branch
  e SHA. `AUTO_CD_ENABLED=true` no GitHub Environment selecionado habilita o Plan automático; esse caminho não executa
  Apply. `develop` seleciona `homolog`; `main` seleciona `production`.
- `workflow_dispatch` executa Plan por padrão. Apply exige `apply=true` e
  `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`. O workflow verifica Required reviewers e a política do Environment para
  limitar `homolog` a `develop` e `production` a `main`; `main` também exige branch protegida.
- O Plan é criptografado e vinculado à execução e ao commit. Apply valida sua integridade e aplica o Plan produzido
  naquele fluxo; o guard do RDS bloqueia exclusões e substituições.

Configure as proteções de branch para exigir Pull Request e checks de CI. Os workflows dos repositórios são
independentes; a ordem de provisionamento e os gates estão descritos no [guia de CI/CD](docs/ci-cd-automatico.md) e no
[runbook de implantação](https://github.com/autoflow-fiap/autoflow-infra/blob/develop/docs/api-gateway/runbook.md).

## Documentação relacionada

- [Integração com API Gateway](docs/api-gateway.md)
- [Seeds de demonstração](docs/seeds-demonstracao.md)
- [Variables e Secrets](docs/variables-and-secrets.md)
- [README do root Terraform](infra/README.md)
