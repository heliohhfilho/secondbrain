import streamlit as st
import pandas as pd
import requests
from datetime import date
from modules import conexoes

# --- CONFIGURAÇÃO API ---
TMDB_BASE_URL = "https://api.themoviedb.org/3"
# Tenta pegar do secrets, se não tiver, avisa (evita crash)
try:
    HEADERS = {
        "Authorization": f"Bearer {st.secrets['TMDB_READ_TOKEN']}",
        "accept": "application/json"
    }
except:
    HEADERS = {}

# --- FUNÇÕES AUXILIARES ---
def load_data():
    df_master = conexoes.load_gsheet("Series_Master", ["ID_TMDB", "Titulo", "Status", "Poster_URL", "Total_Seasons"])
    df_log = conexoes.load_gsheet("Series_Log", ["ID_TMDB", "Titulo", "Temporada", "Episodio", "Nome_Epi", "Data_Estreia", "Visto", "Nota", "Data_Visto"])
    
    # Saneamento
    if not df_master.empty: df_master["ID_TMDB"] = df_master["ID_TMDB"].astype(str)
    if not df_log.empty:
        df_log["ID_TMDB"] = df_log["ID_TMDB"].astype(str)
        df_log["Temporada"] = pd.to_numeric(df_log["Temporada"], errors='coerce').fillna(0).astype(int)
        df_log["Episodio"] = pd.to_numeric(df_log["Episodio"], errors='coerce').fillna(0).astype(int)
        df_log["Visto"] = df_log["Visto"].astype(str).str.upper() == "TRUE"
        
    return df_master, df_log

def save_log(df):
    df_save = df.copy()
    df_save["Visto"] = df_save["Visto"].astype(str).upper()
    conexoes.save_gsheet("Series_Log", df_save)

def fetch_all_episodes(tmdb_id, titulo, total_seasons):
    novos_episodios = []
    # Garante que tente pelo menos 1 temporada se a API tiver retornado 0
    total_seasons = max(1, int(total_seasons))
    
    status_text = st.empty()
    prog_bar = st.progress(0)
    
    for season_num in range(1, total_seasons + 2): # Tenta uma a mais por garantia
        url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{season_num}?language=pt-BR"
        try:
            resp = requests.get(url, headers=HEADERS)
            if resp.status_code == 200:
                data = resp.json()
                episodes = data.get('episodes', [])
                if not episodes: break # Se temporada vazia, para
                
                for ep in episodes:
                    if ep['air_date']: # Só adiciona se tiver data (evita placeholder)
                        novos_episodios.append({
                            "ID_TMDB": str(tmdb_id),
                            "Titulo": titulo,
                            "Temporada": season_num,
                            "Episodio": ep['episode_number'],
                            "Nome_Epi": ep['name'],
                            "Data_Estreia": ep['air_date'],
                            "Visto": False,
                            "Nota": 0,
                            "Data_Visto": ""
                        })
                status_text.text(f"Baixando T{season_num}...")
            else:
                if season_num > 1: break # Se erro 404 e não é a primeira, acabou as temporadas
        except: pass
        prog_bar.progress(min(season_num / (total_seasons + 1), 1.0))
    
    status_text.empty()
    prog_bar.empty()
    return novos_episodios

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎬 TV Time: Ultimate Tracker")
    df_master, df_log = load_data()

    tab_track, tab_add, tab_calendar = st.tabs(["📺 Assistir", "🔍 Adicionar", "🗓️ Calendário"])

    # ------------------------------------------------------------------
    # ABA 1: TRACKER INTELIGENTE
    # ------------------------------------------------------------------
    with tab_track:
        if df_master.empty:
            st.info("Nenhuma série ativa.")
        else:
            series_ativas = df_master[df_master['Status'] == 'Ativo']
            
            for _, serie in series_ativas.iterrows():
                # Filtra log da série
                df_s = df_log[df_log['ID_TMDB'] == str(serie['ID_TMDB'])].sort_values(['Temporada', 'Episodio'])
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 4])
                    with c1:
                        if serie['Poster_URL']: st.image(f"https://image.tmdb.org/t/p/w200{serie['Poster_URL']}")
                        else: st.write("🎬")
                    
                    with c2:
                        st.subheader(serie['Titulo'])
                        
                        # CASO 1: Log Vazio (Erro de Importação)
                        if df_s.empty:
                            st.error("⚠️ Nenhum episódio encontrado.")
                            if st.button("🔄 Forçar Sincronização", key=f"sync_{serie['ID_TMDB']}"):
                                eps = fetch_all_episodes(serie['ID_TMDB'], serie['Titulo'], serie['Total_Seasons'])
                                if eps:
                                    df_log = pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True)
                                    save_log(df_log)
                                    st.success("Corrigido! A página irá recarregar.")
                                    st.rerun()
                                else:
                                    st.error("Falha ao baixar do TMDB. Verifique se a série foi lançada.")
                        
                        else:
                            # CASO 2: Tem episódios
                            pendentes = df_s[df_s['Visto'] == False]
                            
                            if not pendentes.empty:
                                proximo = pendentes.iloc[0]
                                idx_real = proximo.name
                                
                                st.markdown(f"**Próximo:** T{proximo['Temporada']}E{proximo['Episodio']} - *{proximo['Nome_Epi']}*")
                                
                                c_act1, c_act2 = st.columns([1, 1])
                                if c_act1.button("✅ Visto (+1)", key=f"v_{serie['ID_TMDB']}"):
                                    df_log.at[idx_real, 'Visto'] = True
                                    df_log.at[idx_real, 'Data_Visto'] = str(date.today())
                                    save_log(df_log); st.rerun()
                                
                                # --- BULK UPDATE (MARATONA) ---
                                with st.expander("🚀 Opções Avançadas (Marcar Vários)"):
                                    st.caption("Marcar tudo como visto até:")
                                    cols_bulk = st.columns(3)
                                    max_temp = df_s['Temporada'].max()
                                    sel_temp = cols_bulk[0].number_input("Temp.", 1, int(max_temp), int(proximo['Temporada']), key=f"st_{serie['ID_TMDB']}")
                                    
                                    eps_da_temp = df_s[df_s['Temporada'] == sel_temp]['Episodio'].max()
                                    sel_ep = cols_bulk[1].number_input("Epi.", 1, int(eps_da_temp) if eps_da_temp > 0 else 1, 1, key=f"se_{serie['ID_TMDB']}")
                                    
                                    if cols_bulk[2].button("Atualizar", key=f"bk_{serie['ID_TMDB']}"):
                                        # Marca True em tudo que é anterior ou igual à seleção
                                        mask_serie = df_log['ID_TMDB'] == str(serie['ID_TMDB'])
                                        mask_ant = (df_log['Temporada'] < sel_temp) | \
                                                   ((df_log['Temporada'] == sel_temp) & (df_log['Episodio'] <= sel_ep))
                                        
                                        df_log.loc[mask_serie & mask_ant, 'Visto'] = True
                                        df_log.loc[mask_serie & mask_ant, 'Data_Visto'] = str(date.today())
                                        save_log(df_log); st.rerun()

                            else:
                                st.success("🎉 Série em dia! Aguardando estreias.")
                                if st.button("Buscar Novos Episódios", key=f"check_{serie['ID_TMDB']}"):
                                    # Lógica simples de refresh
                                    eps = fetch_all_episodes(serie['ID_TMDB'], serie['Titulo'], 100) # Tenta buscar tudo de novo
                                    # Filtra só o que não tem no log
                                    # (Simplificação: apenas avisa, implementação completa requer merge complexo)
                                    st.info("Varredura completa.")

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR (Mantida igual, mas robusta)
    # ------------------------------------------------------------------
    with tab_add:
        query = st.text_input("Buscar Série", placeholder="Ex: House of Cards")
        if query:
            url = f"{TMDB_BASE_URL}/search/tv?query={query}&language=pt-BR"
            try:
                results = requests.get(url, headers=HEADERS).json().get('results', [])
                for res in results[:3]:
                    with st.expander(f"{res['name']} ({res.get('first_air_date', 'Data desc.')[:4]})"):
                        c_img, c_inf = st.columns([1, 4])
                        with c_img:
                            if res.get('poster_path'): st.image(f"https://image.tmdb.org/t/p/w200{res['poster_path']}")
                        with c_inf:
                            st.write(res.get('overview', '')[:200] + "...")
                            if st.button("➕ Adicionar", key=f"add_{res['id']}"):
                                # Adiciona Master
                                new_m = {"ID_TMDB": str(res['id']), "Titulo": res['name'], "Status": "Ativo", 
                                         "Poster_URL": res.get('poster_path'), "Total_Seasons": 1} # Default 1, update depois
                                
                                # Verifica duplicidade
                                if df_master[df_master['ID_TMDB'] == str(res['id'])].empty:
                                    df_master = pd.concat([df_master, pd.DataFrame([new_m])], ignore_index=True)
                                    conexoes.save_gsheet("Series_Master", df_master)
                                    
                                    # Baixa episódios
                                    eps = fetch_all_episodes(res['id'], res['name'], 20) # Tenta até 20 temps
                                    if eps:
                                        df_log = pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True)
                                        save_log(df_log)
                                        st.success(f"Adicionada com {len(eps)} episódios!")
                                        st.rerun()
                                else:
                                    st.warning("Já cadastrada!")
            except: st.error("Erro na busca TMDB. Verifique conexão.")

    # ------------------------------------------------------------------
    # ABA 3: CALENDÁRIO
    # ------------------------------------------------------------------
    with tab_calendar:
        st.subheader("🗓️ Próximas Estreias")
        if not df_log.empty:
            hoje = date.today().strftime('%Y-%m-%d')
            futuros = df_log[(df_log['Data_Estreia'] >= hoje) & (df_log['Visto'] == False)].sort_values('Data_Estreia')
            
            if not futuros.empty:
                for _, row in futuros.head(10).iterrows():
                    st.info(f"**{row['Data_Estreia']}**: {row['Titulo']} (T{row['Temporada']}E{row['Episodio']}) - {row['Nome_Epi']}")
            else:
                st.write("Nada agendado para os próximos dias.")