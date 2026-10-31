# Início automático do CD

O workflow de CD recebe `push` em `develop` ou `main`. O gate valida a origem, branch e SHA do push, seleciona `homolog` para `develop` e `production` para `main`, e lê a Repository Variable correspondente pelo contexto `vars`. Somente o valor literal `true` habilita o Plan automático; variável ausente ou diferente desabilita esse caminho. Quando habilitado, o gate aguarda sucesso da CI `RDS CI` para o mesmo repositório, branch e SHA; falha, cancelamento, divergência ou timeout bloqueia o Plan. Os jobs fazem checkout do SHA validado.

O gate consulta a API de Actions com permissão de leitura e aguarda até 30 minutos pela CI `RDS CI`; não consulta a API administrativa de Environments para ler as flags. `workflow_dispatch` permite executar Plan sem depender das Repository Variables; o input `apply` tem default `false`. PRs e pushes em `feature/**` executam somente CI. `main` precisa estar protegida.

O caminho automático executa validação e Terraform Plan, sem Apply. A seleção do Environment associa o Plan aos valores do ambiente. Apply exige dispatch com `apply=true`, `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`, Required reviewers e política de branch correspondentes no Environment `homolog`/`develop` ou `production`/`main`.

A aprovação de um Plan não autoriza Apply. O Apply usa o artifact criptografado do mesmo run e commit e revalida seu conteúdo antes de aplicar. O guard do RDS bloqueia exclusões e substituições.

## Configuração externa

- Para habilitar Plan automático em homologação, definir a Repository Variable `AUTO_CD_ENABLED_HOMOLOG=true`; em produção, definir separadamente `AUTO_CD_ENABLED_PRODUCTION=true`. Variável ausente ou diferente de `true` mantém o respectivo ambiente desabilitado.
- Repetir a configuração somente nos repositórios cujo CD automático se queira habilitar.
- As flags são Repository Variables não sensíveis e não exigem Secret novo nem ID de conta. O CD continua reutilizando as configurações AWS, States, criptografia e gates existentes em cada Environment.

Configure as proteções nativas dos Environments e a proteção da branch `main`; o código do workflow não cria essas configurações.
