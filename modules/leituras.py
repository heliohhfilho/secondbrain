import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

FILE_PATH = os.path.join('data', 'leituras.csv')

def load_data():
    if not os.path.exists(FILE_PATH):
        return pd.DataFrame(columns=["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"])
    return pd.read_csv(FILE_PATH)

def save_data(df):
    df.to_csv(FILE_PATH, index=False)

def determine_status(lidas, total):
    # Garante que não ultrapasse o total
    if lidas > total: lidas = total
    
    if lidas == 0:
        return "Na Fila"
    elif lidas >= total:
        return "Concluído"
    else:
        return "Lendo"

def render_page():
    st.header("📚 Biblioteca Pessoal")
    
    df = load_data()

    # --- SIDEBAR ---
    with st.sidebar:
        st.subheader("📖 Novo Livro")
        titulo = st.text_input("Título")
        autor = st.text_input("Autor")
        total_pag = st.number_input("Total Páginas", min_value=1, value=200)
        
        if st.button("Cadastrar"):
            if titulo:
                novo = {
                    "Titulo": titulo, "Autor": autor, "Total_Paginas": total_pag,
                    "Paginas_Lidas": 0, "Nota": 0, "Status": "Na Fila"
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Salvo!")
                st.rerun()

        st.divider()
        velocidade = st.slider("Páginas/dia (Estimativa)", 5, 100, 15)

    # --- KPIs ---
    if not df.empty:
        df['Status'] = df.apply(lambda x: determine_status(x['Paginas_Lidas'], x['Total_Paginas']), axis=1)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Lendo", len(df[df['Status'] == "Lendo"]))
        k2.metric("Concluídos", len(df[df['Status'] == "Concluído"]))
        k3.metric("Páginas Lidas", df['Paginas_Lidas'].sum())
        st.divider()

    # --- ABAS ---
    tab_lendo, tab_fila, tab_concluidos = st.tabs(["📖 Lendo", "⏳ Fila", "🏆 Concluídos"])

    # --- FUNÇÃO AUXILIAR DE EDIÇÃO ---
    def render_edit_controls(idx, row):
        """Renderiza os controles de Edição e Exclusão dentro de um Expander"""
        with st.expander("⚙️ Editar / Excluir", expanded=False):
            with st.form(key=f"form_edit_{idx}"):
                c1, c2 = st.columns(2)
                n_titulo = c1.text_input("Título", row['Titulo'])
                n_autor = c2.text_input("Autor", row['Autor'])
                n_total = st.number_input("Total Páginas", min_value=1, value=int(row['Total_Paginas']))
                
                if st.form_submit_button("💾 Salvar Alterações"):
                    df.at[idx, 'Titulo'] = n_titulo
                    df.at[idx, 'Autor'] = n_autor
                    df.at[idx, 'Total_Paginas'] = n_total
                    # Recalcula status caso o total de paginas mude
                    df.at[idx, 'Status'] = determine_status(row['Paginas_Lidas'], n_total)
                    save_data(df)
                    st.rerun()

            # Botão de Excluir fora do form para evitar submit acidental
            if st.button("🗑️ Excluir Livro", key=f"del_{idx}", type="primary"):
                df.drop(idx, inplace=True)
                save_data(df)
                st.rerun()

    # ==========================
    # ABA: LENDO
    # ==========================
    with tab_lendo:
        df_lendo = df[df['Status'] == "Lendo"]
        if df_lendo.empty: st.info("Nada sendo lido no momento.")
        
        for idx, row in df_lendo.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.subheader(row['Titulo'])
                    st.caption(f"{row['Autor']}")
                    prog = row['Paginas_Lidas'] / row['Total_Paginas']
                    st.progress(min(prog, 1.0))
                    
                with c2:
                    # Atualização Rápida de Leitura
                    n_pag = st.number_input(
                        "Pág. Atual", 0, int(row['Total_Paginas']), int(row['Paginas_Lidas']), key=f"n_{idx}"
                    )
                    if n_pag != row['Paginas_Lidas']:
                        df.at[idx, 'Paginas_Lidas'] = n_pag
                        df.at[idx, 'Status'] = determine_status(n_pag, row['Total_Paginas'])
                        save_data(df)
                        st.rerun()

                # Estimativa
                restam = row['Total_Paginas'] - row['Paginas_Lidas']
                dias = restam / velocidade
                st.caption(f"Faltam {restam} págs. Término est.: {datetime.now() + timedelta(days=dias):%d/%m}")
                
                # Controles de Edição
                render_edit_controls(idx, row)

    # ==========================
    # ABA: FILA
    # ==========================
    with tab_fila:
        df_fila = df[df['Status'] == "Na Fila"]
        if df_fila.empty: st.info("Fila vazia.")
        
        for idx, row in df_fila.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{row['Titulo']}** - {row['Autor']} ({row['Total_Paginas']} pág.)")
                if c2.button("▶️ Ler", key=f"start_{idx}"):
                    df.at[idx, 'Paginas_Lidas'] = 1
                    save_data(df)
                    st.rerun()
                
                render_edit_controls(idx, row)

    # ==========================
    # ABA: CONCLUÍDOS
    # ==========================
    with tab_concluidos:
        df_conc = df[df['Status'] == "Concluído"]
        if df_conc.empty: st.info("Nenhum livro concluído.")
        
        for idx, row in df_conc.iterrows():
            with st.container(border=True):
                st.write(f"✅ **{row['Titulo']}**")
                
                # Avaliação
                nota = st.selectbox(
                    "Nota", [0,1,2,3,4,5], 
                    index=int(row['Nota']), 
                    format_func=lambda x: "⭐"*x if x>0 else "Avaliar",
                    key=f"rate_{idx}"
                )
                if nota != row['Nota']:
                    df.at[idx, 'Nota'] = nota
                    save_data(df)
                    st.rerun()
                
                render_edit_controls(idx, row)