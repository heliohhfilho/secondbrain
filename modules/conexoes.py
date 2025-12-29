import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import time

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

def load_gsheet(nome_aba, colunas_padrao):

    time.sleep(2)
    """
    Carrega uma aba específica da planilha. Se não existir, cria.
    Retorna um DataFrame Pandas.
    """
    client = conectar_gsheets()
    
    # Nome da sua planilha no Google (Tem que ser EXATO)
    PLANILHA_NOME = "Life_OS_Database" 
    
    try:
        sh = client.open(PLANILHA_NOME)
    except gspread.SpreadsheetNotFound:
        st.error(f"Não achei a planilha '{PLANILHA_NOME}'. Crie ela no Google e compartilhe com o robô!")
        return pd.DataFrame(columns=colunas_padrao)

    try:
        worksheet = sh.worksheet(nome_aba)
    except gspread.WorksheetNotFound:
        # Se a aba não existe, cria ela com o cabeçalho
        worksheet = sh.add_worksheet(title=nome_aba, rows=1000, cols=20)
        worksheet.append_row(colunas_padrao)
        return pd.DataFrame(columns=colunas_padrao)

    # Lê todos os dados
    dados = worksheet.get_all_records()
    df = pd.DataFrame(dados)
    
    # Se estiver vazio mas tiver cabeçalho, ajusta colunas
    if df.empty:
        return pd.DataFrame(columns=colunas_padrao)
        
    return df

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