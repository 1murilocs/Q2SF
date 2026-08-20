# Retorno de Dados (Quiver to Salesforce)

Projeto para extração e conciliação de dados de apólices / propostas do Quiver com o Salesforce, usando banco de dados local `SQLite`, `Pandas`, `pyodbc`, `simple-salesforce` e `SQLAlchemy`.

## Descrição

O projeto conecta ao Salesforce e ao banco de dados Quiver para:

- extrair dados de apólices e propostas do Quiver;
- buscar dados de oportunidades e cotações no Salesforce;
- conciliar os dados localmente em SQLite;
- inserir novas apólices no Salesforce (`Q2SF_insert.py`);
- atualizar apólices existentes no Salesforce (`Q2SF_update.py`).

## Organização / Estrutura de Arquivos

database/ - banco de dados SQLite temporário usado nas execuções de insert e update.

insert_logs/ - logs gerados pelo `Q2SF_insert.py` quando são encontradas oportunidades com apólices distintas no Quiver.

notebook/
├── Q2SF_insert_notebook.ipynb - notebook de análise / desenvolvimento do fluxo de insert.
└── Q2SF_update_notebook.ipynb - notebook de análise / desenvolvimento do fluxo de update.

python/
├── Q2SF_insert.py - script para inserir apólices novas no Salesforce.
├── Q2SF_update.py - script para atualizar apólices existentes no Salesforce.
└── test_log.py - script auxiliar que gera logs em `update logs/`.

script_queries/
├── query_quiver.sql - query Quiver para insert.
├── query_quiver_update.sql - query Quiver para update.
├── query_sf_quote.sql - query SOQL para cotações no Salesforce.
└── query_sf.sql - query SOQL para oportunidades no Salesforce.

test_queries/
└── execute.sql - query local que combina dados do Quiver e do Salesforce para insert/update.

update logs/ - logs de atualização gerados pelo `Q2SF_update.py`.

## Bibliotecas

- pandas
- pyodbc
- sqlite3
- simple-salesforce
- sqlalchemy
- os
- datetime

## Uso

1. Configure as conexões do Salesforce e do banco de dados Quiver em `python/Q2SF_insert.py` e `python/Q2SF_update.py`.
2. Ajuste `script_queries/query_quiver.sql` e `script_queries/query_quiver_update.sql` conforme os dados desejados do Quiver.
3. Execute `python python/Q2SF_insert.py` para inserir apólices novas.
4. Execute `python python/Q2SF_update.py` para atualizar apólices existentes.

## Logs

- `insert_logs/apolices_distintas.log` - gerado pelo `Q2SF_insert.py` quando há oportunidades com apólices distintas no Quiver.
- `update logs/update_log_<timestamp>.log` - gerado pelo `Q2SF_update.py` com as atualizações aplicadas no Salesforce.

## Observações

- Os scripts usam queries separadas para Quiver e Salesforce.
- O banco SQLite local é criado em `database/` durante a execução.
- O `Q2SF_update.py` remove o banco SQLite temporário ao final do processo.
- Ajuste os campos conforme a estrutura atual do Salesforce e do Quiver quando necessário.
