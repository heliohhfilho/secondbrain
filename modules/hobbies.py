import streamlit as st
import pandas as pd
from datetime import date
import os

# --- ARQUIVOS ---
PATH_HOBBIES = os.path.join('data', 'hobbies_projetos.csv')

def load_data():
    if not os.path.exists(PATH_HOBBIES):
        return pd.DataFrame(columns=[
            "ID", "Nome", "Categoria", "Status", "Progresso_Perc", 
            "Materiais_Nec", "Link_Ref", "Data_Inicio", "Notas"
        ])
    return pd.read_csv(PATH_HOBBIES)

def save_data(df):
    df.to_csv(PATH_HOBBIES, index=False)

def get_icon(categoria):
    icons = {
        "Costura/Moda": "🧵",
        "Crochet/Tricô": "🧶",
        "Arduino/Eletrônica": "⚡",
        "Programação": "💻",
        "Outros": "🎨"
    }
    return icons.get(categoria, "🔨")

def render_page():
    st.header("🛠️ Maker Space & Ateliê")
    st.caption("Onde as ideias viram realidade física.")
    
    df = load_data()
    
    # --- SIDEBAR: NOVO PROJETO ---
    with st.sidebar:
        st.subheader("➕ Novo Projeto")
        with st.form("form_hobby"):
            h_nome = st.text_input("Nome do Projeto (Ex: Camisa Linho)")
            h_cat = st.selectbox("Categoria", ["Costura/Moda", "Crochet/Tricô", "Arduino/Eletrônica", "Programação", "Outros"])
            h_mat = st.text_area("Materiais Necessários (BOM)", placeholder="- 2m Tecido\n- 1 Arduino Uno\n- Linha")
            h_link = st.text_input("Link de Referência (Tutorial/Inspiração)")
            
            if st.form_submit_button("Criar Projeto"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, "Nome": h_nome, "Categoria": h_cat,
                    "Status": "Ideia", "Progresso_Perc": 0,
                    "Materiais_Nec": h_mat, "Link_Ref": h_link,
                    "Data_Inicio": date.today(), "Notas": ""
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Projeto na bancada!")
                st.rerun()

    # --- KPI RÁPIDO ---
    if not df.empty:
        ativos = len(df[df['Status'] != "Concluído"])
        concluidos = len(df[df['Status'] == "Concluído"])
        c1, c2, c3 = st.columns(3)
        c1.metric("Projetos em Andamento", ativos)
        c2.metric("Portfolio Concluído", concluidos)
        
        # Filtro de Categoria
        cats = df['Categoria'].unique().tolist()
        filtro = c3.multiselect("Filtrar Bancada", cats, default=cats)
        
        df_view = df[df['Categoria'].isin(filtro)]
    else:
        df_view = df
        st.info("Sua bancada está vazia. Adicione um hobby na barra lateral!")

    st.divider()

    # --- VISUALIZAÇÃO EM CARDS (GRID) ---
    if not df_view.empty:
        # Separa Concluídos de Ativos
        df_ativos = df_view[df_view['Status'] != "Concluído"].sort_values("Progresso_Perc", ascending=False)
        df_concluidos = df_view[df_view['Status'] == "Concluído"]

        st.subheader("🚧 Na Bancada (Em Produção)")
        if df_ativos.empty: st.caption("Nada sendo feito agora.")
        
        for idx, row in df_ativos.iterrows():
            icon = get_icon(row['Categoria'])
            
            with st.container(border=True):
                # Cabeçalho do Card
                c_tit, c_prog, c_status = st.columns([3, 2, 2])
                c_tit.markdown(f"### {icon} {row['Nome']}")
                c_prog.progress(int(row['Progresso_Perc']) / 100)
                c_status.caption(f"Status: **{row['Status']}** ({row['Progresso_Perc']}%)")
                
                # Corpo do Card (Expansível)
                with st.expander("🛠️ Detalhes & Atualizar"):
                    c_input1, c_input2 = st.columns(2)
                    
                    # Atualizar Status
                    new_status = c_input1.selectbox("Fase", ["Ideia", "Comprando Material", "Fazendo", "Acabamento", "Concluído"], 
                                                  index=["Ideia", "Comprando Material", "Fazendo", "Acabamento", "Concluído"].index(row['Status']), key=f"s_{row['ID']}")
                    
                    # Atualizar Progresso
                    new_prog = c_input2.slider("Progresso (%)", 0, 100, int(row['Progresso_Perc']), key=f"p_{row['ID']}")
                    
                    # Materiais e Notas
                    st.markdown("**📦 Materiais:**")
                    st.text(row['Materiais_Nec'])
                    
                    if row['Link_Ref']:
                        st.markdown(f"🔗 [Ver Referência/Tutorial]({row['Link_Ref']})")

                    # Botão Salvar dentro do card
                    col_save, col_del = st.columns([4, 1])
                    if col_save.button("Atualizar Projeto", key=f"upd_{row['ID']}"):
                        df.loc[df['ID'] == row['ID'], 'Status'] = new_status
                        df.loc[df['ID'] == row['ID'], 'Progresso_Perc'] = new_prog
                        save_data(df)
                        st.success("Atualizado!")
                        st.rerun()
                        
                    if col_del.button("🗑️", key=f"del_h_{row['ID']}"):
                        df = df[df['ID'] != row['ID']]
                        save_data(df)
                        st.rerun()

        if not df_concluidos.empty:
            st.divider()
            st.subheader("🏆 Hall da Fama (Concluídos)")
            for idx, row in df_concluidos.iterrows():
                icon = get_icon(row['Categoria'])
                st.markdown(f"- {icon} **{row['Nome']}** (Finalizado em {row['Data_Inicio']})")