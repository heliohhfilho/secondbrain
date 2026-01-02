import streamlit as st
import pandas as pd
from datetime import date, datetime
from modules import conexoes

def load_data():
    # Definição das colunas esperadas
    cols_metas = ["ID", "Titulo", "Descricao_S", "Motivo_R", "Meta_Valor", "Unidade", "Progresso_Atual", "Deadline_T", "Trimestre", "Ano"]
    
    # Tenta carregar. Se a função load_gsheet aceitar lista de colunas, ótimo.
    # Se ela retornar colunas antigas, tratamos abaixo.
    df = conexoes.load_gsheet("Metas", cols_metas)
    
    # Se vier vazio ou None, cria DataFrame zerado com a estrutura certa
    if df is None or df.empty:
        df = pd.DataFrame(columns=cols_metas)
    
    # --- CORREÇÃO DE MIGRAÇÃO (Evita o KeyError) ---
    # 1. Se a coluna nova não existe, tenta pegar da antiga 'Progresso_Manual'
    if "Progresso_Atual" not in df.columns:
        if "Progresso_Manual" in df.columns:
            df["Progresso_Atual"] = df["Progresso_Manual"]
        else:
            df["Progresso_Atual"] = 0.0

    # 2. Garante que as outras colunas novas existam antes de mexer nelas
    if "Descricao_S" not in df.columns: df["Descricao_S"] = ""
    if "Motivo_R" not in df.columns: df["Motivo_R"] = ""
    if "Deadline_T" not in df.columns: df["Deadline_T"] = None
    # ------------------------------------------------

    # Agora é seguro converter os tipos
    df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
    df["Meta_Valor"] = pd.to_numeric(df["Meta_Valor"], errors='coerce').fillna(0.0)
    df["Progresso_Atual"] = pd.to_numeric(df["Progresso_Atual"], errors='coerce').fillna(0.0)
    
    # Garante que Ano é Texto
    df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce').fillna(date.today().year).astype(int).astype(str)
    
    # Tratamento de Data
    df["Deadline_T"] = pd.to_datetime(df["Deadline_T"], errors='coerce').dt.date
    
    return df

def save_data(df):
    conexoes.save_gsheet("Metas", df)

def render_page():
    st.header("🎯 Metas S.M.A.R.T.")
    st.caption("Específico • Mensurável • Atingível • Relevante • Temporal")
    
    df = load_data()
    
    # --- SIDEBAR: CRIAÇÃO SMART ---
    with st.sidebar:
        st.subheader("⚙️ Configuração")
        ano_view = st.number_input("Visualizar Ano:", 2024, 2030, date.today().year)
        st.divider()

        st.subheader("➕ Nova Meta SMART")
        with st.form("nova_meta_smart"):
            # S - Specific
            m_titulo = st.text_input("Objetivo (Curto)", placeholder="Ex: Ler 5 Livros")
            m_desc = st.text_area("S: Específico (O que exatamente?)", placeholder="Ler livros técnicos sobre Engenharia e Day Trade.")
            
            # R - Relevant
            m_motivo = st.text_area("R: Relevante (Por que?)", placeholder="Para melhorar minha análise técnica e disciplina.")
            
            # M - Measurable
            c1, c2 = st.columns(2)
            m_valor = c1.number_input("M: Meta (Valor)", 1.0, 100000.0, 10.0)
            m_unidade = c2.text_input("Unidade", "livros")
            
            # T - Time-bound
            c3, c4 = st.columns(2)
            m_trim = c3.selectbox("Trimestre", ["Q1", "Q2", "Q3", "Q4"])
            m_ano = c4.number_input("Ano", 2024, 2030, date.today().year)
            
            m_deadline = st.date_input("T: Deadline Final", date(m_ano, 3, 31))

            if st.form_submit_button("Criar Meta SMART"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, 
                    "Titulo": m_titulo, 
                    "Descricao_S": m_desc,
                    "Motivo_R": m_motivo,
                    "Meta_Valor": m_valor, 
                    "Unidade": m_unidade, 
                    "Progresso_Atual": 0.0,
                    "Deadline_T": m_deadline,
                    "Trimestre": m_trim, 
                    "Ano": str(m_ano)
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Meta Definida!")
                st.rerun()

    if df.empty:
        st.info("Defina sua primeira meta SMART na barra lateral.")
        df = pd.DataFrame(columns=["ID", "Titulo", "Descricao_S", "Motivo_R", "Meta_Valor", "Unidade", "Progresso_Atual", "Deadline_T", "Trimestre", "Ano"])

    # --- DASHBOARD ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Q1", "Q2", "Q3", "Q4", "⚙️ Gerenciar"])
    tabs_map = {"Q1": tab1, "Q2": tab2, "Q3": tab3, "Q4": tab4}

    for q_name, tab_obj in tabs_map.items():
        with tab_obj:
            metas_q = df[(df['Trimestre'] == q_name) & (df['Ano'] == str(ano_view))]
            
            if metas_q.empty:
                st.caption(f"Sem metas para {q_name}/{ano_view}.")
            else:
                for idx, row in metas_q.iterrows():
                    with st.container(border=True):
                        # Cabeçalho: Título + Delete
                        c_tit, c_del = st.columns([0.9, 0.1])
                        c_tit.markdown(f"### {row['Titulo']}")
                        if c_del.button("❌", key=f"d_{row['ID']}"):
                            df = df[df['ID'] != row['ID']]
                            save_data(df); st.rerun()

                        # Progresso Visual
                        progresso = min(100.0, (row['Progresso_Atual'] / row['Meta_Valor']) * 100) if row['Meta_Valor'] > 0 else 0
                        st.progress(progresso/100)
                        
                        c_metrics1, c_metrics2, c_metrics3 = st.columns(3)
                        c_metrics1.metric("Atual", f"{row['Progresso_Atual']:.1f}")
                        c_metrics2.metric("Meta", f"{row['Meta_Valor']:.1f} {row['Unidade']}")
                        
                        # Cálculo de Dias Restantes (Time-bound)
                        if pd.notnull(row['Deadline_T']):
                            hoje = date.today()
                            dias_rest = (row['Deadline_T'] - hoje).days
                            cor = "normal" if dias_rest > 30 else "off" if dias_rest < 0 else "inverse"
                            c_metrics3.metric("Dias Restantes", f"{dias_rest} dias", delta_color=cor)

                        # Detalhes SMART (Expander)
                        with st.expander("📖 Detalhes SMART (Motivação & Específico)"):
                            st.markdown(f"**S (Específico):** {row['Descricao_S']}")
                            st.markdown(f"**R (Relevante):** *{row['Motivo_R']}*")
                            st.caption(f"Deadline: {row['Deadline_T']}")

                        # Input Manual
                        new_val = st.number_input("Atualizar Progresso:", value=float(row['Progresso_Atual']), key=f"up_{row['ID']}")
                        if new_val != row['Progresso_Atual']:
                            df.loc[df['ID'] == row['ID'], 'Progresso_Atual'] = new_val
                            save_data(df)
                            st.rerun()

    # --- ABA EDITORA ---
    with tab5:
        st.subheader("Base de Dados Completa")
        edited_df = st.data_editor(df, num_rows="dynamic", width='stretch', hide_index=True)
        if st.button("💾 Salvar Tabela"):
            save_data(edited_df)
            st.success("Salvo!")
            st.rerun()