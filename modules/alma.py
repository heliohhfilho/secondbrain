import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date
import os
import random
from modules import conexoes # <--- Importa o conector que criamos

# --- CITAÇÕES PARA INSPIRAÇÃO ---
QUOTES = [
    "A paz vem de dentro. Não a procure fora. - Buda",
    "O que você pensa, você se torna. - Buda",
    "A alma é tingida pela cor dos seus pensamentos. - Marco Aurélio",
    "Não se amoldem ao padrão deste mundo, mas transformem-se pela renovação da sua mente. - Romanos 12:2",
    "A felicidade da sua vida depende da qualidade dos seus pensamentos. - Marco Aurélio",
    "Conhece-te a ti mesmo. - Sócrates",
    "A gratidão transforma o que temos em suficiente. - Melodie Beattie",
    "Tudo o que te irrita nos outros pode te levar a uma compreensão de ti mesmo. - Carl Jung"
]

def load_data():
    # Define as colunas padrão para o Google Sheets
    cols = [
        "Data", "Gratidao_1", "Gratidao_2", "Gratidao_3", 
        "Emocao_Dominante", "Nivel_Paz_0_10", "Diario_Reflexao"
    ]
    # Carrega da nuvem
    df = conexoes.load_gsheet("Alma", cols)
    
    # Saneamento: garante que Nivel_Paz seja numérico
    if not df.empty:
        df["Nivel_Paz_0_10"] = pd.to_numeric(df["Nivel_Paz_0_10"], errors='coerce').fillna(5)
    
    return df

def save_data(df):
    # Salva na nuvem (aba "Alma")
    conexoes.save_gsheet("Alma", df)

def render_page():
    st.header("🕊️ Santuário: Cuidando da Alma")
    
    # --- CITAÇÃO DO DIA (RANDOM) ---
    quote_hoje = random.choice(QUOTES)
    st.info(f"💡 **Sabedoria do Dia:**\n\n*{quote_hoje}*")
    
    df = load_data()
    
    # --- INPUT DIÁRIO ---
    with st.sidebar:
        st.subheader("🧘 Check-in Espiritual")
        dt = st.date_input("Data", value=date.today())
        
        # Lógica para verificar se já existe registro na data (GSheets traz datas como string)
        data_str = str(dt)
        row_hoje = df[df['Data'] == data_str]
        existe = not row_hoje.empty
        
        def get_val(col, default):
            return row_hoje.iloc[0][col] if existe else default

        st.markdown("**🙏 Pote da Gratidão**")
        st.caption("3 coisas que aconteceram hoje:")
        g1 = st.text_input("1.", get_val("Gratidao_1", ""))
        g2 = st.text_input("2.", get_val("Gratidao_2", ""))
        g3 = st.text_input("3.", get_val("Gratidao_3", ""))
        
        st.markdown("---")
        st.markdown("**🌡️ Termômetro Interno**")
        
        opcoes_emocao = ["Em Paz", "Grato", "Energizado", "Ansioso", "Triste", "Irritado", "Cansado/Vazio", "Confuso"]
        emocao_atual = get_val("Emocao_Dominante", "Em Paz")
        idx_emocao = opcoes_emocao.index(emocao_atual) if emocao_atual in opcoes_emocao else 0

        emocao = st.selectbox("Como você se sente?", opcoes_emocao, index=idx_emocao)
        
        paz = st.slider("Nível de Paz Interior", 0, 10, int(get_val("Nivel_Paz_0_10", 5)))
        
        st.markdown("---")
        st.markdown("**📔 Diário / Desabafo**")
        diario = st.text_area("Reflexão do dia:", get_val("Diario_Reflexao", ""), height=150)
        
        if st.button("Salvar Registro"):
            novo = {
                "Data": data_str, 
                "Gratidao_1": g1, "Gratidao_2": g2, "Gratidao_3": g3,
                "Emocao_Dominante": emocao, "Nivel_Paz_0_10": paz,
                "Diario_Reflexao": diario
            }
            # Remove duplicata local e concatena
            df = df[df['Data'] != data_str]
            df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
            save_data(df)
            st.success("Sua alma agradece. ✨")
            st.rerun()

    # --- DASHBOARD ---
    if df.empty:
        st.write("Comece registrando o que te fez grato hoje na barra lateral.")
        return

    # Garante que a data seja datetime para os gráficos
    df['Data_dt'] = pd.to_datetime(df['Data'])
    df = df.sort_values("Data_dt", ascending=False)

    # KPI Rápido
    st.divider()
    k1, k2, k3 = st.columns(3)
    
    media_paz = df.head(7)['Nivel_Paz_0_10'].mean()
    k1.metric("Nível de Paz (Semana)", f"{media_paz:.1f}/10")
    
    top_emocao = df['Emocao_Dominante'].mode()[0] if not df.empty else "-"
    k2.metric("Emoção Predominante", top_emocao)
    
    total_gratidoes = (df['Gratidao_1'].str.strip().ne("").sum() + 
                      df['Gratidao_2'].str.strip().ne("").sum() + 
                      df['Gratidao_3'].str.strip().ne("").sum())
    k3.metric("Momentos de Gratidão", int(total_gratidoes))

    # --- ABAS ---
    t1, t2, t3 = st.tabs(["📊 Monitoramento", "🏺 Gratidão", "📔 Diário"])
    
    with t1:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Oscilação da Paz")
            # Ordena para o gráfico de linha fazer sentido temporal
            st.line_chart(df.sort_values("Data_dt").set_index("Data_dt")['Nivel_Paz_0_10'])
            
        with c2:
            st.subheader("Mapa de Sentimentos")
            counts = df['Emocao_Dominante'].value_counts().reset_index()
            counts.columns = ['Emoção', 'Qtd']
            fig = px.pie(counts, values='Qtd', names='Emoção', hole=0.4)
            st.plotly_chart(fig, use_container_width=True)

    with t2:
        st.subheader("Lembranças que Aquecem 🔥")
        for idx, row in df.iterrows():
            g_list = [x for x in [row['Gratidao_1'], row['Gratidao_2'], row['Gratidao_3']] if str(x).strip() != "" and pd.notnull(x)]
            if g_list:
                with st.container(border=True):
                    st.markdown(f"**📅 {row['Data_dt'].strftime('%d/%m/%Y')}**")
                    for g in g_list:
                        st.write(f"✨ {g}")

    with t3:
        st.subheader("Histórico de Reflexões")
        for idx, row in df.iterrows():
            if pd.notnull(row['Diario_Reflexao']) and len(str(row['Diario_Reflexao']).strip()) > 5:
                with st.expander(f"📖 {row['Data_dt'].strftime('%d/%m/%Y')} - {row['Emocao_Dominante']}"):
                    st.write(row['Diario_Reflexao'])