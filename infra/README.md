# Terraform do RDS

## Configuração de rede e RDS

O Terraform final configura um DB Subnet Group formado pelas sub-redes privadas lidas do state da infraestrutura e RDS privado com armazenamento criptografado, classe `db.t3.micro` e 20 GB `gp3`. A retenção de backup configurada é de um dia e Enhanced Monitoring está desativado. Após reset do Learner Lab, reexecute as pipelines CI/CD para provisionar novamente os recursos.

O ingresso TCP 5432 é limitado ao `clusterSecurityGroupId` obtido por `data.aws_eks_cluster` e ao Security Group criado para a Lambda. O nome do cluster vem do output `eks_cluster_name` do state EKS; o output `eks_security_group_id` é um Security Group diferente e não é usado como origem do tráfego dos nodes. A consulta EKS precisa de permissão de leitura `eks:DescribeCluster`; não há recursos ou roles IAM novos declarados por este root. VPC, sub-redes e state são consultados, não criados ou alterados aqui.

## State e inicialização

O backend S3 não fixa bucket, chave ou região. Em `homolog`, preserve `rds/terraform.tfstate` para este root e `eks/terraform.tfstate` para o root VPC/EKS consumido. Em `production`, use `production/rds/terraform.tfstate` para este root; `AWS_INFRA_STATE_KEY` deve usar o prefixo `production/` e coincidir exatamente com `AWS_TF_STATE_KEY_INFRA` do Environment production do repositório produtor `autoflow-infra`. O sufixo dessa key ainda precisa ser reconciliado entre os repositórios antes de cadastrar o Environment. Não versionar IDs de conta ou configurações locais.

As keys de homologação correspondem às Repository Variables atualmente configuradas e ao mapeamento usado pelos workflows dos produtores/consumidores. Um runbook do repositório de infraestrutura registra os objetos como presentes em um inventário AWS read-only de 15/10/2026; a presença atual não foi confirmada nesta auditoria. As keys de produção são somente destinos planejados, cuja existência não foi verificada. Não inicializar States vazios, copiar ou migrar State automaticamente; reconciliar conta, bucket, owner, lineage e objeto antes de qualquer deploy.

O nome do cluster é lido do output `eks_cluster_name` no state da infraestrutura. A autenticação do provider usa a configuração de credenciais AWS do processo e `aws_allowed_account_ids`, sem provisionamento de IAM. Execute/aplique primeiro a infraestrutura com esse output publicado.

## Credenciais do banco

O contrato existente de `database_username` e `database_password` foi preservado. `sensitive = true` oculta a senha em algumas saídas do Terraform, mas **não impede sua gravação no Terraform State**, que também contém o argumento `password` do recurso RDS. O acesso ao state deve ser estritamente limitado, com criptografia e locking, e a senha deve ser passada somente por mecanismo secreto.

Como evolução recomendada, avaliar `manage_master_user_password = true`, que delega a geração e armazenamento da senha ao AWS Secrets Manager. A adoção exige validar suporte e permissões no Learner Lab, além de adaptar consumidores (aplicação e Lambda) para ler o secret; por isso não foi ativada nesta alteração nem foi modificado o contrato entre repositórios.

## Proteção contra remoção

`deletion_protection = true` reduz risco de remoção acidental. Quando uma remoção for aprovada, será necessário desabilitar a proteção em alteração explícita e revisar o plano. `skip_final_snapshot = false` exige snapshot final; o identificador configurado pode precisar ser atualizado se já existir um snapshot com o mesmo nome. Nenhum recurso AWS foi alterado nesta revisão.
