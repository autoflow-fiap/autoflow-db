# Banco de dados na migração do gateway

Discovery somente de leitura em 13/10/2026 observou RDS PostgreSQL 17 privado (`PubliclyAccessible=false`), criptografado e disponível, com acesso PostgreSQL 5432 a partir dos SGs da Lambda e do EKS. Essa observação antecede o reset do Learner Lab e não comprova o estado atual. Nenhuma regra pública foi adicionada naquela revisão e nenhuma mudança no banco/Terraform deste repositório foi executada.

API Gateway e VPC Link **não acessam diretamente o RDS**. A Lambda mantém autenticação por consulta a usuários; o Spring mantém a persistência de negócio. Não alterar credenciais ou Secrets para migrar o gateway.

O state `rds/terraform.tfstate` continua independente e é consumido pela aplicação e pela Lambda. Reproduzir outra conta usando bucket/roles/credenciais configuráveis; não transportar state ou senhas do laboratório atual.

Após recriar a infraestrutura, ainda é necessário validar login fictício via Lambda/RDS, consulta autenticada de negócio, health do backend e isolamento de rede. Os testes locais de integração usaram PostgreSQL Testcontainers 16; não comprovam tráfego do gateway até um RDS ativo.

Consulte a [arquitetura declarada e o registro histórico anterior ao reset](https://github.com/autoflow-fiap/autoflow-infra/blob/develop/docs/api-gateway/arquitetura.md).
