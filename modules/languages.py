import streamlit as st
import pandas as pd
from datetime import date
import random
from modules import conexoes

def load_lang_data():
    # 1. Configuração de Idiomas (Idiomas ativos e níveis)
    cols_conf = ["Idioma", "Nivel_Atual", "Data_Inicio"]
    df_conf = conexoes.load_gsheet("Lang_Config", cols_conf)
    if df_conf.empty:
        df_conf = pd.DataFrame(columns=cols_conf)

    # 2. Dicionário (Vocabulário e Frases)
    cols_dict = ["Idioma", "Data", "Palavra_Frase", "Traducao", "Contexto_Exemplo"]
    df_dict = conexoes.load_gsheet("Lang_Dicionario", cols_dict)
    if df_dict.empty:
        df_dict = pd.DataFrame(columns=cols_dict)
    
    # Saneamento: Garantir que datas sejam strings consistentes
    if not df_dict.empty:
        df_dict["Data"] = df_dict["Data"].astype(str)

    return df_conf, df_dict

def save_lang_data(df, aba):
    """
    Padroniza o salvamento convertendo booleanos e datas para string,
    evitando erros de serialização no gspread.
    """
    df_save = df.copy()
    
    # Colunas que podem causar conflito de tipo no Sheets
    cols_to_str = ["Data", "Data_Inicio"]
    for col in cols_to_str:
        if col in df_save.columns:
            df_save[col] = df_save[col].astype(str)
            
    conexoes.save_gsheet(aba, df_save)

import streamlit as st
import pandas as pd
from datetime import date
from modules import conexoes

def render_page():
    st.title("🌐 Language Engineering Hub")
    
    # 1. CARREGAMENTO
    df_conf, df_dict = load_lang_data()

    # --- SIDEBAR: GERENCIAMENTO DE IDIOMAS ---
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # Botão para adicionar novos idiomas (Sempre disponível)
        with st.expander("➕ Adicionar Novo Idioma"):
            novo_nome = st.text_input("Nome do Idioma", placeholder="Ex: Japonês")
            novo_nivel = st.select_slider("Nível Inicial", ["A1", "A2", "B1", "B2", "C1", "C2"])
            
            if st.button("Cadastrar Idioma"):
                if novo_nome and novo_nome not in df_conf["Idioma"].values:
                    novo_id = pd.DataFrame([{
                        "Idioma": novo_nome, 
                        "Nivel_Atual": novo_nivel, 
                        "Data_Inicio": str(date.today())
                    }])
                    df_conf = pd.concat([df_conf, novo_id], ignore_index=True)
                    save_lang_data(df_conf, "Lang_Config")
                    st.success(f"{novo_nome} cadastrado!")
                    st.rerun()
                else:
                    st.error("Idioma já existe ou campo vazio.")

    # --- FLUXO PRINCIPAL ---
    if df_conf.empty:
        st.info("Utilize o menu lateral para cadastrar seu primeiro idioma de estudo.")
        return

    # Seleção do idioma atual de estudo
    idioma_alvo = st.selectbox("Estudar agora:", df_conf["Idioma"].unique())
    
    # KPIs Rápidos
    nivel_atual = df_conf[df_conf["Idioma"] == idioma_alvo]["Nivel_Atual"].values[0]
    total_termos = len(df_dict[df_dict["Idioma"] == idioma_alvo])
    
    c1, c2 = st.columns(2)
    c1.metric("Nível Atual", nivel_atual)
    c2.metric("Termos no Dicionário", total_termos)

    tab_registro, tab_treino = st.tabs(["📖 Dicionário & Frases", "🧠 Treino Reverso"])

    with tab_registro:
        # Form de Registro (Input Diário)
        with st.form("new_entry"):
            st.caption(f"Novo registro para {idioma_alvo}")
            col_a, col_b = st.columns(2)
            palavra = col_a.text_input("Palavra/Expressão")
            traducao = col_b.text_input("Tradução")
            contexto = st.text_area("Exemplo de uso (Frase completa)")
            
            if st.form_submit_button("💾 Salvar no Log"):
                if palavra and traducao:
                    novo_item = {
                        "Idioma": idioma_alvo,
                        "Data": str(date.today()),
                        "Palavra_Frase": palavra,
                        "Traducao": traducao,
                        "Contexto_Exemplo": contexto
                    }
                    df_dict = pd.concat([df_dict, pd.DataFrame([novo_item])], ignore_index=True)
                    save_lang_data(df_dict, "Lang_Dicionario")
                    st.toast("Registrado com sucesso!")
                    st.rerun()

        # Visualização do Dicionário
        st.markdown("---")
        view_df = df_dict[df_dict["Idioma"] == idioma_alvo].sort_values("Data", ascending=False)
        st.dataframe(view_df, width='stretch', hide_index=True)

    with tab_treino:
        st.subheader("Modo Flashcard")
        # Aqui entra a lógica de buscar uma frase aleatória que você pediu
        if not view_df.empty:
            if st.button("Gerar Desafio Aleatório"):
                amostra = view_df.sample(1).iloc[0]
                st.session_state['desafio'] = amostra
            
            if 'desafio' in st.session_state:
                st.info(f"Como se traduz: **{st.session_state['desafio']['Palavra_Frase']}**?")
                resp = st.text_input("Sua resposta:")
                if st.button("Corrigir"):
                    if resp.lower().strip() == st.session_state['desafio']['Traducao'].lower().strip():
                        st.success("Correto! Engenharia mental em dia.")
                    else:
                        st.error(f"Incorreto. A tradução é: {st.session_state['desafio']['Traducao']}")
        else:
            st.warning("Adicione palavras ao dicionário primeiro para poder treinar.")