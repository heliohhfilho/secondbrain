import streamlit as st
import pandas as pd
import requests
import plotly.express as px
from datetime import date
from modules import conexoes

# --- CONFIGURAÇÃO API ---
TMDB_BASE_URL = "https://api.themoviedb.org/3"
try:
    HEADERS = {
        "Authorization": f"Bearer {st.secrets['TMDB_READ_TOKEN']}",
        "accept": "application/json"
    }
except:
    HEADERS = {}

# --- FUNÇÕES DADOS ---
def load_data():
    cols = ["ID_TMDB", "Titulo", "Diretor", "Ano", "Genero", "Poster_URL", "Status", "Nota", "Review", "Data_Visto"]
    df = conexoes.load_gsheet("Filmes", cols)
    
    if not df.empty:
        df["ID_TMDB"] = df["ID_TMDB"].astype(str)
        df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce').fillna(0).astype(int)
        df["Nota"] = pd.to_numeric(df["Nota"], errors='coerce').fillna(0.0)
    return df

def save_data(df):
    df_save = df.copy()
    conexoes.save_gsheet("Filmes", df_save)

# --- INTEGRAÇÃO TMDB ---
def search_movie(query):
    url = f"{TMDB_BASE_URL}/search/movie?query={query}&language=pt-BR"
    try:
        return requests.get(url, headers=HEADERS).json().get('results', [])
    except: return []

def get_movie_details(tmdb_id):
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}?language=pt-BR&append_to_response=credits"
    try:
        data = requests.get(url, headers=HEADERS).json()
        diretor = "Desconhecido"
        # Busca Diretor nos Créditos
        for crew in data.get('credits', {}).get('crew', []):
            if crew['job'] == 'Director':
                diretor = crew['name']
                break
        
        genero = data['genres'][0]['name'] if data.get('genres') else "Geral"
        
        return {
            "Diretor": diretor,
            "Genero": genero,
            "Poster_URL": data.get('poster_path'),
            "Overview": data.get('overview')
        }
    except: return {}

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎬 Cinephile Tracker")
    df = load_data()

    tab_gallery, tab_add, tab_stats = st.tabs(["🍿 Galeria", "🔍 Adicionar Filme", "📊 Estatísticas"])

    # ------------------------------------------------------------------
    # ABA 1: GALERIA (Visual)
    # ------------------------------------------------------------------
    with tab_gallery:
        if df.empty:
            st.info("Sua videoteca está vazia.")
        else:
            # Filtros
            f_status = st.radio("Filtro", ["Todos", "Assistido", "Para Ver"], horizontal=True)
            df_view = df if f_status == "Todos" else df[df['Status'] == f_status]
            
            # Grid de Posters (3 por linha)
            cols = st.columns(3)
            for idx, (i, row) in enumerate(df_view.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        # Poster
                        if row['Poster_URL']:
                            st.image(f"https://image.tmdb.org/t/p/w200{row['Poster_URL']}", use_column_width=True)
                        else:
                            st.write("🎬")
                        
                        st.write(f"**{row['Titulo']}** ({row['Ano']})")
                        
                        if row['Status'] == 'Assistido':
                            st.caption(f"⭐ {row['Nota']}/5 | Dir. {row['Diretor']}")
                        else:
                            if st.button("✅ Vi", key=f"seen_{row['ID_TMDB']}"):
                                df.at[i, 'Status'] = 'Assistido'
                                df.at[i, 'Data_Visto'] = str(date.today())
                                save_data(df); st.rerun()
                        
                        with st.popover("📝 Detalhes / Review"):
                            st.write(f"**Gênero:** {row['Genero']}")
                            new_nota = st.slider("Nota", 0.0, 5.0, float(row['Nota']), key=f"sl_{row['ID_TMDB']}")
                            new_review = st.text_area("Review", row['Review'], key=f"tx_{row['ID_TMDB']}")
                            
                            if st.button("Salvar Review", key=f"sv_{row['ID_TMDB']}"):
                                df.at[i, 'Nota'] = new_nota
                                df.at[i, 'Review'] = new_review
                                df.at[i, 'Status'] = 'Assistido' # Força status se avaliou
                                save_data(df); st.rerun()
                            
                            if st.button("🗑️ Remover", key=f"del_{row['ID_TMDB']}"):
                                save_data(df.drop(i)); st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR (Busca Automática)
    # ------------------------------------------------------------------
    with tab_add:
        q = st.text_input("Buscar Filme", placeholder="O Poderoso Chefão")
        if q:
            results = search_movie(q)
            if results:
                for res in results[:3]:
                    with st.expander(f"{res['title']} ({res.get('release_date', '')[:4]})"):
                        c1, c2 = st.columns([1, 4])
                        if res.get('poster_path'): c1.image(f"https://image.tmdb.org/t/p/w200{res['poster_path']}")
                        c2.write(res.get('overview', ''))
                        
                        if c2.button("➕ Adicionar à Galeria", key=f"add_{res['id']}"):
                            if df[df['ID_TMDB'] == str(res['id'])].empty:
                                # Busca detalhes extras (Diretor)
                                dets = get_movie_details(res['id'])
                                
                                new_movie = {
                                    "ID_TMDB": str(res['id']),
                                    "Titulo": res['title'],
                                    "Diretor": dets.get('Diretor', 'Desconhecido'),
                                    "Ano": res.get('release_date', '0000')[:4],
                                    "Genero": dets.get('Genero', 'Geral'),
                                    "Poster_URL": res.get('poster_path'),
                                    "Status": "Para Ver",
                                    "Nota": 0, "Review": "", "Data_Visto": ""
                                }
                                save_data(pd.concat([df, pd.DataFrame([new_movie])], ignore_index=True))
                                st.success("Filme adicionado!"); st.rerun()
                            else:
                                st.warning("Filme já está na lista!")

    # ------------------------------------------------------------------
    # ABA 3: ESTATÍSTICAS
    # ------------------------------------------------------------------
    with tab_stats:
        if not df.empty:
            vistos = df[df['Status'] == 'Assistido']
            c1, c2 = st.columns(2)
            c1.markdown("#### Diretores Mais Vistos")
            c1.bar_chart(vistos['Diretor'].value_counts().head(5))
            
            c2.markdown("#### Gêneros")
            fig = px.pie(df, names='Genero', hole=0.4)
            c2.plotly_chart(fig, width=True)
            
            st.metric("Total de Filmes Vistos", len(vistos))