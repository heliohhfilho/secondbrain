import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import os

# --- ARQUIVOS ---
PATH_FILMES = os.path.join('data', 'filmes_watchlist.csv')

def load_data():
    if not os.path.exists(PATH_FILMES):
        return pd.DataFrame(columns=[
            "ID", "Titulo", "Diretor", "Genero", "Ano", 
            "Onde_Assistir", "Status", "Nota_0_10", "Review", "Data_Add"
        ])
    return pd.read_csv(PATH_FILMES)

def save_data(df):
    df.to_csv(PATH_FILMES, index=False)

def render_page():
    st.header("🎬 Cinephile Tracker")
    st.caption("Acompanhe sua jornada pelos clássicos e lançamentos.")
    
    df = load_data()
    
    # --- SIDEBAR: ADICIONAR FILME ---
    with st.sidebar:
        st.subheader("➕ Adicionar Filme")
        with st.form("form_filme"):
            f_titulo = st.text_input("Título (Ex: O Iluminado)")
            f_diretor = st.text_input("Diretor (Ex: Stanley Kubrick)")
            f_genero = st.selectbox("Gênero", ["Drama", "Sci-Fi", "Terror", "Ação", "Comédia", "Thriller", "Documentário", "Animação", "Clássico/Cult"])
            f_ano = st.number_input("Ano de Lançamento", 1900, 2030, 1980)
            f_onde = st.selectbox("Onde Assistir?", ["Netflix", "Prime Video", "HBO Max", "Disney+", "Apple TV", "Cinema", "Torresmo/Jack Sparrow", "Outro"])
            f_status = st.selectbox("Status", ["Para Assistir", "Assistido"])
            
            # Se já assistiu, pede nota
            st.markdown("---")
            st.caption("Se já assistiu:")
            f_nota = st.slider("Nota (0-10)", 0.0, 10.0, 0.0, 0.1)
            f_review = st.text_area("Review / Comentários")
            
            if st.form_submit_button("Salvar Filme"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, "Titulo": f_titulo, "Diretor": f_diretor,
                    "Genero": f_genero, "Ano": f_ano, "Onde_Assistir": f_onde,
                    "Status": f_status, "Nota_0_10": f_nota if f_status == "Assistido" else 0.0,
                    "Review": f_review if f_status == "Assistido" else "",
                    "Data_Add": date.today()
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Filme adicionado ao rolo!")
                st.rerun()

    # --- DASHBOARD RÁPIDO ---
    if not df.empty:
        assistidos = df[df['Status'] == "Assistido"]
        watchlist = df[df['Status'] == "Para Assistir"]
        
        # Filtro Kubrick (Já que você mencionou!)
        kubrick_count = len(df[df['Diretor'].str.contains("Kubrick", case=False, na=False)])
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total na Lista", len(df))
        c2.metric("Já Assistidos", len(assistidos))
        c3.metric("Fila de Espera", len(watchlist))
        c4.metric("Coleção Kubrick", kubrick_count, "Diretor Favorito")
        
        st.divider()
        
        # --- ABAS ---
        t1, t2, t3 = st.tabs(["🍿 Watchlist (Fila)", "✅ Já Assistidos", "📊 Estatísticas"])
        
        with t1:
            if not watchlist.empty:
                for idx, row in watchlist.iterrows():
                    with st.container(border=True):
                        c_img, c_info, c_act = st.columns([1, 4, 2])
                        
                        with c_img:
                            st.markdown("## 🎞️") # Placeholder pra poster
                            
                        with c_info:
                            st.markdown(f"**{row['Titulo']}** ({row['Ano']})")
                            st.caption(f"Dir. {row['Diretor']} | {row['Genero']}")
                            st.info(f"📍 Disponível em: **{row['Onde_Assistir']}**")
                            
                        with c_act:
                            if st.button("Marcar como Visto", key=f"seen_{row['ID']}"):
                                # Abre um mini form ou apenas marca e pede pra editar depois?
                                # Vamos marcar e o usuário edita a nota depois pra ser rápido
                                df.loc[df['ID'] == row['ID'], 'Status'] = "Assistido"
                                df.loc[df['ID'] == row['ID'], 'Data_Add'] = date.today() # Atualiza data pra hoje
                                save_data(df)
                                st.balloons()
                                st.rerun()
                                
                            if st.button("🗑️", key=f"del_w_{row['ID']}"):
                                df = df[df['ID'] != row['ID']]
                                save_data(df)
                                st.rerun()
            else:
                st.info("Sua fila está vazia! Adicione clássicos.")

        with t2:
            if not assistidos.empty:
                # Ordenar por nota
                assistidos = assistidos.sort_values("Nota_0_10", ascending=False)
                
                for idx, row in assistidos.iterrows():
                    with st.container(border=True):
                        c_tit, c_nota = st.columns([4, 1])
                        c_tit.markdown(f"### {row['Titulo']}")
                        c_tit.caption(f"Dir. {row['Diretor']} | {row['Ano']}")
                        
                        cor = "green" if row['Nota_0_10'] >= 9 else "orange" if row['Nota_0_10'] >= 7 else "red"
                        c_nota.markdown(f"<h2 style='color:{cor}; text-align:right'>{row['Nota_0_10']}</h2>", unsafe_allow_html=True)
                        
                        if row['Review']:
                            st.markdown(f"> _{row['Review']}_")
                            
                        # Botão de editar nota (Expand)
                        with st.expander("Editar Nota/Review"):
                            with st.form(f"edit_{row['ID']}"):
                                n_nota = st.slider("Nova Nota", 0.0, 10.0, float(row['Nota_0_10']))
                                n_rev = st.text_area("Review", row['Review'])
                                if st.form_submit_button("Atualizar"):
                                    df.loc[df['ID'] == row['ID'], 'Nota_0_10'] = n_nota
                                    df.loc[df['ID'] == row['ID'], 'Review'] = n_rev
                                    save_data(df)
                                    st.rerun()
            else:
                st.info("Nenhum filme assistido registrado.")

        with t3:
            if not df.empty:
                c_bar, c_pie = st.columns(2)
                with c_bar:
                    st.markdown("#### Diretores Mais Assistidos")
                    top_dir = df[df['Status']=='Assistido']['Diretor'].value_counts().head(5)
                    st.bar_chart(top_dir)
                    
                with c_pie:
                    st.markdown("#### Gêneros")
                    fig = px.pie(df, names='Genero', hole=0.4)
                    st.plotly_chart(fig, use_container_width=True)