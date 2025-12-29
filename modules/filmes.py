import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import os
from modules import conexao # <--- Conexão Nuvem

def load_data():
    cols = [
        "ID", "Titulo", "Diretor", "Genero", "Ano", 
        "Onde_Assistir", "Status", "Nota_0_10", "Review", "Data_Add"
    ]
    df = conexao.load_gsheet("Filmes", cols)
    
    if not df.empty:
        # Saneamento para cálculos estatísticos e visualização
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce').fillna(1980).astype(int)
        df["Nota_0_10"] = pd.to_numeric(df["Nota_0_10"], errors='coerce').fillna(0.0)
        df["Review"] = df["Review"].fillna("")
        df["Diretor"] = df["Diretor"].fillna("Desconhecido")
        
    return df

def save_data(df):
    # Converte tipos para garantir compatibilidade com GSheets
    df_save = df.copy()
    if "Data_Add" in df_save.columns:
        df_save["Data_Add"] = df_save["Data_Add"].astype(str)
    conexao.save_gsheet("Filmes", df_save)

def render_page():
    st.header("🎬 Cinephile Tracker")
    st.caption("Acompanhe sua jornada pelos clássicos e lançamentos na nuvem.")
    
    df = load_data()
    
    # --- SIDEBAR: ADICIONAR FILME ---
    with st.sidebar:
        st.subheader("➕ Adicionar Filme")
        with st.form("form_filme"):
            f_titulo = st.text_input("Título")
            f_diretor = st.text_input("Diretor")
            f_genero = st.selectbox("Gênero", ["Drama", "Sci-Fi", "Terror", "Ação", "Comédia", "Thriller", "Documentário", "Animação", "Clássico/Cult"])
            f_ano = st.number_input("Ano", 1900, 2030, 2024)
            f_onde = st.selectbox("Onde Assistir?", ["Netflix", "Prime Video", "HBO Max", "Disney+", "Apple TV", "Cinema", "Torresmo", "Outro"])
            f_status = st.selectbox("Status", ["Para Assistir", "Assistido"])
            
            st.markdown("---")
            f_nota = st.slider("Nota (0-10)", 0.0, 10.0, 0.0, 0.1)
            f_review = st.text_area("Review")
            
            if st.form_submit_button("Salvar no Rolo"):
                if f_titulo:
                    new_id = 1 if df.empty else int(df['ID'].max()) + 1
                    novo = {
                        "ID": new_id, "Titulo": f_titulo, "Diretor": f_diretor,
                        "Genero": f_genero, "Ano": f_ano, "Onde_Assistir": f_onde,
                        "Status": f_status, "Nota_0_10": f_nota if f_status == "Assistido" else 0.0,
                        "Review": f_review if f_status == "Assistido" else "",
                        "Data_Add": str(date.today())
                    }
                    df_up = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_up)
                    st.success("Filme sincronizado!")
                    st.rerun()

    if df.empty:
        st.info("Sua videoteca está vazia no Google Sheets.")
        return

    # --- DASHBOARD RÁPIDO ---
    assistidos = df[df['Status'] == "Assistido"]
    watchlist = df[df['Status'] == "Para Assistir"]
    kubrick_count = len(df[df['Diretor'].str.contains("Kubrick", case=False, na=False)])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(df))
    c2.metric("Vistos", len(assistidos))
    c3.metric("Fila", len(watchlist))
    c4.metric("Kubrick", kubrick_count, "Diretor Favorito")
    
    st.divider()
    t1, t2, t3 = st.tabs(["🍿 Watchlist", "✅ Assistidos", "📊 Stats"])
    
    with t1:
        if not watchlist.empty:
            for idx, row in watchlist.iterrows():
                with st.container(border=True):
                    c_info, c_act = st.columns([5, 2])
                    c_info.markdown(f"**{row['Titulo']}** ({row['Ano']})")
                    c_info.caption(f"Dir. {row['Diretor']} | {row['Onde_Assistir']}")
                    if c_act.button("Visto", key=f"seen_{row['ID']}"):
                        df.loc[df['ID'] == row['ID'], 'Status'] = "Assistido"
                        save_data(df)
                        st.rerun()
        else: st.info("Fila vazia.")

    with t2:
        if not assistidos.empty:
            assistidos = assistidos.sort_values("Nota_0_10", ascending=False)
            for idx, row in assistidos.iterrows():
                with st.container(border=True):
                    c_tit, c_nota = st.columns([4, 1])
                    c_tit.markdown(f"### {row['Titulo']}")
                    c_tit.caption(f"Dir. {row['Diretor']} | {row['Ano']}")
                    cor = "green" if row['Nota_0_10'] >= 8 else "orange" if row['Nota_0_10'] >= 6 else "red"
                    c_nota.markdown(f"<h2 style='color:{cor}; text-align:right'>{row['Nota_0_10']}</h2>", unsafe_allow_html=True)
                    if row['Review']: st.markdown(f"> _{row['Review']}_")
                    if st.button("🗑️", key=f"del_{row['ID']}"):
                        save_data(df[df['ID'] != row['ID']])
                        st.rerun()

    with t3:
        c_bar, c_pie = st.columns(2)
        with c_bar:
            st.markdown("#### Top Diretores")
            st.bar_chart(assistidos['Diretor'].value_counts().head(5))
        with c_pie:
            st.markdown("#### Gêneros")
            st.plotly_chart(px.pie(df, names='Genero', hole=0.4), use_container_width=True)