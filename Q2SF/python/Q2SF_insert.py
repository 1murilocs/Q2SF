import datetime
import os
import sys
import pandas as pd
import pyodbc 
import sqlite3
from cfg import SFPASSWORD, SFUSER, SFTOKEN, SERVER, DATABASE, UID, DBPASS
from simple_salesforce import Salesforce
from sqlalchemy import create_engine

# Início do processo de inserção de apólices no Salesforce
print('Insert:')

# Garante que o CWD seja sempre a pasta Q2SF, independente de onde o script é executado
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def removeDatabase():
    # Remove o banco de dados SQLite temporário criado para esta execução
    os.remove('database/q2sf_Insert.db')
    print('\nBanco de dados local (insert) removido com sucesso.\n')

# Conexão com o banco de dados SQL Server onde os dados Quiver estão armazenados
conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={UID};PWD={DBPASS};TrustServerCertificate=yes;"
)
print('Conexão com o banco de dados SQL Server estabelecida com sucesso.')

# Autenticação no Salesforce para leituras e inserções
sf = Salesforce(username=SFUSER,password=SFPASSWORD,security_token=SFTOKEN)

cursor = conn.cursor()
DISTAP = []

# Executa a consulta Quiver e carrega os dados em um DataFrame
with open ("script_queries/query_quiver.sql", "r") as f1:
    sql = f1.read()
    
cursor.execute(sql)
rows = cursor.fetchall()

columns = [desc[0] for desc in cursor.description]

df = pd.DataFrame.from_records(rows, columns=columns)
conn.close()

# Salva os dados Quiver localmente em SQLite para uso posterior
sqlite_conn = sqlite3.connect('database/q2sf_Insert.db')
df.to_sql('quiver', sqlite_conn, if_exists='replace', index=False)
print('\nDados da tabela Quiver inseridos no banco de dados SQLite com sucesso.')
# Consulta registros de oportunidade e cotação no Salesforce
with open('script_queries/query_sf.sql', 'r') as f2:
    soql_query = f2.read()
    
sfresults = sf.query_all(soql_query)

with open('script_queries/query_sf_quote.sql', 'r') as f3:
    soql_query_quote = f3.read()

sfresults_quote = sf.query_all(soql_query_quote)

# Converte resultados do Salesforce em DataFrames e ajusta nomes de colunas
df_sf2 = pd.DataFrame(sfresults['records']).drop(columns='attributes')
df_sf3 = pd.DataFrame(sfresults_quote['records']).drop(columns='attributes')
df_sf2.rename(columns={'Id': 'OportunidadeApoliceAtual__c'})
df_sf2.rename(columns={'PropostaQuiver__c': 'Proposta__c'})
df_sf3.rename(columns={'Id': 'Cotacao__c'})
local_engine = create_engine('sqlite:///database/q2sf_Insert.db')
df_sf2.to_sql("sf_opp", con=local_engine, if_exists='replace', index=False)
df_sf3.to_sql("sf_quote", con=local_engine, if_exists='replace', index=False)
print('\nDados do Salesforce inseridos no banco de dados SQLite com sucesso.')
local_engine.dispose()

# Executa a consulta final local que combina dados Quiver e Salesforce
with open('test_queries/execute.sql', 'r') as f4:
    execute_query = f4.read()
    
df_local = pd.read_sql_query(execute_query, sqlite_conn)
print('\nConsulta SQL executada no banco local com sucesso.')

# Ajusta o status para texto quando necessário
if 'Status__c' in df_local.columns:
    df_local.loc[df_local['Status__c'].astype(str) == '1', 'Status__c'] = 'Ativa'

# Excluir OPOs que apresentam mais de um número de apólice distinto
if {'OportunidadeApoliceAtual__c', 'Numero_da_Apolice__c'}.issubset(df_local.columns):
    distinct_apolice_counts = df_local.groupby('OportunidadeApoliceAtual__c')['Numero_da_Apolice__c'].nunique()
    ambiguous_opos = distinct_apolice_counts[distinct_apolice_counts > 1].index.tolist()
    if ambiguous_opos:
        os.makedirs('insert_logs', exist_ok=True)
        log_filename = 'insert_logs/apolices_distintas.log'
        with open(log_filename, 'w') as f:
            f.write(f'Data: {datetime.datetime.now()}\n')
            f.write('As seguintes oportunidades tem apólices distintas NO QUIVER contendo a mesma proposta:\n')
            for opp in ambiguous_opos:
                DISTAP.append(opp)
            ids = ",".join(f"'{item}'" for item in DISTAP)
            query = sf.query_all(f"SELECT Id, Numero_da_Oportunidade__c, PropostaQuiver__c, Area_Formula__c, Name FROM Opportunity WHERE Id IN ({ids})")
            for row in query['records']:
                f.write(f"  - https://galcorr.lightning.force.com/lightning/r/Opportunity/{row['Id']}/view - {row['Area_Formula__c']} - {row['Numero_da_Oportunidade__c']}\n")
            f.write('Acesse os links acima para verificar as "OPO" no Salesforce e realizar as mudanças necessárias nas propostas do Quiver.\n')
        print(f"\nLog de Oportunidades com Números de Apólice Distintos salvo em: {log_filename}:")
        df_local = df_local[~df_local['OportunidadeApoliceAtual__c'].isin(ambiguous_opos)]

sqlite_conn.close()

# Prepara lista de IDs de oportunidades válidos para validação no Salesforce
opp_ids = df_local['OportunidadeApoliceAtual__c'].replace('', pd.NA).dropna().unique().tolist()

# Verifica se já existem apólices no Salesforce para essas oportunidades
existing_ids = set()
if opp_ids:
    batch_size = 2000
    for i in range(0, len(opp_ids), batch_size):
        batch = opp_ids[i:i + batch_size]
        ids_str = "','".join(batch)
        q2 = f"SELECT OportunidadeApoliceAtual__c FROM Apolice__c WHERE OportunidadeApoliceAtual__c IN ('{ids_str}')"
        result = sf.query_all(q2)['records']
        existing_ids.update([r['OportunidadeApoliceAtual__c'] for r in result])
df_new = df_local[~df_local['OportunidadeApoliceAtual__c'].isin(existing_ids)]

# Mostra oportunidades que já têm apólices no Salesforce
if existing_ids:
    print('\nAs seguintes oportunidades já possuem Apólice no Salesforce:')
    for i in existing_ids:
        print(f"  - {i}")

# Inserção em lote das apólices novas no Salesforce
if not df_new.empty:
    r_sf = df_new.astype(object).where(pd.notna(df_new), other=None).to_dict('records')
    results = sf.bulk.Apolice__c.insert(
        r_sf,
        batch_size=2000)
    print('\nRegistros inseridos no Salesforce com sucesso.')
    print(results)
else:
    print('\nNão há novas oportunidades para inserir apólice no Salesforce.')
    
removeDatabase()

external = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'envio_emails'))
if external not in sys.path:
    sys.path.append(external)
# pyrefly: ignore [missing-import]
from emails import send_email

send_email()