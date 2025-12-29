import streamlit as st
import pandas as pd
import requests
from datetime import date, datetime, timedelta
from modules import conexoes

# --- CONFIGURAÇÃO API ---
# Certifique-se de que TMDB_READ_TOKEN está no seu secrets.toml
TMDB_BASE_URL = "https://api.themoviedb.org/3"
HEADERS = {
    "Authorization": f"Bearer {st.secrets['TMDB_READ_TOKEN']}",
    "accept": "application/json"
}

# --- FUNÇÕES DE DADOS (CRUD) ---
def load_data():
    """Carrega as tabelas Mestre e de Log da nuvem"""
    df_master = conexoes.load_gsheet("Series_Master", ["ID_TMDB", "Titulo", "Status", "Poster_URL", "Total_Seasons"])
    df_log = conexoes.load_gsheet("Series_Log", ["ID_TMDB", "Titulo", "Temporada", "Episodio", "Nome_Epi", "Data_Estreia", "Visto", "Nota", "Data_Visto"])
    
    # Saneamento de Tipos
    if not df_master.empty:
        df_master["ID_TMDB"] = df_master["ID_TMDB"].astype(str)
    
    if not df_log.empty:
        df_log["ID_TMDB"] = df_log["ID_TMDB"].astype(str)
        df_log["Temporada"] = pd.to_numeric(df_log["Temporada"], errors='coerce').fillna(0).astype(int)
        df_log["Episodio"] = pd.to_numeric(df_log["Episodio"], errors='coerce').fillna(0).astype(int)
        df_log["Nota"] = pd.to_numeric(df_log["Nota"], errors='coerce').fillna(0).astype(int)
        df_log["Visto"] = df_log["Visto"].astype(str).str.upper() == "TRUE"
        
    return df_master, df_log

def save_master(df):
    conexoes.save_gsheet("Series_Master", df)

def save_log(df):
    # Converte boleanos e datas para string antes de subir
    df_save = df.copy()
    df_save["Visto"] = df_save["Visto"].astype(str).upper()
    conexoes.save_gsheet("Series_Log", df_save)

# --- INTEGRAÇÃO TMDB (ENGINE) ---
def search_tv_show(query):
    url = f"{TMDB_BASE_URL}/search/tv?query={query}&language=pt-BR"
    try:
        resp = requests.get(url, headers=HEADERS)
        return resp.json().get('results', [])
    except: return []

def fetch_all_episodes(tmdb_id, titulo, total_seasons):
    """Varre todas as temporadas e retorna uma lista de episódios"""
    novos_episodios = []
    
    # Barra de progresso visual no Streamlit
    progress_bar = st.progress(0)
    
    for season_num in range(1, total_seasons + 1):
        url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_num}?language=pt-BR"
        try:
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                for ep in data.get('episodes', []):
                    novos_episodios.append({
                        "ID_TMDB": str(tmdb_id),
                        "Titulo": titulo,
                        "Temporada": season_num,
                        "Episodio": ep['episode_number'],
                        "Nome_Epi": ep['name'],
                        "Data_Estreia": ep['air_date'] if ep['air_date'] else "Futuro",
                        "Visto": False,
                        "Nota": 0,
                        "Data_Visto": ""
                    })
        except: pass
        progress_bar.progress(season_num / total_seasons)
        
    progress_bar.empty()
    return novos_episodios

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎬 TV Time: Ultimate Tracker")
    df_master, df_log = load_data()

    # Abas Principais
    tab_track, tab_add, tab_calendar, tab_manage = st.tabs(["📺 Assistir Agora", "🔍 Adicionar Série", "🗓️ Calendário", "⚙️ Gerenciar"])

    # ------------------------------------------------------------------
    # ABA 1: TRACKER (O que assistir agora?)
    # ------------------------------------------------------------------
    with tab_track:
        if df_master.empty:
            st.info("Nenhuma série ativa. Adicione na aba de busca!")
        else:
            # Filtra apenas séries ATIVAS
            series_ativas = df_master[df_master['Status'] == 'Ativo']
            
            for _, serie in series_ativas.iterrows():
                # Pega log desta série
                df_s = df_log[df_log['ID_TMDB'] == str(serie['ID_TMDB'])].sort_values(['Temporada', 'Episodio'])
                
                # Descobre o próximo episódio (Primeiro que Visto == False)
                pendentes = df_s[df_s['Visto'] == False]
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if serie['Poster_URL']:
                            st.image(f"https://image.tmdb.org/t/p/w200{serie['Poster_URL']}")
                        else:
                            st.write("🎬")
                    
                    with c2:
                        st.subheader(serie['Titulo'])
                        
                        if not pendentes.empty:
                            proximo = pendentes.iloc[0]
                            idx_real = proximo.name # Index original do DataFrame
                            
                            st.markdown(f"**Próximo:** T{proximo['Temporada']}E{proximo['Episodio']} - *{proximo['Nome_Epi']}*")
                            st.caption(f"Estreia: {proximo['Data_Estreia']}")
                            
                            # Ações Rápidas
                            col_b1, col_b2 = st.columns([1, 2])
                            
                            # Botão Marcar Visto
                            if col_b1.button("✅ Visto", key=f"chk_{serie['ID_TMDB']}"):
                                df_log.at[idx_real, 'Visto'] = True
                                df_log.at[idx_real, 'Data_Visto'] = str(date.today())
                                save_log(df_log)
                                st.rerun()
                                
                            # Avaliação (Selectbox para não ocupar espaço)
                            nota = col_b2.selectbox("Nota", [0,1,2,3,4,5], key=f"rate_{serie['ID_TMDB']}", 
                                                  format_func=lambda x: "⭐"*x if x>0 else "Avaliar")
                            if nota > 0 and nota != proximo['Nota']:
                                df_log.at[idx_real, 'Nota'] = nota
                                save_log(df_log) # Salva nota mesmo sem marcar visto
                                
                        else:
                            st.success("🎉 Tudo assistido! Aguardando novos episódios.")

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR (Integração TMDB)
    # ------------------------------------------------------------------
    with tab_add:
        query = st.text_input("Buscar Série no TMDB", placeholder="Ex: Breaking Bad")
        if query:
            results = search_tv_show(query)
            if results:
                for res in results[:3]: # Top 3 resultados
                    with st.expander(f"{res['name']} ({res.get('first_air_date', '')[:4]})"):
                        c_img, c_det = st.columns([1, 3])
                        with c_img:
                            poster = res.get('poster_path')
                            if poster: st.image(f"https://image.tmdb.org/t/p/w200{poster}")
                        with c_det:
                            st.write(res.get('overview', 'Sem descrição.'))
                            
                            # Botão de Importação Mágica
                            if st.button("➕ Adicionar ao Tracker", key=f"add_{res['id']}"):
                                # 1. Adiciona à Master
                                novo_master = {
                                    "ID_TMDB": str(res['id']),
                                    "Titulo": res['name'],
                                    "Status": "Ativo",
                                    "Poster_URL": res.get('poster_path', ''),
                                    "Total_Seasons": 0 # Será atualizado ou ignorado, usamos o log
                                }
                                # Verifica duplicidade
                                if not df_master[df_master['ID_TMDB'] == str(res['id'])].empty:
                                    st.warning("Série já está na lista!")
                                else:
                                    # Pega detalhes para saber temporadas
                                    url_det = f"{TMDB_BASE_URL}/tv/{res['id']}?language=pt-BR"
                                    detalhes = requests.get(url_det, headers=HEADERS).json()
                                    novo_master['Total_Seasons'] = detalhes.get('number_of_seasons', 1)
                                    
                                    df_master = pd.concat([df_master, pd.DataFrame([novo_master])], ignore_index=True)
                                    save_master(df_master)
                                    
                                    # 2. Busca e Adiciona TODOS os Episódios ao Log
                                    with st.spinner("Baixando guia de episódios..."):
                                        eps = fetch_all_episodes(res['id'], res['name'], novo_master['Total_Seasons'])
                                        if eps:
                                            df_log = pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True)
                                            save_log(df_log)
                                            st.success(f"{len(eps)} episódios importados com sucesso!")
                                            st.rerun()
            else:
                st.warning("Nenhum resultado encontrado.")

    # ------------------------------------------------------------------
    # ABA 3: CALENDÁRIO (Próximas Estreias)
    # ------------------------------------------------------------------
    with tab_calendar:
        st.subheader("🗓️ Próximos Lançamentos")
        # Filtra episódios não vistos que têm data de estreia no futuro ou hoje
        if not df_log.empty:
            hoje = date.today().strftime('%Y-%m-%d')
            
            # Filtra datas válidas
            df_futuro = df_log[
                (df_log['Data_Estreia'] >= hoje) & 
                (df_log['Data_Estreia'] != "Futuro") &
                (df_log['Visto'] == False)
            ].sort_values('Data_Estreia')
            
            if not df_futuro.empty:
                for _, row in df_futuro.head(10).iterrows():
                    st.info(f"**{row['Data_Estreia']}**: {row['Titulo']} - T{row['Temporada']}E{row['Episodio']} ({row['Nome_Epi']})")
            else:
                st.write("Nenhuma estreia próxima agendada nas suas séries.")
        else:
            st.write("Adicione séries para ver o calendário.")

    # ------------------------------------------------------------------
    # ABA 4: GERENCIAR (Pausar/Remover)
    # ------------------------------------------------------------------
    with tab_manage:
        if not df_master.empty:
            st.subheader("Gerenciar Catálogo")
            
            # Edição de Status (Ativo/Pausado)
            edited_df = st.data_editor(
                df_master[["ID_TMDB", "Titulo", "Status"]], 
                key="editor_status", 
                disabled=["ID_TMDB", "Titulo"],
                column_config={
                    "Status": st.column_config.SelectboxColumn("Status", options=["Ativo", "Pausado", "Finalizado"])
                }
            )
            
            if st.button("Salvar Alterações de Status"):
                # Atualiza o df_master original com as mudanças
                for idx, row in edited_df.iterrows():
                    # Localiza no df original pelo ID (mais seguro que index se houver filtro)
                    mask = df_master['ID_TMDB'] == row['ID_TMDB']
                    if mask.any():
                        df_master.loc[mask, 'Status'] = row['Status']
                save_master(df_master)
                st.success("Status atualizados!")
            
            st.divider()
            
            # Zona de Exclusão
            st.subheader("🗑️ Remover Série")
            serie_del = st.selectbox("Selecione para excluir permanentemente:", df_master['Titulo'].unique())
            if st.button("EXCLUIR SÉRIE"):
                # Pega ID
                id_del = df_master[df_master['Titulo'] == serie_del].iloc[0]['ID_TMDB']
                
                # Remove da Master
                df_master = df_master[df_master['ID_TMDB'] != id_del]
                save_master(df_master)
                
                # Remove do Log (Episódios)
                df_log = df_log[df_log['ID_TMDB'] != id_del]
                save_log(df_log)
                
                st.success("Série removida do sistema.")
                st.rerun()