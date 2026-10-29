# Diagrama ER do AutoFlow

O diagrama representa as relações relacionais declaradas nas migrations Flyway do backend e o mapeamento JPA atual. Campos de identificador que não possuem chave estrangeira não são desenhados como relacionamentos.

```mermaid
erDiagram
    USUARIOS {
        BIGINT id PK
        VARCHAR email
        VARCHAR cpf_cnpj
        VARCHAR senha
        VARCHAR role
    }
    CLIENTES {
        BIGINT id PK
        BIGINT usuario_id FK
        VARCHAR nome
        VARCHAR cpf_cnpj
        VARCHAR telefone
        VARCHAR email
        VARCHAR status
    }
    VEICULOS {
        BIGINT id PK
        BIGINT cliente_id FK
        VARCHAR marca
        VARCHAR modelo
        INTEGER ano
        VARCHAR placa
    }
    SERVICOS {
        BIGINT id PK
        VARCHAR nome
        NUMERIC valor
        VARCHAR descricao
        BOOLEAN ativo
    }
    PECAS_INSUMOS {
        BIGINT id PK
        VARCHAR nome
        INTEGER quantidade
        NUMERIC valor
        VARCHAR tipo
    }
    ORDEM_SERVICO {
        BIGINT id PK
        VARCHAR numero_os
        BIGINT cliente_id
        VARCHAR cliente_nome
        VARCHAR cliente_cpf_cnpj
        VARCHAR cliente_email
        VARCHAR cliente_telefone
        BIGINT veiculo_id FK
        BIGINT diagnostico_mecanico_id FK
        VARCHAR status
        TIMESTAMP data_abertura
    }
    ORDEM_SERVICO_STATUS_HISTORICO {
        BIGINT id PK
        BIGINT ordem_servico_id FK
        VARCHAR numero_os
        VARCHAR status
        TIMESTAMP registrado_em
    }
    ORDEM_SERVICO_SERVICO_SOLICITADO {
        BIGINT id PK
        BIGINT servico_id
        BIGINT ordem_servico_id FK
        BIGINT reparo_adicional_id FK
        VARCHAR nome
        NUMERIC valor
        VARCHAR status
    }
    ORDEM_SERVICO_SERVICO_ITEM_NECESSARIO {
        BIGINT servico_solicitado_id FK
        INTEGER ordem
        BIGINT peca_insumo_id
        VARCHAR nome
        VARCHAR tipo
        NUMERIC valor_unitario
        INTEGER quantidade
    }
    REPARO_ADICIONAL {
        BIGINT id PK
        BIGINT ordem_servico_id FK
        BIGINT mecanico_id FK
        BIGINT orcamento_id FK
        VARCHAR status
        TIMESTAMP criado_em
    }
    ORCAMENTO {
        BIGINT id PK
        BIGINT ordem_servico_id FK
        VARCHAR numero_os
        VARCHAR tipo
        INTEGER versao
        VARCHAR status
        VARCHAR cliente_nome_snapshot
        VARCHAR veiculo_placa_snapshot
    }
    ORCAMENTO_SERVICO_ITEM {
        BIGINT orcamento_id FK
        INTEGER ordem
        BIGINT servico_id
        VARCHAR nome
        NUMERIC valor
    }
    ORCAMENTO_ITEM_NECESSARIO_ITEM {
        BIGINT orcamento_id FK
        INTEGER ordem
        BIGINT peca_insumo_id
        BIGINT servico_os_id
        VARCHAR nome
        NUMERIC valor_total
    }
    NOTIFICACAO {
        BIGINT id PK
        BIGINT orcamento_id
        BIGINT cliente_id
        VARCHAR canal
        VARCHAR destinatario
        VARCHAR status
        TIMESTAMP criada_em
    }

    USUARIOS o|--o{ CLIENTES : usuario_id
    CLIENTES ||--o{ VEICULOS : cliente_id
    VEICULOS ||--o{ ORDEM_SERVICO : veiculo_id
    USUARIOS o|--o{ ORDEM_SERVICO : diagnostico_mecanico_id
    ORDEM_SERVICO ||--o{ ORDEM_SERVICO_STATUS_HISTORICO : ordem_servico_id
    ORDEM_SERVICO o|--o{ ORDEM_SERVICO_SERVICO_SOLICITADO : ordem_servico_id
    REPARO_ADICIONAL o|--o{ ORDEM_SERVICO_SERVICO_SOLICITADO : reparo_adicional_id
    ORDEM_SERVICO_SERVICO_SOLICITADO ||--o{ ORDEM_SERVICO_SERVICO_ITEM_NECESSARIO : servico_solicitado_id
    ORDEM_SERVICO ||--o{ REPARO_ADICIONAL : ordem_servico_id
    USUARIOS ||--o{ REPARO_ADICIONAL : mecanico_id
    ORCAMENTO o|--o| REPARO_ADICIONAL : orcamento_id
    ORDEM_SERVICO ||--o{ ORCAMENTO : ordem_servico_id
    ORCAMENTO ||--o{ ORCAMENTO_SERVICO_ITEM : orcamento_id
    ORCAMENTO ||--o{ ORCAMENTO_ITEM_NECESSARIO_ITEM : orcamento_id
```

## Relacionamentos e decisões de persistência

- `clientes.usuario_id` é uma FK opcional em V5, e a entidade Java usa `@OneToOne`. V5 não declara constraint `UNIQUE` para essa coluna; a cardinalidade permitida pela migration pode ser mais ampla que o mapeamento JPA.
- Cada veículo tem `cliente_id` obrigatório e FK para `clientes` em V1. A entidade Java usa `@ManyToOne`, mas não declara `nullable = false`; o diagrama segue a obrigatoriedade do schema Flyway.
- Cada ordem referencia obrigatoriamente um veículo e, opcionalmente, o mecânico do diagnóstico. V10 remove a FK de `ordem_servico.cliente_id` e adiciona os campos de cliente copiados como snapshot; portanto, esse `cliente_id` não é relação vigente com `clientes`.
- O histórico de status referencia a ordem por FK (V17). `HistoricoStatusOsEntity` representa o identificador como campo escalar, embora o schema mantenha a integridade referencial.
- Um serviço solicitado pode pertencer a uma ordem ou a um reparo adicional; os dois vínculos são opcionais no banco. Seus itens necessários são armazenados na tabela de coleção ligada ao serviço solicitado. `servico_id` e `peca_insumo_id` são identificadores sem FK para o catálogo.
- Reparo adicional referencia obrigatoriamente uma ordem e um mecânico. `orcamento_id` é opcional e tem índice único parcial (V43), limitando a associação a um orçamento por reparo e vice-versa.
- Orçamento referencia obrigatoriamente uma ordem. Os serviços e itens do orçamento ficam em tabelas de coleção ligadas ao orçamento; os dados de cliente e veículo são snapshots. Os campos `servico_id`, `peca_insumo_id` e `servico_os_id` nessas coleções não são FKs.
- `notificacao.orcamento_id` e `notificacao.cliente_id` não possuem FKs nas migrations; por isso o diagrama não representa essas colunas como relacionamentos.

As migrations V49 e V50 da aplicação alteram documentos de registros demonstrativos já existentes, sem modificar tabelas, colunas ou relacionamentos. A V49 também sincroniza um valor de documento armazenado no snapshot da ordem; a V50 atualiza documentos de usuários demonstrativos. A confirmação dessas migrations no RDS depende de consulta autorizada ao histórico Flyway após recriar a infraestrutura.
