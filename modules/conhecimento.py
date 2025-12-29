import streamlit as st
import pandas as pd
from datetime import date
import os
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols = ["ID", "Titulo", "Categoria", "Conteudo", "Tags", "Data_Criacao"]
    df = conexoes.load_gsheet("Wiki", cols)
    
    if not df.empty:
        # Garante que o ID seja numérico para o auto-incremento
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        # Garante que as colunas de texto sejam strings (evita erro com Markdown)
        df['Conteudo'] = df['Conteudo'].astype(str)
        df['Titulo'] = df['Titulo'].astype(str)
        
    return df

def save_data(df):
    conexoes.save_gsheet("Wiki", df)

def render_page():
    st.header("🧠 Base de Conhecimento (Wiki)")
    st.caption("Insights e aprendizados sincronizados na nuvem.")
    
    df = load_data()
    
    # --- SIDEBAR: NOVA NOTA ---
    with st.sidebar:
        st.subheader("➕ Novo Insight")
        with st.form("form_wiki"):
            w_tit = st.text_input("Título (O Conceito)")
            w_cat = st.selectbox("Área", ["Day Trade", "Engenharia", "Psicologia", "Negócios", "Código/Dev", "Filosofia", "Outros"])
            w_tags = st.text_input("Tags (sep. por vírgula)")
            w_cont = st.text_area("Conteúdo (Markdown)", height=200)
            
            if st.form_submit_button("Salvar Nota"):
                if w_tit and w_cont:
                    max_id = df['ID'].max() if not df.empty else 0
                    new_id = int(max_id) + 1
                    
                    novo = {
                        "ID": new_id, 
                        "Titulo": w_tit, 
                        "Categoria": w_cat, 
                        "Conteudo": w_cont, 
                        "Tags": w_tags, 
                        "Data_Criacao": str(date.today())
                    }
                    
                    df_updated = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_updated)
                    st.success("Sinapse sincronizada na nuvem!")
                    st.rerun()
                else:
                    st.error("Título e Conteúdo são obrigatórios.")

    # --- ÁREA DE PESQUISA ---
    termo = st.text_input("🔍 Pesquisar no Cérebro", placeholder="Fórmulas, setups, ideias...")
    
    view_df = df.copy()
    if termo and not view_df.empty:
        # Busca case-insensitive em múltiplas frentes
        mask = view_df['Titulo'].str.contains(termo, case=False, na=False) | \
               view_df['Conteudo'].str.contains(termo, case=False, na=False) | \
               view_df['Tags'].str.contains(termo, case=False, na=False)
        view_df = view_df[mask]
    
    # --- VISUALIZAÇÃO ---
    if not view_df.empty:
        # Saneamento de data para ordenação
        view_df['Data_dt'] = pd.to_datetime(view_df['Data_Criacao'], errors='coerce')
        view_df = view_df.sort_values("Data_dt", ascending=False)
        
        for idx, row in view_df.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.subheader(f"📌 {row['Titulo']}")
                
                # Formata data para exibição
                dt_str = row['Data_dt'].strftime('%d/%m/%Y') if pd.notnull(row['Data_dt']) else "-"
                c2.caption(dt_str)
                
                st.markdown(f"**Categoria:** `{row['Categoria']}` | **Tags:** *{row['Tags']}*")
                st.divider()
                st.markdown(row['Conteudo'])
                
                if st.button("Apagar Nota", key=f"del_w_{row['ID']}"):
                    df_final = df[df['ID'] != row['ID']]
                    save_data(df_final)
                    st.rerun()
    else:
        st.info("Nenhuma nota encontrada.")
        
    # --- ESTATÍSTICAS ---
    if not df.empty:
        st.divider()
        c1, c2 = st.columns(2)
        c1.metric("Total de Notas", len(df))
        top_cat = df['Categoria'].value_counts().idxmax() if not df['Categoria'].empty else "-"
        c2.metric("Área Dominante", top_cat)