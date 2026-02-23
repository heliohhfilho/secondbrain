import streamlit as st
import conexoes
import pandas as pd
from statsmodels.tsa.seasonal import seasonal_decompose
import matplotlib.pyplot as plt
from datetime import date

# Configuração inicial da página
st.title("Análise de Sazonalidade de Produtividade")

@st.cache_data
def load_data():
    cols_log = ["Data", "Tipo", "Subtipo", "Valor", "Unidade", "Detalhe"]
    df_log = conexoes.load_gsheet("Log_Produtividade", cols_log)
    
    if not df_log.empty:
        df_log["Valor"] = pd.to_numeric(df_log["Valor"], errors='coerce').fillna(0)
        df_log['Data'] = pd.to_datetime(df_log['Data'], errors='coerce')
        return df_log.dropna(subset=['Data'])
    
    return pd.DataFrame(columns=cols_log)

df = load_data()

if not df.empty:
    # 1. Criação do filtro interativo no Streamlit
    tipos_disponiveis = df['Tipo'].unique()
    tipo_selecionado = st.selectbox("Selecione o Tipo de Atividade:", tipos_disponiveis)
    
    # 2. Filtragem do DataFrame
    df_filtrado = df[df['Tipo'] == tipo_selecionado]
    
    if not df_filtrado.empty:
        # Pega a unidade da primeira linha para fins de display
        unidade_atual = df_filtrado['Unidade'].iloc[0]
        st.write(f"**Analisando:** {tipo_selecionado} (Medido em: {unidade_atual})")
        
        # 3. Agrupamento e Reindexação específicos para o filtro
        df_agrupado = df_filtrado.groupby('Data')['Valor'].sum()
        idx = pd.date_range(start=df_agrupado.index.min(), end=pd.to_datetime(date.today()))
        df_agrupado = df_agrupado.reindex(idx, fill_value=0)

        # A decomposição sazonal exige no mínimo o dobro de observações do período (2 * 7 = 14 dias)
        if len(df_agrupado) >= 14:
            # Período 7 focado no ciclo comportamental semanal
            decomposicao = seasonal_decompose(df_agrupado, model='additive', period=7)
            
            st.subheader(f"Decomposição Completa - {tipo_selecionado}")
            fig = decomposicao.plot()
            fig.set_size_inches(10, 8)
            st.pyplot(fig)

            st.subheader("Componente Sazonal Isolada (Ciclo Semanal)")
            st.line_chart(decomposicao.seasonal)
        else:
            st.warning("Dados insuficientes: O modelo estatístico requer pelo menos 14 dias de intervalo temporal para calcular a sazonalidade semanal.")
    else:
        st.info("Nenhum dado encontrado para este filtro.")
else:
    st.error("Base de dados vazia ou erro de conexão com o Google Sheets.")