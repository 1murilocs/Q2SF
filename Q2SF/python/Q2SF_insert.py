import os, sys, datetime, pyodbc, sqlite3
import pandas as pd
from cfg import SFPASSWORD, SFUSER, SFTOKEN, SERVER, DATABASE, UID, DBPASS
from simple_salesforce import Salesforce
from sqlalchemy import create_engine

# Adiciona a pasta email ao path, pois ela fica fora da pasta python/
external = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'envio_emails'))
if external not in sys.path:
    sys.path.append(external)
# pyrefly: ignore [missing-import]
from emails import send_email

# Muda o diretório de trabalho para o diretório raiz do projeto
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def removeDatabase():
    # Remove o banco de dados SQLite temporário criado para esta execução
    try:
        db_path = 'database/q2sf_Insert.db'
        if os.path.exists(db_path):
            os.remove(db_path)
            print('\nBanco de dados local (insert) removido com sucesso.\n')
    except Exception as e:
        print(f'\nAviso: Não foi possível remover o banco de dados local: {e}')

def main():


    removeDatabase()
    

    # Início do processo de inserção de apólices no Salesforce
    print('Insert:')

    # Conexão com o banco de dados SQL Server onde os dados Quiver estão armazenados
    conn = pyodbc.connect(
        f"DRIVER={{ODBC Driver 18 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};UID={UID};PWD={DBPASS};TrustServerCertificate=yes;"
    )
    print('Conexão com o banco de dados SQL Server estabelecida com sucesso.')

    try:
        # Autenticação no Salesforce para leituras e inserções
        sf = Salesforce(username=SFUSER,password=SFPASSWORD,security_token=SFTOKEN)

        cursor = conn.cursor()

        # Executa a consulta Quiver e carrega os dados em um DataFrame
        with open ("script_queries/query_quiver.sql", "r") as f1:
            sql = f1.read()

        cursor.execute(sql)
        rows = cursor.fetchall()

        columns = [desc[0] for desc in cursor.description]

        df = pd.DataFrame.from_records(rows, columns=columns)
    finally:
        conn.close()

    # Salva os dados Quiver localmente em SQLite para uso posterior
    sqlite_conn = sqlite3.connect('database/q2sf_Insert.db')
    try:
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
        df_sf2.rename(columns={'Id': 'OportunidadeApoliceAtual__c'}, inplace=True)
        df_sf2.rename(columns={'PropostaQuiver__c': 'Proposta__c'}, inplace=True)
        df_sf3.rename(columns={'Id': 'Cotacao__c'}, inplace=True)
        local_engine = create_engine('sqlite:///database/q2sf_Insert.db')
        try:
            df_sf2.to_sql("sf_opp", con=local_engine, if_exists='replace', index=False)
            df_sf3.to_sql("sf_quote", con=local_engine, if_exists='replace', index=False)
            print('\nDados do Salesforce inseridos no banco de dados SQLite com sucesso.')
        finally:
            local_engine.dispose()

        # Executa a consulta final local que combina dados Quiver e Salesforce
        with open('test_queries/execute.sql', 'r') as f4:
            execute_query = f4.read()

        df_local = pd.read_sql_query(execute_query, sqlite_conn)
        print('\nConsulta SQL executada no banco local com sucesso.')

        # Ajusta o status para texto quando necessário
        df_local['Status__c'] = df_local['Status__c'].replace('1','Ativa')
    finally:
        sqlite_conn.close()

    # Prepara lista de IDs de oportunidades válidos para validação no Salesforce
    opp_ids = df_local['OportunidadeApoliceAtual__c'].replace('', pd.NA).dropna().unique().tolist()

    df_sem_beneficios = df_local[(df_local['Area_Formula__c'] != 'BENEFICIOS') & (df_local['Status__c'] == 'Ativa')]

    distinct_apolice_count = df_sem_beneficios.groupby('OportunidadeApoliceAtual__c')['Numero_da_Apolice__c'].nunique()
    ambiguous_opo = distinct_apolice_count[distinct_apolice_count > 1].index.tolist()

    if ambiguous_opo:
        os.makedirs('insert_logs', exist_ok=True)
        log_filename = 'insert_logs/apolices_distintas.log'

        # Transforma a lista de oportunidades ambíguas em uma string formatada para o filtro da query SOQL
        ids = ", ".join(f"'{opp}'" for opp in ambiguous_opo)
        query = sf.query_all(f"SELECT Id, Numero_da_Oportunidade__c, PropostaQuiver__c, Area_Formula__c, Name from Opportunity where Id IN ({ids})")

        # Inicia a lista de linhas do log com a data/hora e uma mensagem explicando o problema
        linhas = [f'Data: {datetime.datetime.now()}',
                  'As seguintes oportunidades tem apólices distintas no QUIVER contendo a mesma proposta:']

        # Adiciona uma linha na lista para cada oportunidade ambígua retornada pela query SOQL, com o link direto no Salesforce
        linhas += [f"- https://galcorr.lightning.force.com/lightning/r/Opportunity/{r['Id']}/view - {r['Area_Formula__c']} - {r['Numero_da_Oportunidade__c']} "
                   for r in query['records']]

        linhas.append('Acesse os links acima para verificar as "OPO" no Salesforce e realizar as mudanças necessárias nas propostas do Quiver.')

        # Acessando o arquivo de log como write e escrevendo as linhas nele
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write('\n'.join(linhas) + '\n')

        print(f"\nLog de Oportunidades com Números de Apólice Distintos salvo em: {log_filename}")

        # Envia por e-mail o alerta com as oportunidades ambíguas encontradas nessa execução
        send_email()
    else:
        print("\nNenhuma oportunidade com apólices distintas encontrada.\n")
        
    #Verifica se já existem apólices no Salesforce para essas oportunidades
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
        # Remove colunas auxiliares que não existem no objeto Apolice__c do Salesforce
        cols_to_drop = [c for c in ['Area_Formula__c'] if c in df_new.columns]
        df_insert = df_new.drop(columns=cols_to_drop)
        r_sf = df_insert.astype(object).where(pd.notna(df_insert), other=None).to_dict('records')
        results = sf.bulk.Apolice__c.insert(
            r_sf,
            batch_size=2000)
        print('\nRegistros inseridos no Salesforce com sucesso.')
        print(results)
    else:
        print('\nNão há novas oportunidades para inserir apólice no Salesforce.')
main()