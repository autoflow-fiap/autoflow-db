# Terraform do RDS

## Configuração de rede e RDS

O root usa o DB Subnet Group formado pelas sub-redes privadas lidas do state da infraestrutura. O RDS é privado, criptografa o armazenamento e mantém a classe `db.t3.micro` com 20 GB `gp3`, adequada à homologação de baixo custo. A retenção de backup é de um dia. Enhanced Monitoring permanece desativado para evitar custos adicionais.

O ingresso TCP 5432 é limitado ao `clusterSecurityGroupId` obtido por `data.aws_eks_cluster` e ao Security Group criado para a Lambda. O nome do cluster vem do output `eks_cluster_name` do state EKS; o output `eks_security_group_id` é um Security Group diferente e não é usado como origem do tráfego dos nodes. A consulta EKS precisa de permissão de leitura `eks:DescribeCluster`; não há recursos ou roles IAM novos declarados por este root. VPC, sub-redes e state são consultados, não criados ou alterados aqui.

## State e inicialização

O backend S3 não fixa bucket, chave ou região. Inicialize com os parâmetros aprovados externamente, incluindo `key=rds/terraform.tfstate`, região `us-east-1`, criptografia e locking conforme suporte do bucket. `TF_VAR_terraform_state_bucket` é obrigatório e deve apontar ao bucket externo correto; `TF_VAR_infra_state_key` assume `eks/terraform.tfstate`. Não versionar configurações locais com identificadores de ambiente.

O nome do cluster é lido do output `eks_cluster_name` no state da infraestrutura. A autenticação do provider usa a configuração de credenciais AWS do processo e `aws_allowed_account_ids`, sem provisionamento de IAM. Execute/aplique primeiro a infraestrutura com esse output publicado.

## Credenciais do banco

O contrato existente de `database_username` e `database_password` foi preservado. `sensitive = true` oculta a senha em algumas saídas do Terraform, mas **não impede sua gravação no Terraform State**, que também contém o argumento `password` do recurso RDS. O acesso ao state deve ser estritamente limitado, com criptografia e locking, e a senha deve ser passada somente por mecanismo secreto.

Como evolução recomendada, avaliar `manage_master_user_password = true`, que delega a geração e armazenamento da senha ao AWS Secrets Manager. A adoção exige validar suporte e permissões no Learner Lab, além de adaptar consumidores (aplicação e Lambda) para ler o secret; por isso não foi ativada nesta alteração nem foi modificado o contrato entre repositórios.

## Proteção contra remoção

`deletion_protection = true` reduz risco de remoção acidental. Quando uma remoção for aprovada, será necessário desabilitar a proteção em alteração explícita e revisar o plano. `skip_final_snapshot = false` exige snapshot final; o identificador configurado pode precisar ser atualizado se já existir um snapshot com o mesmo nome. Nenhum recurso AWS foi alterado nesta revisão.
