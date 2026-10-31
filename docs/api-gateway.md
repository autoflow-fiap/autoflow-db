# Banco de dados na arquitetura do gateway

O API Gateway e o VPC Link não acessam diretamente o RDS. A Lambda consulta o PostgreSQL para autenticação; o backend Spring Boot usa o mesmo banco para a persistência de negócio.

O Terraform deste repositório provisiona o RDS PostgreSQL e suas regras de rede. `autoflow-infra` provisiona VPC/EKS e API Gateway; `autoflow-lambda` provisiona a função; `autoflow` provisiona os workloads e executa as migrations Flyway.

Os states Terraform permanecem independentes e são consumidos pelos repositórios conforme a configuração. O schema é mantido somente pelas migrations da aplicação.

## Provisionamento após reset

Após reset do AWS Academy Learner Lab, reexecute as pipelines CI/CD dos repositórios na ordem de dependências para provisionar novamente a infraestrutura, o RDS, a Lambda, o API Gateway e a aplicação.

Consulte a [arquitetura e os fluxos provisionáveis](https://github.com/autoflow-fiap/autoflow-infra/blob/develop/docs/api-gateway/arquitetura.md).
