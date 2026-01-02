import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from modules import conexoes

def load_data():
    # 1. Carrega Metas Principais (Com Trimestre)
    cols_metas = ["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Trimestre", "Ano", "Progresso_Manual"]
    df = conexoes.load_gsheet("Metas", cols_metas)
    
    if not df.empty:
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Meta_Valor"] = pd.to_numeric(df["Meta_Valor"], errors='coerce').fillna(0.0)
        df["Progresso_Manual"] = pd.to_numeric(df["Progresso_Manual"], errors='coerce').fillna(0.0)
        # Default para Q1/2025 se vier vazio
        if "Trimestre" not in df.columns: df["Trimestre"] = "Q1"
        if "Ano" not in df.columns: df["Ano"] = str(date.today().year)

    # 2. Busca Dados Externos (OKRs Automáticos)
    dados_externos = {}
    
    # Investimentos
    df_inv = conexoes.load_gsheet("Investimentos", ["Qtd", "Preco_Unitario"])
    if not df_inv.empty:
        df_inv["Qtd"] = pd.to_numeric(df_inv["Qtd"], errors='coerce').fillna(0)
        df_inv["Preco_Unitario"] = pd.to_numeric(df_inv["Preco_Unitario"], errors='coerce').fillna(0)
        dados_externos['Investimento Total'] = (df_inv['Qtd'] * df_inv['Preco_Unitario']).sum()
    
    # Bio
    df_b = conexoes.load_gsheet("Bio", ["Data", "Peso_kg", "Gordura_Perc"])
    if not df_b.empty:
        df_b['Data'] = pd.to_datetime(df_b['Data'], errors='coerce')
        last_bio = df_b.sort_values("Data").iloc[-1]
        dados_externos['Peso Atual'] = pd.to_numeric(last_bio['Peso_kg'], errors='coerce')
        dados_externos['BF Atual'] = pd.to_numeric(last_bio['Gordura_Perc'], errors='coerce')

    return df, dados_externos

def save_data(df):
    df_save = df.copy()
    conexoes.save_gsheet("Metas", df_save)

def calcular_status(tipo, meta, manual, externos):
    atual = 0.0
    # Roteamento de Dados
    if tipo == "Manual": atual = manual
    elif tipo == "💰 Investimento Total": atual = externos.get('Investimento Total', 0)
    elif tipo == "⚖️ Peso (Emagrecer)": atual = externos.get('Peso Atual', 0)
    elif tipo == "🧬 Gordura % (Baixar)": atual = externos.get('BF Atual', 0)
    
    # Lógica de Progresso
    if tipo in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]:
        perc = 0 
    else:
        perc = (atual / meta * 100) if meta > 0 else 0
        perc = min(100.0, max(0.0, perc))
        
    return atual, perc

def get_trimestre_dates(q, ano):
    if q == "Q1": return date(ano, 1, 1), date(ano, 3, 31)
    if q == "Q2": return date(ano, 4, 1), date(ano, 6, 30)
    if q == "Q3": return date(ano, 7, 1), date(ano, 9, 30)
    if q == "Q4": return date(ano, 10, 1), date(ano, 12, 31)
    return date(ano, 1, 1), date(ano, 12, 31)

def render_page():
    st.header("🎯 OKRs & Metas")
    
    df, dados_externos = load_data()
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.subheader("⚙️ Configuração")
        # 1. SOLUÇÃO DO PROBLEMA: Seletor de Ano para Visualização
        ano_view = st.number_input("Visualizar Ano:", 2024, 2030, date.today().year)
        st.divider()

        st.subheader("➕ Nova Meta")
        tipos_disponiveis = ["Manual", "💰 Investimento Total", "⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]
        
        with st.form("nova_meta"):
            m_titulo = st.text_input("Objetivo")
            m_tipo = st.selectbox("Tipo", tipos_disponiveis)
            c1, c2 = st.columns(2)
            m_trim = c1.selectbox("Trimestre", ["Q1", "Q2", "Q3", "Q4"])
            m_ano = c2.number_input("Ano Meta", 2024, 2030, date.today().year) # Default ano atual
            
            c3, c4 = st.columns(2)
            m_valor = c3.number_input("Valor Alvo", 0.0, 1000000.0, 10.0)
            m_unidade = c4.text_input("Unidade", "kg")
            
            if st.form_submit_button("Criar Sprint"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, "Titulo": m_titulo, "Tipo_Vinculo": m_tipo,
                    "Meta_Valor": m_valor, "Unidade": m_unidade, 
                    "Trimestre": m_trim, "Ano": m_ano, "Progresso_Manual": 0.0
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Criado!")
                st.rerun()

    if df.empty:
        st.info("Nenhuma meta encontrada. Crie a primeira na barra lateral.")
        # Cria dataframe vazio estruturado para evitar erro no editor
        df = pd.DataFrame(columns=["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Trimestre", "Ano", "Progresso_Manual"])

    # --- ABAS ---
    # 2. SOLUÇÃO DO PROBLEMA: Aba extra "Gerenciar"
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["Q1", "Q2", "Q3", "Q4", "⚙️ Gerenciar Tudo"])
    
    tabs_map = {"Q1": tab1, "Q2": tab2, "Q3": tab3, "Q4": tab4}
    
    # Lógica de Trimestres
    for q_name, tab_obj in tabs_map.items():
        with tab_obj:
            # Filtra pelo ANO SELECIONADO NA SIDEBAR (ano_view), não mais date.today()
            metas_q = df[(df['Trimestre'] == q_name) & (df['Ano'] == str(ano_view))]
            
            if metas_q.empty:
                st.caption(f"Sem metas para {q_name}/{ano_view}.")
            else:
                # Barra de tempo apenas se for o ano atual
                if ano_view == date.today().year:
                    start_q, end_q = get_trimestre_dates(q_name, ano_view)
                    total_days = (end_q - start_q).days
                    passed_days = (date.today() - start_q).days
                    perc_time = max(0.0, min(1.0, passed_days / total_days))
                    st.progress(perc_time, text=f"Tempo decorrido: {int(perc_time*100)}%")
                    st.divider()

                # Cards
                col1, col2 = st.columns(2)
                for idx, row in metas_q.iterrows():
                    target_col = col1 if idx % 2 == 0 else col2
                    with target_col:
                        with st.container(border=True):
                            st.markdown(f"**{row['Titulo']}**")
                            
                            atual, perc = calcular_status(row['Tipo_Vinculo'], row['Meta_Valor'], row['Progresso_Manual'], dados_externos)
                            
                            # Lógica Visual
                            is_weight = row['Tipo_Vinculo'] in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]
                            
                            if is_weight:
                                delta = atual - row['Meta_Valor']
                                if delta <= 0: st.success(f"✅ {atual} {row['Unidade']}")
                                else: st.metric("Falta", f"{delta:.1f}", f"Atual: {atual}")
                            else:
                                st.metric("Progresso", f"{atual:,.0f} / {row['Meta_Valor']:,.0f}", f"{perc:.1f}%")
                                st.progress(perc/100)
                            
                            if row['Tipo_Vinculo'] == "Manual":
                                new_val = st.number_input("Atualizar", value=float(row['Progresso_Manual']), key=f"up_{row['ID']}")
                                if new_val != row['Progresso_Manual']:
                                    df.loc[df['ID'] == row['ID'], 'Progresso_Manual'] = new_val
                                    save_data(df); st.rerun()

    # --- ABA DE GERENCIAMENTO TOTAL ---
    with tab5:
        st.subheader("Base de Dados Completa")
        st.caption("Edite valores diretamente na tabela. Selecione linhas e aperte DEL no teclado para apagar.")
        
        # Editor nativo do Streamlit (permite adicionar, editar e excluir)
        edited_df = st.data_editor(
            df, 
            num_rows="dynamic", 
            use_container_width=True,
            key="editor_geral",
            hide_index=True
        )

        # Botão para salvar alterações feitas na tabela
        if st.button("💾 Salvar Alterações na Tabela"):
            save_data(edited_df)
            st.success("Banco de dados atualizado!")
            st.rerun()