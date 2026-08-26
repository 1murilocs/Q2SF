import pandas as pd
import pyodbc 
import sqlite3
import os
import datetime
from simple_salesforce import Salesforce
from sqlalchemy import create_engine
from cfg import SFPASSWORD, SFUSER, SFTOKEN, SERVER, DATABASE, UID, DBPASS

# Início do processo de inserção de apólices no Salesforce
print('\nUpdate:')

# Garante que o CWD seja sempre a pasta Q2SF, independente de onde o script é executado
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Função para remover o banco de dados SQLite local temporário
def removeDatabase():
    try:
        db_path = 'database/q2sf_Update.db'
        if os.path.exists(db_path):
            os.remove(db_path)
            print('\nBanco de dados local (update) removido com sucesso.')
    except Exception as e:
        print(f'\nAviso: Não foi possível remover o banco de dados local: {e}')

# Conexão com o banco de dados SQL Server onde os dados Quiver estão armazenados
conn = pyodbc.connect(
    f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={UID};PWD={DBPASS};TrustServerCertificate=yes;"
)
print('Conexão com o banco de dados SQL Server estabelecida com sucesso.')

# Autenticação no Salesforce para leituras e atualizações
sf = Salesforce(username=SFUSER,password=SFPASSWORD,security_token=SFTOKEN)

cursor = conn.cursor()

# Executa a consulta Quiver e carrega os dados em um DataFrame
with open ("script_queries/query_quiver_update.sql", "r") as f1:
    sql = f1.read()
    
cursor.execute(sql)
rows = cursor.fetchall()

columns = [desc[0] for desc in cursor.description]

df = pd.DataFrame.from_records(rows, columns=columns)
conn.close()

# Salva os dados Quiver localmente em SQLite para uso posterior
os.makedirs('database', exist_ok=True)
sqlite_conn = sqlite3.connect('database/q2sf_Update.db')
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
if sfresults.get('records'):
    df_sf2 = pd.DataFrame(sfresults['records'])
    if 'attributes' in df_sf2.columns:
        df_sf2.drop(columns='attributes', inplace=True)
    df_sf2.rename(columns={'Id': 'OportunidadeApoliceAtual__c', 'PropostaQuiver__c': 'Proposta__c'}, inplace=True)
else:
    df_sf2 = pd.DataFrame(columns=['OportunidadeApoliceAtual__c', 'Proposta__c'])

if sfresults_quote.get('records'):
    df_sf3 = pd.DataFrame(sfresults_quote['records'])
    if 'attributes' in df_sf3.columns:
        df_sf3.drop(columns='attributes', inplace=True)
    df_sf3.rename(columns={'Id': 'Cotacao__c'}, inplace=True)
else:
    df_sf3 = pd.DataFrame(columns=['Cotacao__c'])

# Salva os DataFrames do Salesforce no banco SQLite local
local_engine = create_engine('sqlite:///database/q2sf_Update.db')
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
if 'Status__c' in df_local.columns:
    df_local.loc[df_local['Status__c'].astype(str) == '2', 'Status__c'] = 'Cancelada'

# Excluir OPOs que apresentam mais de um número de apólice distinto para evitar atualizações erradas
if {'OportunidadeApoliceAtual__c', 'Numero_da_Apolice__c'}.issubset(df_local.columns):
    distinct_apolice_counts = df_local.groupby('OportunidadeApoliceAtual__c')['Numero_da_Apolice__c'].nunique()
    ambiguous_opos = distinct_apolice_counts[distinct_apolice_counts > 1].index.tolist()
    if ambiguous_opos:
        print('\nAs seguintes oportunidades têm apólices distintas e serão excluídas da atualização:')
        for opp in ambiguous_opos:
            print(f'  - {opp}')
        df_local = df_local[~df_local['OportunidadeApoliceAtual__c'].isin(ambiguous_opos)]
    
sqlite_conn.close()

# Converte o DataFrame com dados combinados para um formato de dicionário
r_sf = df_local.to_dict('records')

# Função auxiliar para formatar e padronizar valores (remoção de NaNs e ajuste de datas)
def fmt(v, sf=False):
    if pd.isna(v) or str(v).strip().lower() in ('', 'none', 'nan', 'nat'): return ''
    s = str(v).strip()
    # Tenta tratar como número (para campos como Premio_Quiver__c)
    try:
        n = float(s)
        # Retorna sem casas decimais desnecessárias (ex: 1500.0 -> '1500')
        return str(int(n)) if n == int(n) else str(n)
    except (ValueError, OverflowError):
        pass
    # Trata como data (remove parte de hora)
    return s.split('T' if sf else ' ')[0].strip()

# Consulta todas as apólices existentes no Salesforce para comparar antes de atualizar
sf_apolice = sf.query_all(
    "SELECT Id, OportunidadeApoliceAtual__c, Numero_da_Apolice__c, Proposta__c, "
    "Data_de_Emissao__c, Inicio_da_Vigencia__c, Termino_da_Vigencia__c, Cotacao__c, Status__c, Premio_Quiver__c "
    "FROM Apolice__c WHERE OportunidadeApoliceAtual__c != null"
)

# Cria um dicionário com o OportunidadeApoliceAtual__c como chave para busca rápida
apolice_lookup = {
    rec['OportunidadeApoliceAtual__c']: rec
    for rec in sf_apolice['records'] if rec.get('OportunidadeApoliceAtual__c')
}

# Compara os dados locais (Quiver) com os registros do Salesforce
updates = []
unchanged_ids = []
log_entries = {}
campos = ['Numero_da_Apolice__c', 'Proposta__c', 'Data_de_Emissao__c', 'Inicio_da_Vigencia__c', 'Termino_da_Vigencia__c', 'Cotacao__c', 'Status__c', 'Premio_Quiver__c']

for record in r_sf:
    opp_id = record.get('OportunidadeApoliceAtual__c')
    if not opp_id: continue
        
    sf_rec = apolice_lookup.get(opp_id)
    if sf_rec:
        changed_fields = []
        for c in campos:
            new_val = fmt(record.get(c))
            old_val = fmt(sf_rec.get(c), True)
            if new_val != old_val:
                changed_fields.append(f"{c}: DE '{old_val}' PARA '{new_val}'")
                
        if changed_fields:
            update_payload = {'Id': sf_rec['Id']}
            for c in campos:
                new_val = fmt(record.get(c))
                old_val = fmt(sf_rec.get(c), True)
                if new_val != old_val:
                    update_payload[c] = new_val if new_val != '' else None
            
            updates.append(update_payload)
            log_entries[sf_rec['Id']] = f"Apólice ID: {sf_rec['Id']}\n" + "\n".join([f"  - {ch}" for ch in changed_fields]) + "\n"
        else:
            unchanged_ids.append(sf_rec['Id'])
    else:
        print(f"Nenhuma apólice encontrada para OportunidadeApoliceAtual__c {opp_id}.")

if unchanged_ids:
    print(f'\nApólices não alteradas (já atualizadas): {unchanged_ids}')

# Atualização em lote (bulk) no Salesforce e gravação de log local
if updates:
    updates_df = pd.DataFrame(updates)
    updates_clean = updates_df.astype(object).where(pd.notna(updates_df), other=None).to_dict('records')
    results = sf.bulk.Apolice__c.update(updates_clean, batch_size=2000)
    alteradas = [rec['Id'] for rec, res in zip(updates, results) if res.get('success')]
    print(f'\nApólices alteradas com sucesso: {alteradas}')
    
    if alteradas:
        import datetime
        os.makedirs('update logs', exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"update logs/update_log_{timestamp}.log"
        with open(log_filename, 'w', encoding='utf-8') as f_log:
            f_log.write(f"Relatório de Atualização - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n")
            f_log.write("="*50 + "\n\n")
            for sf_id in alteradas:
                if sf_id in log_entries:
                    f_log.write(log_entries[sf_id] + "\n")
        print(f"Log de alterações salvo em: {log_filename}")
else:
    print('\nNão há registros de apólice para atualizar com base nos dados recebidos.')

# Limpeza final: remove o banco SQLite
removeDatabase()    