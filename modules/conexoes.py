import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from requests.exceptions import ConnectionError, ReadTimeout
import time

PLANILHA_NOME = "Life_OS_Database"

# Cache para não reconectar toda hora
@st.cache_resource
def conectar_gsheets():
    # Pega as credenciais dos secrets do Streamlit
    credentials_dict = st.secrets["gcp_service_account"]
    
    # Escopos necessários
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
    client = gspread.authorize(creds)
    return client

# Em modules/conexoes.py

def load_gsheet(aba, cols_esperadas):
    """
    Carrega dados da aba com tratamento de erro de conexão e retentativas.
    """

    client = conectar_gsheets()
    max_retries = 3
    wait_seconds = 2
    
    for attempt in range(max_retries):
        try:
            # 1. Tenta abrir a planilha (Onde seu erro estava acontecendo)
            sh = client.open(PLANILHA_NOME)
            
            # 2. Tenta selecionar a aba
            worksheet = sh.worksheet(aba)
            
            # 3. Pega os dados
            data = worksheet.get_all_records()
            
            # 4. Converte para DataFrame
            df = pd.DataFrame(data)
            
            # 5. Garante que as colunas existam mesmo se a planilha estiver vazia
            if df.empty:
                return pd.DataFrame(columns=cols_esperadas)
            
            # Filtra apenas colunas que queremos (se existirem)
            cols_existentes = [c for c in cols_esperadas if c in df.columns]
            return df[cols_existentes]

        except (ConnectionError, ReadTimeout, gspread.exceptions.APIError) as e:
            # Se for a última tentativa, não tem o que fazer, deixa o erro subir
            if attempt == max_retries - 1:
                print(f"❌ Erro fatal ao ler '{aba}': {e}")
                # Retorna um DF vazio para o app não quebrar totalmente, ou você pode dar 'raise e'
                return pd.DataFrame(columns=cols_esperadas) 
            
            print(f"⚠️ Erro de conexão ao ler '{aba}'. Tentando de novo em {wait_seconds}s... ({attempt+1}/{max_retries})")
            time.sleep(wait_seconds)
            wait_seconds *= 2 # Backoff exponencial (espera 2s, depois 4s...)
            
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existe, cria um DF vazio e não tenta de novo (erro lógico, não de conexão)
            print(f"⚠️ Aba '{aba}' não encontrada. Retornando vazio.")
            return pd.DataFrame(columns=cols_esperadas)

def save_gsheet(nome_aba, df):
    """
    Salva o DataFrame na aba específica (Sobrescreve tudo para garantir consistência).
    Nota: Para grandes volumes, o ideal é usar append, mas para uso pessoal isso é mais seguro.
    """
    client = conectar_gsheets()
    PLANILHA_NOME = "Life_OS_Database"
    sh = client.open(PLANILHA_NOME)
    worksheet = sh.worksheet(nome_aba)
    
    # Limpa tudo
    worksheet.clear()
    
    # Reescreve cabeçalho e dados
    # set_with_dataframe do gspread-dataframe é melhor, mas vamos usar lista pura para não adicionar lib
    cabecalho = df.columns.tolist()
    linhas = df.astype(str).values.tolist() # Converte tudo pra texto para evitar erro de JSON
    
    # Atualiza em lote (Batch Update) - Mais rápido
    worksheet.update([cabecalho] + linhas)