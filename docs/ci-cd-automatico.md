# Início automático do CD

O workflow de CD recebe `push` em `develop` ou `main`. O gate seleciona `homolog` para `develop` e `production` para `main`, lê `AUTO_CD_ENABLED` no Environment selecionado e aguarda a CI do mesmo repositório, branch e SHA quando a variável tem o valor literal `true`. Ausência da variável desabilita o Plan automático; erro diferente de 404 na consulta ou falha, cancelamento, divergência ou timeout da CI bloqueia o gate. Os jobs fazem checkout do SHA validado.

O gate consulta a API de Actions com permissão de leitura e aguarda até 30 minutos pela CI `RDS CI`. `workflow_dispatch` permite executar Plan sem depender de `AUTO_CD_ENABLED`; o input `apply` tem default `false`. PRs e pushes em `feature/**` executam somente CI. `main` precisa estar protegida.

O caminho automático executa validação e Terraform Plan, sem Apply. A seleção do Environment associa o Plan aos valores do ambiente. Apply exige dispatch com `apply=true`, `TERRAFORM_APPLY_APPROVAL_CONFIGURED=true`, Required reviewers e política de branch correspondentes no Environment `homolog`/`develop` ou `production`/`main`.

A aprovação de um Plan não autoriza Apply. O Apply usa o artifact criptografado do mesmo run e commit e revalida seu conteúdo antes de aplicar. O guard do RDS bloqueia exclusões e substituições.

## Configuração externa

- Para habilitar homologação, configurar `AUTO_CD_ENABLED=true` no Environment `homolog`; para produção, configurar o mesmo nome separadamente em `production`. Variável ausente ou diferente de `true` mantém o ambiente desabilitado.
- Repetir a configuração somente nos repositórios e ambientes que se queira habilitar.
- A configuração exige apenas uma Variable não sensível; não exige Secret novo nem ID de conta. O CD continua reutilizando as configurações AWS, States, criptografia e gates existentes em cada Environment.

Configure as proteções nativas dos Environments e a proteção da branch `main`; o código do workflow não cria essas configurações.
