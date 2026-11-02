# ADR-001 — PostgreSQL como mecanismo de persistência do AutoFlow

- **Status:** Aceita.
- **Data:** 02/11/2026.
- **Escopo:** mecanismo de persistência, ownership do schema e provisionamento relacional nos repositórios `autoflow-db` e `autoflow`.

## Contexto

O backend Spring Boot configura PostgreSQL, JPA/Hibernate e Flyway. O schema versionado contém relações entre usuários, clientes, veículos, ordens de serviço, orçamentos, reparos, itens e histórico. As migrations usam constraints e funcionalidades específicas do PostgreSQL, incluindo `pg_trgm`/GIN (V37) e índice único parcial (V43). Alguns IDs de catálogo e valores de snapshot não são FKs; não se presume integridade referencial universal.

O Terraform em `autoflow-db` declara Amazon RDS PostgreSQL 17, `db.t3.micro`, 20 GB gp3, subnets privadas, storage criptografado, backup de um dia, snapshot final obrigatório e proteção contra remoção. Não declara Multi-AZ nem Enhanced Monitoring. A configuração local não prova o estado ativo da AWS.

As forças em oposição são compatibilidade relacional e recursos necessários ao schema versus dependência de engine/provedor, necessidade de operar credenciais e States, limites de disponibilidade configurados e custo dependente de uso. Não foi encontrada comparação formal, benchmark ou registro de aprovação da decisão original; a justificativa abaixo explica a arquitetura observada, não inventa sua história.

## Decisão

Manter PostgreSQL como banco relacional gerenciado do AutoFlow, provisionado em Amazon RDS. Manter o schema funcional e suas migrations Flyway no repositório `autoflow`, que é consumido pelo backend; `autoflow-db` é proprietário da infraestrutura RDS e da conectividade, não de uma segunda versão do schema.

Essa combinação preserva o dialecto, os drivers, o mapeamento JPA, consultas e mecanismos declarados nas migrations. O uso de RDS delega a execução do serviço de banco à AWS, mas não transfere à plataforma a responsabilidade da equipe por schema, credenciais, autorização de rede, State, backup/restauração e validação operacional.

## Alternativas consideradas

Análise retrospectiva, sem avaliação quantitativa formal:

| Alternativa | Trade-off específico | Motivo para não adotar |
|---|---|---|
| PostgreSQL em RDS (decisão) | Compatibilidade direta com Flyway/JPA e funcionalidades PostgreSQL usadas; serviço gerenciado reduz operação de host. Mantém dependência AWS, custo e limites da configuração atual, que não declara Multi-AZ. | Configuração atual versionada e compatível com schema e backend. |
| MySQL/Aurora MySQL | Mantém SQL relacional, mas não oferece substituto direto para `pg_trgm` com GIN. V37 indexa `lower(numero_os)`, `lower(cliente_nome)` e `lower(cliente_cpf_cnpj)` para buscas com `LIKE '%termo%'`; `FULLTEXT` indexa tokens e não preserva por si só essa busca por fragmento. V43 usa índice único parcial em coluna nullable; um índice único comum pode preservar a regra de múltiplos `NULL` no MySQL, mas a migration/semântica precisa ser convertida e confirmada. | O motivo principal é a incompatibilidade de mecanismo para as buscas por fragmentos: seria necessário redesenhar o índice/consulta ou aceitar outra semântica, testar resultados e avaliar o desempenho com dados reais. Também devem ser convertidos DDL, funções e migrations do dialecto. Não há implementação/testes de portabilidade nem benefício medido que justifique esse trabalho; não se afirma que MySQL seja incapaz de modelar o restante do schema relacional. |
| NoSQL, como DynamoDB | Pode atender modelo orientado a chave e padrões de consulta específicos; o schema atual depende de relações, SQL, constraints e transações. Remodelaria consultas, consistência, índices e gravações. | Não corresponde ao modelo e às migrations presentes; não há workload/benchmark justificando remodelagem. |
| PostgreSQL autogerenciado | Maior controle de host, extensões e parâmetros; transfere patching, backups, monitoramento, capacidade e recuperação à equipe. | O Terraform declara RDS e não há necessidade versionada de gerir host próprio. |
| Schema sob ownership do Terraform de banco | Centralizaria artefatos próximos ao RDS; acoplaria mudanças funcionais ao lifecycle de infraestrutura e criaria segunda fonte de migrations. | Flyway no backend já é a fonte de evolução do schema; não se deve duplicar seu ownership. |

## Consequências positivas

- Preserva a compatibilidade direta com engine, driver, JPA, consultas e migrations atuais.
- Permite declarar FKs, constraints, índices e transações quando explicitamente modelados nas migrations.
- Separa lifecycle do RDS da evolução funcional do schema sem criar autoridade concorrente.
- RDS fornece a execução gerenciada do serviço, enquanto a infraestrutura permanece revisável em Terraform.

## Consequências negativas e limites

- O sistema continua dependente de PostgreSQL e da AWS; outra engine exigiria migração e testes de compatibilidade.
- A classe `db.t3.micro`, 20 GB, retenção de backup de um dia e ausência de Multi-AZ limitam o que se pode afirmar sobre capacidade e disponibilidade.
- Storage criptografado, snapshot final e deletion protection são declarações; não comprovam restore, durabilidade operacional ou configuração ativa.
- A equipe mantém responsabilidade por schema, migrações, tuning, credenciais, acesso ao State e validação de recuperação.
- IDs de catálogo sem FK e snapshots não recebem garantias de integridade que não estejam declaradas nas migrations.

## Riscos e mitigação

| Risco | Mitigação/limite |
|---|---|
| Migration incompatível com versão de código ou dados | Nova migration Flyway, revisão de compatibilidade, testes com PostgreSQL e promoção coordenada; não editar migration aplicada. |
| Confiança excessiva em FKs ou cardinalidade | Usar migrations como fonte da verdade e revisar cada coluna; o diagrama documenta exceções como IDs escalares e snapshots. |
| Exposição de senha em State/Plan/runtime | Proteger IAM e artefatos; `sensitive` mascara determinadas saídas, mas não remove valores do State. Rotação e cifragem efetivas não são inferidas da configuração local. |
| Falha de banco ou recuperação não comprovada | Preservar snapshot final e deletion protection; definir e executar restauração/RPO/RTO em trabalho operacional autorizado. |
| Dimensionamento/custo inadequado | Observar métricas e cobrança na conta antes de alterar classe, storage ou topologia; nenhum benchmark ou custo foi medido. |

## Referências

- [RFC-001 — PostgreSQL e estratégia de persistência](../RFC-001.md)
- [README do repositório de banco](../../README.md)
- [`infra/rds-postgresql.tf`](../../infra/rds-postgresql.tf) e [`infra/sg.tf`](../../infra/sg.tf)
- [Migrations Flyway do backend](https://github.com/autoflow-fiap/autoflow/tree/develop/backend/src/main/resources/db/migration)
- [Migration V37 — índices PostgreSQL](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/src/main/resources/db/migration/V37__add_ordem_servico_listing_indexes.sql)
- [Migration V43 — índice único parcial](https://github.com/autoflow-fiap/autoflow/blob/develop/backend/src/main/resources/db/migration/V43__protect_reparo_adicional_relationships.sql)
- [Diagrama ER](../diagrama-er.md)
