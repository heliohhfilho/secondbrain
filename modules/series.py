import streamlit as st
import requests
import pandas as pd
from datetime import datetime
from modules import conexoes

# Configurações da API
TMDB_BASE_URL = "https://api.themoviedb.org/3"
HEADERS = {
    "Authorization": f"Bearer {st.secrets['TMDB_READ_TOKEN']}",
    "accept": "application/json"
}

def get_series_metadata(tmdb_id):
    """Busca dados técnicos da série, temporadas e episódios via TMDB"""
    url = f"{TMDB_BASE_URL}/tv/{tmdb_id}?language=pt-BR"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else None

def get_season_details(tmdb_id, season_number):
    """Busca a lista de episódios de uma temporada específica"""
    url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_number}?language=pt-BR"
    response = requests.get(url, headers=HEADERS)
    return response.json() if response.status_code == 200 else None

def sync_tmdb_to_sheets(tmdb_id, serie_titulo):
    """Função de Automação: Sincroniza episódios novos com o Log"""
    data = get_series_metadata(tmdb_id)
    if not data: return st.error("Erro ao conectar com TMDB")

    # Carrega seus logs atuais
    _, df_log = load_series_data() # Supondo que você já tenha essa função
    
    novos_episodios = []
    
    # Varre todas as temporadas retornadas pela API
    for season in data['seasons']:
        s_num = season['season_number']
        if s_num == 0: continue # Ignora especiais
        
        details = get_season_details(tmdb_id, s_num)
        if details:
            for epi in details['episodes']:
                # Verifica se você já tem esse episódio no Log
                exists = not df_log[(df_log['Titulo'] == serie_titulo) & 
                                   (df_log['Temporada'] == s_num) & 
                                   (df_log['Episodio'] == epi['episode_number'])].empty
                
                if not exists:
                    # Se não existe, prepara para adicionar como 'Pendente'
                    novos_episodios.append({
                        "Titulo": serie_titulo,
                        "Temporada": s_num,
                        "Episodio": epi['episode_number'],
                        "Nome_Epi": epi['name'],
                        "Nota_Estrelas": 0, # Você avaliará depois
                        "Data_Visto": "Pendente"
                    })
    
    if novos_episodios:
        df_new = pd.concat([df_log, pd.DataFrame(novos_episodios)], ignore_index=True)
        conexoes.save_gsheet("Series_Log", df_new)
        return len(novos_episodios)
    return 0

def render_page():
    st.header("🎬 TV Time Pro: Segundo Cérebro")
    
    # Interface para adicionar nova série via Busca
    with st.expander("🔍 Adicionar Série via TMDB"):
        query = st.text_input("Buscar nome da série...")
        if query:
            search_url = f"{TMDB_BASE_URL}/search/tv?query={query}&language=pt-BR"
            results = requests.get(search_url, headers=HEADERS).json().get('results', [])
            
            for res in results[:3]: # Mostra os 3 primeiros
                col1, col2 = st.columns([1, 3])
                with col1:
                    st.image(f"https://image.tmdb.org/t/p/w200{res['poster_path']}")
                with col2:
                    st.write(f"**{res['name']}** ({res['first_air_date'][:4]})")
                    if st.button("Importar Catálogo Completo", key=res['id']):
                        with st.spinner("Sincronizando episódios..."):
                            count = sync_tmdb_to_sheets(res['id'], res['name'])
                            # Salva também na Master
                            # ... lógica para salvar na Series_Master ...
                            st.success(f"{count} episódios importados!")
                            st.rerun()

    # --- ABA DE CALENDÁRIO ---
    # Aqui você pode usar os dados de 'air_date' da API para montar o seu calendário