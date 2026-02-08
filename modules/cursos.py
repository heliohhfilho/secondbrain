import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
from modules import conexoes

def load_data():
    # Carrega Cursos
    cols = ["Curso", "Plataforma", "Total_Aulas", "Aulas_Feitas", "Link_Certificado", "Status"]
    df = conexoes.load_gsheet("Cursos", cols)
    
    if not df.empty:
        # Saneamento de tipos
        df["Total_Aulas"] = pd.to_numeric(df["Total_Aulas"], errors='coerce').fillna(1).astype(int)
        df["Aulas_Feitas"] = pd.to_numeric(df["Aulas_Feitas"], errors='coerce').fillna(0).astype(int)
        df["Link_Certificado"] = df["Link_Certificado"].fillna("")
    return df

def render_page():
    st.header("🎓 Dashboard de Estudos")
    
    df_cursos = load_data()
    # Carregamos o Log para calcular a velocidade real (Engenharia de Dados)
    df_log = conexoes.load_gsheet("Log_Produtividade", ["Data", "Tipo", "Valor"])

    # --- CÁLCULO DE RITMO (KPIs) ---
    ritmo_diario = 0.0
    total_aulas_mes = 0
    
    if not df_log.empty:
        df_log['Data'] = pd.to_datetime(df_log['Data']).dt.date
        hoje = date.today()
        primeiro_dia = hoje.replace(day=1)
        
        # Filtra logs do tipo 'Estudo' deste mês
        df_mes = df_log[
            (df_log['Tipo'] == "Estudo") & 
            (df_log['Data'] >= primeiro_dia)
        ].copy()
        
        df_mes['Valor'] = pd.to_numeric(df_mes['Valor'], errors='coerce').fillna(0)
        total_aulas_mes = df_mes['Valor'].sum()
        
        # Média Realista: Divide pelo dia atual (ex: dia 8)
        dias_passados = max(hoje.day, 1)
        ritmo_diario = total_aulas_mes / dias_passados

    # --- EXIBIÇÃO DE KPIs ---
    k1, k2, k3 = st.columns(3)
    k1.metric("Aulas este Mês", int(total_aulas_mes))
    k2.metric("Ritmo Real", f"{ritmo_diario:.2f} aulas/dia", help="Baseado na produção deste mês")
    
    # Progresso Geral (Soma de tudo)
    ativos = df_cursos[df_cursos['Status'] == "Em Andamento"]
    if not ativos.empty:
        total_geral = ativos['Total_Aulas'].sum()
        feito_geral = ativos['Aulas_Feitas'].sum()
        pct = (feito_geral / total_geral) if total_geral > 0 else 0
        k3.metric("Progresso Global", f"{pct:.1%}")
    else:
        k3.metric("Cursos Ativos", "0")

    st.divider()

    # --- GRÁFICO DE CONSISTÊNCIA ---
    st.subheader("📊 Frequência de Estudo (Mês Atual)")
    if 'df_mes' in locals() and not df_mes.empty:
        daily_study = df_mes.groupby('Data')['Valor'].sum().reset_index()
        fig = px.bar(daily_study, x='Data', y='Valor', 
                     labels={'Valor': 'Aulas/Tempo', 'Data': 'Dia'},
                     color_discrete_sequence=['#636EFA'])
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem registros de estudo este mês. Vá em 'Produtividade' para registrar.")

    # --- ABAS DE GESTÃO ---
    tab_andamento, tab_fila, tab_concluidos = st.tabs(["💻 Em Andamento", "⏳ Fila / Adicionar", "🏆 Certificados"])

    # ---------------------------------------------------------
    # ABA 1: EM ANDAMENTO (Com Previsão)
    # ---------------------------------------------------------
    with tab_andamento:
        if ativos.empty:
            st.warning("Nenhum curso em andamento.")
        
        for idx, row in ativos.iterrows():
            with st.container(border=True):
                c_info, c_action = st.columns([3, 1.5])
                
                # Cálculo de Previsão
                restam = row['Total_Aulas'] - row['Aulas_Feitas']
                prog = row['Aulas_Feitas'] / row['Total_Aulas']
                
                # Lógica de Data: Data = Hoje + (Faltam / Ritmo)
                prev_texto = "Calculando..."
                if ritmo_diario > 0.1: # Evita divisão por zero ou números absurdos
                    dias_para_fim = restam / ritmo_diario
                    data_fim = datetime.now() + timedelta(days=dias_para_fim)
                    prev_texto = f"Termina em: {data_fim.strftime('%d/%m/%Y')}"
                else:
                    prev_texto = "Sem ritmo suficiente para prever."

                with c_info:
                    st.markdown(f"### {row['Curso']}")
                    st.caption(f"{row['Plataforma']} | {prev_texto}")
                    st.progress(min(prog, 1.0))
                    st.caption(f"Progresso: {row['Aulas_Feitas']} / {row['Total_Aulas']} aulas")

                with c_action:
                    # Se completou 100%, libera botão de concluir
                    if row['Aulas_Feitas'] >= row['Total_Aulas']:
                        st.success("Curso Finalizado!")
                        link = st.text_input("Link do Certificado", key=f"lnk_{idx}")
                        if st.button("🏅 Emitir Conclusão", key=f"end_{idx}"):
                            df_cursos.at[idx, 'Status'] = "Concluído"
                            df_cursos.at[idx, 'Link_Certificado'] = link
                            conexoes.save_gsheet("Cursos", df_cursos)
                            st.balloons()
                            st.rerun()
                    else:
                        st.info(f"Faltam {restam} aulas")

    # ---------------------------------------------------------
    # ABA 2: FILA (Adicionar e Iniciar)
    # ---------------------------------------------------------
    with tab_fila:
        # Formulário de Adição
        with st.expander("➕ Cadastrar Novo Curso"):
            with st.form("new_course"):
                n_nome = st.text_input("Nome do Curso")
                n_plat = st.text_input("Plataforma")
                n_total = st.number_input("Total de Aulas", min_value=1, value=40)
                
                if st.form_submit_button("Salvar na Fila"):
                    novo = pd.DataFrame([{
                        "Curso": n_nome, "Plataforma": n_plat, 
                        "Total_Aulas": n_total, "Aulas_Feitas": 0, 
                        "Link_Certificado": "", "Status": "Na Fila"
                    }])
                    conexoes.save_gsheet("Cursos", pd.concat([df_cursos, novo], ignore_index=True))
                    st.success("Cadastrado!")
                    st.rerun()

        st.divider()
        
        # Lista da Fila
        df_fila = df_cursos[df_cursos['Status'] == "Na Fila"]
        if df_fila.empty: st.info("Fila vazia.")
        
        for idx, row in df_fila.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['Curso']}** ({row['Total_Aulas']} aulas) - {row['Plataforma']}")
                
                if c2.button("▶️ Iniciar", key=f"start_{idx}"):
                    df_cursos.at[idx, 'Status'] = "Em Andamento"
                    conexoes.save_gsheet("Cursos", df_cursos)
                    st.rerun()

    # ---------------------------------------------------------
    # ABA 3: CONCLUÍDOS
    # ---------------------------------------------------------
    with tab_concluidos:
        df_conc = df_cursos[df_cursos['Status'] == "Concluído"]
        
        if df_conc.empty: st.info("Nenhum certificado ainda.")
        
        for idx, row in df_conc.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"### 🎖️ {row['Curso']}")
                c1.caption(f"Plataforma: {row['Plataforma']}")
                
                if row['Link_Certificado']:
                    c2.link_button("Ver Certificado", row['Link_Certificado'])
                else:
                    c2.caption("Sem link")