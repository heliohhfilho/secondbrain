import streamlit as st
import os

# Mantenha seus imports originais aqui
from modules import produtividade, faculdade, leitura, cursos, corpo, negocio, conhecimento, metas, carros
from modules import dashboard, dump
#viagens, projetos, financeiro, daytrade,financeiro, daytrade, dashboard,hobbies,  decisoes, eisenhower, fear_setting, musica, filmes, series

st.set_page_config(
    page_title="Segundo Cérebro",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CSS INJECTION (CYBERPUNK AESTHETIC) ---
st.markdown("""
<style>
    /* 1. IMPORTANDO RAJDHANI */
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@300;400;500;600;700&display=swap');

    /* 2. VARIÁVEIS DE TEMA */
    :root {
        --neon-yellow: #FCEE0A;
        --neon-cyan: #00F0FF;
        --matrix-bg: #000000;
        --hud-gray: #1a1a1a;
    }

    /* 3. RESET GLOBAL */
    html, body, [class*="css"], .stApp {
        font-family: 'Rajdhani', sans-serif !important;
        background-color: var(--matrix-bg);
        color: #e0e0e0; /* Cor texto padrão (branco gelo) */
    }

    /* 4. TÍTULOS (H1, H2, H3) - FORÇANDO AMARELO */
    h1, h2, h3, .stHeadingContainer h1, .stHeadingContainer h2, .stHeadingContainer h3 {
        color: var(--neon-yellow) !important;
        font-weight: 700 !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        text-shadow: 0 0 10px rgba(252, 238, 10, 0.4); /* Glow amarelo suave */
        border-bottom: 2px solid var(--neon-cyan); /* Linha ciano embaixo dos títulos */
        padding-bottom: 5px;
    }

    /* 5. SIDEBAR */
    [data-testid="stSidebar"] {
        background-color: #050505;
        border-right: 1px solid var(--neon-cyan);
    }
    
    /* 6. MENU DE NAVEGAÇÃO (RADIO BUTTONS CUSTOMIZADOS) */
    
    /* Esconde as bolinhas originais */
    [data-testid="stSidebar"] [role="radiogroup"] > label > div:first-child {
        display: none;
    }

    /* Estilo dos Botões do Menu */
    [data-testid="stSidebar"] [role="radiogroup"] label {
        padding: 12px 20px;
        background: rgba(255, 255, 255, 0.03);
        margin-bottom: 3px;
        transition: all 0.2s ease-in-out;
        border-left: 3px solid transparent;
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 18px !important;
        text-transform: uppercase;
        color: #888; /* Cor inativa */
        cursor: pointer;
    }

    /* Hover (Mouse em cima) */
    [data-testid="stSidebar"] [role="radiogroup"] label:hover {
        color: var(--neon-cyan) !important;
        background: rgba(0, 240, 255, 0.1);
        border-left: 3px solid var(--neon-cyan);
        padding-left: 25px; /* Efeito de deslizar */
    }

    /* Item Ativo (Selecionado) */
    [data-testid="stSidebar"] [role="radiogroup"] [data-checked="true"] {
        background: rgba(252, 238, 10, 0.1) !important;
        color: var(--neon-yellow) !important;
        border-left: 5px solid var(--neon-yellow) !important;
        font-weight: 700 !important;
        text-shadow: 0 0 5px var(--neon-yellow);
    }

    /* 7. BOTÕES GERAIS (st.button) */
    .stButton button {
        background-color: transparent;
        border: 1px solid var(--neon-cyan);
        color: var(--neon-cyan);
        border-radius: 0px; /* Canto reto */
        text-transform: uppercase;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 600;
        transition: 0.3s;
    }
    
    .stButton button:hover {
        background-color: var(--neon-cyan);
        color: #000;
        box-shadow: 0 0 15px var(--neon-cyan);
    }

</style>
""", unsafe_allow_html=True)

if not os.path.exists("data"):
    os.makedirs("data")

# --- SIDEBAR --- #
with st.sidebar:
    st.markdown("<h1 style='text-align: center; border-bottom: 2px solid #FCEE0A; padding-bottom: 10px;'>🧠 NEURAL_LINK</h1>", unsafe_allow_html=True)
    
    # Menu Principal
    choice = st.radio(
        "NAVIGATION MODULES:", # Label escondida visualmente se quiser, ou estilizada
        [
            "Dashboard", "Produtividade", "Financeiro", "Projetos", "Viagens",
            "Dump", "Faculdade", "Leituras", "Cursos",
            "DayTrade", "Bio-Data", "Negócio", "Conhecimento",
            "Metas", "Hobbies", "Carros", "Decisões", "Eisenhower",
            "Fear Setting", "Musica", "Filmes", "Series", "Linguagens"
        ],
        label_visibility="collapsed" # Esconde o título "Navigation Modules" para limpar o visual
    )

    st.markdown("---")
    
    # Botão Sincronizar (Estilo Cyberpunk)
    if st.button("⚡ SYNC_CLOUD"):
        st.cache_data.clear()
        st.rerun()
    
    st.markdown("<div style='text-align: right; color: #555; font-size: 0.8em; margin-top: 20px;'>SYS_ID: HELIO_V1</div>", unsafe_allow_html=True)

# --- LOGICA DE ROTEAMENTO (MANTIDA) ---
# Dica de Engenharia: Dict mapping é mais performático que múltiplos IFs
pages = {
    "Dashboard": dashboard, 
    "Produtividade": produtividade,
    "Faculdade": faculdade,
    "Leituras": leitura, 
    "Cursos": cursos,
    "Bio-Data": corpo, 
    "Negócio": negocio, 
    "Conhecimento": conhecimento,
    "Metas": metas,
    "Carros": carros,
    "Dump": dump,
}
"""
    "Financeiro": financeiro,
    "Projetos": projetos, "Viagens": viagens
    "DayTrade": daytrade,
    "Bio-Data": corpo,
    "Hobbies": hobbies, "Decisões": decisoes,
    "Eisenhower": eisenhower, "Fear Setting": fear_setting, "Musica": musica,
    "Filmes": filmes, "Series": series

"""
if choice in pages:
    pages[choice].render_page()