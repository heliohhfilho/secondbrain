import streamlit as st
import pandas as pd
from datetime import datetime, date
import plotly.express as px
from modules import conexoes

def load_data():
    cols = ["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"]
    df = conexoes.load_gsheet("Leituras", cols)
    if not df.empty:
        df["Total_Paginas"] = pd.to_numeric(df["Total_Paginas"], errors='coerce').fillna(1).astype(int)
        df["Paginas_Lidas"] = pd.to_numeric(df["Paginas_Lidas"], errors='coerce').fillna(0).astype(int)
    return df

def render_page():
    st.header("📚 Dashboard de Leitura")
    
    # Carrega dados dos livros e do log de produtividade
    df_livros = load_data()
    # Carregamos o log para calcular o ritmo diário
    df_log = conexoes.load_gsheet("Log_Produtividade", ["Data", "Tipo", "Subtipo", "Valor"])
    
    if df_log.empty:
        st.warning("Nenhum log de leitura encontrado para calcular métricas.")
        return

    # --- PROCESSAMENTO DE RITMO (Mês Atual) ---
    df_log['Data'] = pd.to_datetime(df_log['Data']).dt.date
    hoje = date.today()
    primeiro_dia_mes = hoje.replace(day=1)
    
    # Filtra logs de leitura do mês atual
    df_mes = df_log[(df_log['Tipo'] == "Leitura") & (df_log['Data'] >= primeiro_dia_mes)].copy()
    df_mes['Valor'] = pd.to_numeric(df_mes['Valor'], errors='coerce').fillna(0)
    
    # Cálculo de métricas realistas
    total_lido_mes = df_mes['Valor'].sum()
    dias_passados = hoje.day # Ex: Se hoje é dia 07, divide por 7
    ritmo_diario = total_lido_mes / dias_passados

    # --- KPIs SUPERIORES ---
    c1, c2, c3 = st.columns(3)
    c1.metric("Páginas lidas no mês", f"{int(total_lido_mes)} pág")
    c2.metric("Ritmo Diário (Real)", f"{ritmo_diario:.1f} pág/dia")
    c3.metric("Livros em Andamento", len(df_livros[df_livros['Status'] == "Lendo"]))

    st.divider()

    # --- GRÁFICO DE BARRAS: PÁGINAS POR DIA ---
    st.subheader("📊 Consistência Diária (Mês Atual)")
    if not df_mes.empty:
        daily_read = df_mes.groupby('Data')['Valor'].sum().reset_index()
        fig = px.bar(daily_read, x='Data', y='Valor', 
                     title="Páginas Lidas por Dia",
                     labels={'Valor': 'Páginas', 'Data': 'Dia'},
                     color_discrete_sequence=['#00CC96'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Ainda não há registros de leitura este mês.")

# --- ABAS COM GESTÃO DE ESTADO ---
    tab_lendo, tab_fila, tab_concluidos = st.tabs(["📖 Lendo Agora", "⏳ Na Estante", "🏆 Concluídos"])

    with tab_lendo:
        df_lendo = df_livros[df_livros['Status'] == "Lendo"]
        if df_lendo.empty:
            st.info("Nenhum livro em progresso. Vá até a 'Estante' para começar um!")
        
        for idx, row in df_lendo.iterrows():
            with st.container(border=True):
                col_t, col_p = st.columns([3, 1])
                prog = row['Paginas_Lidas'] / row['Total_Paginas']
                
                with col_t:
                    st.markdown(f"### {row['Titulo']}")
                    st.caption(f"Autor: {row['Autor']} | {row['Paginas_Lidas']}/{row['Total_Paginas']} pág.")
                    st.progress(min(prog, 1.0))
                
                with col_p:
                    # Lógica de Conclusão Automática baseada no progresso vindo da aba Produtividade
                    if row['Paginas_Lidas'] >= row['Total_Paginas']:
                        st.success("Concluído!")
                        nota = st.selectbox("Nota", [5,4,3,2,1], key=f"nota_{idx}")
                        if st.button("Arquivar", key=f"arc_{idx}"):
                            df_livros.at[idx, 'Status'] = "Concluído"
                            df_livros.at[idx, 'Nota'] = nota
                            conexoes.save_gsheet("Leituras", df_livros)
                            st.rerun()
                    else:
                        st.metric("Progresso", f"{int(prog*100)}%")

    with tab_fila:
        df_fila = df_livros[df_livros['Status'] == "Na Fila"]
        
        # Formulário para novo livro
        with st.expander("➕ Adicionar Novo à Estante"):
            with st.form("novo_livro"):
                t = st.text_input("Título")
                a = st.text_input("Autor")
                p = st.number_input("Total Páginas", min_value=1)
                if st.form_submit_button("Cadastrar"):
                    novo = pd.DataFrame([{"Titulo": t, "Autor": a, "Total_Paginas": p, "Paginas_Lidas": 0, "Nota": 0, "Status": "Na Fila"}])
                    conexoes.save_gsheet("Leituras", pd.concat([df_livros, novo], ignore_index=True))
                    st.rerun()

        # Botão para mover para "Lendo"
        for idx, row in df_fila.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['Titulo']}** ({row['Total_Paginas']} pág.)")
                if c2.button("▶️ Iniciar", key=f"start_{idx}"):
                    df_livros.at[idx, 'Status'] = "Lendo"
                    conexoes.save_gsheet("Leituras", df_livros)
                    st.rerun()

    with tab_concluidos:
        st.dataframe(df_livros[df_livros['Status'] == "Concluído"][["Titulo", "Autor", "Nota"]], use_container_width=True)