import streamlit as st
import os

from modules import produtividade, viagens, faculdade, leituras, cursos, compras, projetos, financeiro, daytrade, dashboard, bio, alma, negocio, conhecimento, metas, hobbies, carros, decisoes, eisenhower, fear_setting, musica, filmes, cartoes, investimentos, series, criatividade

st.set_page_config(
    page_title="Segundo Cérebro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

if not os.path.exists("data"):
    os.makedirs("data")

# --- SIDEBAR --- #

with st.sidebar:
    st.title("🧠 Segundo Cérebro")
    st.markdown("---")

    choice = st.radio(
        "Navegue por aqui:",
        [
            "Dashboard",
            "Produtividade", 
            "Financeiro",
            "Investimentos",
            "Projetos", 
            "Viagens", 
            "Faculdade",
            "Leituras",
            "Cursos",
            "Compras",
            "DayTrade",
            "Bio-Data",
            "Alma",
            "Negócio",
            "Conhecimento",
            "Metas",
            "Hobbies",
            "Carros",
            "Decisões",
            "Eisenhower",
            "Fear Setting",
            "Musica",
            "Filmes",
            "Series",
            "Cartões",
            "Criatividade"
            ]
    )
    st.markdown("---")
    st.caption("V1.0 -- Helio")

    if st.sidebar.button("🔄 Sincronizar Nuvem"):
        st.cache_data.clear()
        st.rerun()

# --- ROTEAMENTO --- #

if choice == "Produtividade":
    produtividade.render_page()

if choice == "Viagens":
    viagens.render_page()

if choice == "Faculdade":
    faculdade.render_page()

if choice == "Leituras":
    leituras.render_page()

if choice == "Cursos":
    cursos.render_page()

if choice == "Compras":
    compras.render_page()

if choice == "Projetos":
    projetos.render_page()

if choice == "Financeiro":
    financeiro.render_page()

if choice == "DayTrade":
    daytrade.render_page()

if choice == "Dashboard":
    dashboard.render_page()

if choice == "Bio-Data":
    bio.render_page()

if choice == "Alma":
    alma.render_page()

if choice == "Negócio":
    negocio.render_page()

if choice == "Conhecimento":
    conhecimento.render_page()

if choice == "Metas":
    metas.render_page()

if choice == "Hobbies":
    hobbies.render_page()

if choice == "Carros":
    carros.render_page()

if choice == "Decisões":
    decisoes.render_page()

if choice == "Eisenhower":
    eisenhower.render_page()

if choice == "Fear Setting":
    fear_setting.render_page()

if choice == "Musica":
    musica.render_page()

if choice == "Filmes":
    filmes.render_page()

if choice == "Cartões":
    cartoes.render_page()

if choice == "Investimentos":
    investimentos.render_page()

if choice == "Series":
    series.render_page()

if choice == "Criatividade":
    criatividade.render_page()