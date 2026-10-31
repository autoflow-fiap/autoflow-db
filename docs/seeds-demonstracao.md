# Dados sintéticos de demonstração

As migrations Flyway do schema e dos dados demonstrativos pertencem ao backend em
[`autoflow`](https://github.com/autoflow-fiap/autoflow/tree/develop/backend/src/main/resources/db/migration). Este
repositório provisiona o RDS e não executa nem promove migrations da aplicação.

| Migration | Escopo |
|---|---|
| V49 — clientes de demonstração | Sincroniza documentos sintéticos dos usuários/clientes `CLIENTE` e os snapshots das ordens de serviço associadas. Valida presença, vínculos e unicidade antes das alterações. |
| V50 — equipe de demonstração | Sincroniza documentos sintéticos de usuários `MECANICO` e `ATENDENTE`. |

V49 preserva IDs, vínculos, ordens e históricos. Colisões, seeds ausentes ou vínculos divergentes interrompem a migration
antes da alteração dos dados. `migrations/V49__corrigir_documentos_seeds_demo.sql` é uma cópia de referência;
Flyway executa a versão mantida no repositório `autoflow`.

## Autenticação de clientes

A Lambda recebe `cpf_cnpj` e `senha`, normaliza e valida CPF/CNPJ, verifica a senha com BCrypt e consulta
`usuarios.cpf_cnpj`. Para o perfil `CLIENTE`, exige cliente relacionado com o mesmo documento e status `ATIVO`. Os testes
locais usam credenciais sintéticas; documentos e senhas não são publicados nesta documentação.

## Testes locais

Os testes unitários executam sem banco:

```bash
python -m unittest discover -s tests -v
```

Para validar também constraints e sincronização em PostgreSQL descartável, defina `TEST_DATABASE_URL` localmente para
esse banco e execute o mesmo comando. O teste não deve apontar a ambientes compartilhados.
