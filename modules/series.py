import streamlit as st
import pandas as pd
import requests
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

# --- FUNÇÕES DE DADOS ---
def load_data():
    df_master = conexoes.load_gsheet("Series_Master", ["ID_TMDB", "Titulo", "Status", "Poster_URL", "Total_Seasons"])
    df_log = conexoes.load_gsheet("Series_Log", ["ID_TMDB", "Titulo", "Temporada", "Episodio", "Nome_Epi", "Data_Estreia", "Visto", "Nota", "Data_Visto"])
    
    if not df_master.empty: df_master["ID_TMDB"] = df_master["ID_TMDB"].astype(str)
    if not df_log.empty:
        df_log["ID_TMDB"] = df_log["ID_TMDB"].astype(str)
        df_log["Temporada"] = pd.to_numeric(df_log["Temporada"], errors='coerce').fillna(0).astype(int)
        df_log["Episodio"] = pd.to_numeric(df_log["Episodio"], errors='coerce').fillna(0).astype(int)
        df_log["Nota"] = pd.to_numeric(df_log["Nota"], errors='coerce').fillna(0).astype(int)
        df_log["Visto"] = df_log["Visto"].astype(str).str.upper() == "TRUE"
        
    return df_master, df_log

def save_log(df):
    df_save = df.copy()
    df_save["Visto"] = df_save["Visto"].astype(str).str.upper()
    conexoes.save_gsheet("Series_Log", df_save)

def save_master(df):
    conexoes.save_gsheet("Series_Master", df)

def fetch_all_episodes(tmdb_id, titulo, total_seasons):
    novos = []
    total_seasons = max(1, int(total_seasons))
    placeholder = st.empty()
    bar = st.progress(0)
    for sn in range(1, total_seasons + 2):
        try:
            url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/season/{sn}?language=pt-BR"
            r = requests.get(url, headers=HEADERS)
            if r.status_code == 200:
                data = r.json()
                for ep in data.get('episodes', []):
                    if ep.get('air_date'):
                        novos.append({
                            "ID_TMDB": str(tmdb_id), "Titulo": titulo,
                            "Temporada": sn, "Episodio": ep['episode_number'],
                            "Nome_Epi": ep['name'], "Data_Estreia": ep['air_date'],
                            "Visto": False, "Nota": 0, "Data_Visto": ""
                        })
                placeholder.text(f"Baixando T{sn}...")
            else:
                if sn > 1: break 
        except: pass
        bar.progress(min(sn/(total_seasons+1), 1.0))
    placeholder.empty(); bar.empty()
    return novos

# --- COMPONENTE DE RENDERIZAÇÃO DE SÉRIE ---
def render_serie_card(serie, df_log, key_suffix, readonly=False):
    """Renderiza o card de uma série específica"""
    mask_serie = df_log['ID_TMDB'] == str(serie['ID_TMDB'])
    df_s = df_log[mask_serie].sort_values(['Temporada', 'Episodio'])
    
    total_eps = len(df_s)
    vistos = df_s['Visto'].sum()
    progresso = vistos / total_eps if total_eps > 0 else 0
    
    with st.container(border=True):
        c1, c2 = st.columns([1, 5])
        with c1:
            if serie['Poster_URL']: st.image(f"https://image.tmdb.org/t/p/w200{serie['Poster_URL']}")
            else: st.write("📺")
        
        with c2:
            st.subheader(f"{serie['Titulo']}")
            
            # --- FEATURE NOVA: PRÓXIMO EPISÓDIO ---
            # Filtra o que não foi visto e pega o primeiro (menor Temp e menor Ep)
            pendentes = df_s[df_s['Visto'] == False]
            
            if not pendentes.empty:
                prox = pendentes.iloc[0]
                # Mostra em destaque
                st.info(f"▶️ **Próximo:** T{prox['Temporada']}E{prox['Episodio']} - *{prox['Nome_Epi']}*")
            else:
                if total_eps > 0:
                    st.success("🎉 Série em dia! Aguardando novos episódios.")
                else:
                    st.warning("Sem episódios baixados.")

            # Barra de Progresso Geral
            st.progress(progresso)
            st.caption(f"Total Visto: {vistos}/{total_eps} ({int(progresso*100)}%)")
            
            if readonly:
                return

            # --- MODO CHECKLIST ---
            with st.expander("📂 Abrir Temporadas", expanded=False):
                temps = sorted(df_s['Temporada'].unique())
                if not temps:
                    st.warning("Sem episódios.")
                    if st.button("🔄 Baixar", key=f"sync_{serie['ID_TMDB']}_{key_suffix}"):
                        eps = fetch_all_episodes(serie['ID_TMDB'], serie['Titulo'], serie['Total_Seasons'])
                        if eps:
                            st.rerun() 
                else:
                    t_select = st.selectbox(f"Temp. ({serie['Titulo']})", temps, key=f"ts_{serie['ID_TMDB']}_{key_suffix}")
                    
                    mask_view = (df_log['ID_TMDB'] == str(serie['ID_TMDB'])) & (df_log['Temporada'] == t_select)
                    df_view = df_log.loc[mask_view, ['Episodio', 'Nome_Epi', 'Data_Estreia', 'Visto', 'Nota']]
                    
                    edited_df = st.data_editor(
                        df_view,
                        column_config={
                            "Visto": st.column_config.CheckboxColumn("Vi", width="small"),
                            "Nota": st.column_config.NumberColumn("⭐", min_value=0, max_value=5, width="small"),
                            "Episodio": st.column_config.NumberColumn("Ep.", format="%d", width="small"),
                            "Nome_Epi": st.column_config.TextColumn("Título", disabled=True),
                            "Data_Estreia": st.column_config.TextColumn("Data", disabled=True),
                        },
                        hide_index=True,
                        use_container_width=True,
                        key=f"ed_{serie['ID_TMDB']}_{t_select}_{key_suffix}"
                    )
                    
                    if st.button("💾 Salvar", key=f"sv_{serie['ID_TMDB']}_{t_select}_{key_suffix}"):
                        df_log.loc[edited_df.index, ['Visto', 'Nota']] = edited_df[['Visto', 'Nota']]
                        mask_new_seen = (df_log['Visto'] == True) & (df_log['Data_Visto'] == "")
                        df_log.loc[mask_new_seen, 'Data_Visto'] = str(date.today())
                        save_log(df_log)
                        st.success("Salvo!")
                        st.rerun()

# --- RENDERIZAÇÃO PRINCIPAL ---
def render_page():
    st.header("🎬 TV Time: Hub de Séries")
    df_master, df_log = load_data()

    tab_track, tab_add, tab_cal, tab_man = st.tabs(["📺 Minhas Séries", "🔍 Adicionar", "🗓️ Calendário", "⚙️ Gerenciar"])

    with tab_track:
        if df_master.empty:
            st.info("Nenhuma série.")
        else:
            s_ativas = df_master[df_master['Status'] == 'Ativo']
            s_pausadas = df_master[df_master['Status'] == 'Pausado']
            s_finalizadas = df_master[df_master['Status'] == 'Finalizado']
            
            ids_ativas = s_ativas['ID_TMDB'].unique()
            ids_em_dia = []
            ids_assistindo = []
            
            for sid in ids_ativas:
                log_serie = df_log[df_log['ID_TMDB'] == str(sid)]
                if log_serie.empty or not log_serie['Visto'].all():
                    ids_assistindo.append(sid)
                else:
                    ids_em_dia.append(sid)
            
            df_assistindo = s_ativas[s_ativas['ID_TMDB'].isin(ids_assistindo)]
            df_em_dia = s_ativas[s_ativas['ID_TMDB'].isin(ids_em_dia)]

            st_t1, st_t2, st_t3, st_t4 = st.tabs([
                f"▶️ Assistindo ({len(df_assistindo)})", 
                f"⏳ Em Dia ({len(df_em_dia)})", 
                f"⏸️ Pausadas ({len(s_pausadas)})", 
                f"✅ Finalizadas ({len(s_finalizadas)})"
            ])
            
            with st_t1:
                if df_assistindo.empty: st.info("Nada pendente!")
                for _, row in df_assistindo.iterrows():
                    render_serie_card(row, df_log, "watch")
            
            with st_t2:
                for _, row in df_em_dia.iterrows():
                    render_serie_card(row, df_log, "wait", readonly=False)
            
            with st_t3:
                for _, row in s_pausadas.iterrows():
                    st.warning(f"⏸️ **{row['Titulo']}**")
                    if st.button("▶️ Retomar", key=f"res_{row['ID_TMDB']}"):
                        df_master.loc[df_master['ID_TMDB'] == row['ID_TMDB'], 'Status'] = 'Ativo'
                        save_master(df_master); st.rerun()

            with st_t4:
                for _, row in s_finalizadas.iterrows():
                    st.markdown(f"✅ **{row['Titulo']}**")

    with tab_add:
        q = st.text_input("Buscar Série", placeholder="Succession")
        if q:
            url = f"{TMDB_BASE_URL}/search/tv?query={q}&language=pt-BR"
            try:
                res = requests.get(url, headers=HEADERS).json().get('results', [])
                for r in res[:3]:
                    with st.expander(f"{r['name']} ({r.get('first_air_date','')[:4]})"):
                        c_img, c_inf = st.columns([1,4])
                        if r.get('poster_path'): c_img.image(f"https://image.tmdb.org/t/p/w200{r['poster_path']}")
                        c_inf.write(r.get('overview',''))
                        if c_inf.button("➕ Adicionar", key=f"add_{r['id']}"):
                            if df_master[df_master['ID_TMDB']==str(r['id'])].empty:
                                new_m = {"ID_TMDB":str(r['id']), "Titulo":r['name'], "Status":"Ativo", 
                                         "Poster_URL":r.get('poster_path'), "Total_Seasons":1}
                                try:
                                    det = requests.get(f"{TMDB_BASE_URL}/tv/{r['id']}", headers=HEADERS).json()
                                    new_m['Total_Seasons'] = det.get('number_of_seasons', 1)
                                except: pass
                                conexoes.save_gsheet("Series_Master", pd.concat([df_master, pd.DataFrame([new_m])], ignore_index=True))
                                eps = fetch_all_episodes(r['id'], r['name'], new_m['Total_Seasons'])
                                if eps: save_log(pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True))
                                st.success("Adicionado!"); st.rerun()
                            else: st.warning("Já existe.")
            except: pass

    with tab_cal:
        st.subheader("🗓️ Próximas Estreias")
        if not df_log.empty:
            hj = date.today().strftime('%Y-%m-%d')
            mask_fut = (df_log['Data_Estreia'] >= hj) & (df_log['Visto'] == False)
            df_fut = df_log[mask_fut].sort_values('Data_Estreia').head(15)
            if not df_fut.empty:
                for _, row in df_fut.iterrows():
                    st.info(f"**{row['Data_Estreia']}**: {row['Titulo']} - T{row['Temporada']}E{row['Episodio']}")
            else: st.write("Sem estreias.")

    with tab_man:
        if not df_master.empty:
            st.subheader("⚙️ Gerenciar Status")
            edited_master = st.data_editor(
                df_master[['ID_TMDB', 'Titulo', 'Status']],
                column_config={
                    "ID_TMDB": st.column_config.TextColumn("ID", disabled=True),
                    "Titulo": st.column_config.TextColumn("Título", disabled=True),
                    "Status": st.column_config.SelectboxColumn("Status", options=["Ativo", "Pausado", "Finalizado"])
                },
                hide_index=True,
                key="editor_status_master"
            )
            if st.button("💾 Salvar Status"):
                for i, row in edited_master.iterrows():
                    id_row = row['ID_TMDB']
                    df_master.loc[df_master['ID_TMDB'] == id_row, 'Status'] = row['Status']
                save_master(df_master); st.success("Atualizado!"); st.rerun()
            
            st.divider()
            del_serie = st.selectbox("Excluir Série", df_master['Titulo'].unique())
            if st.button("DELETAR SÉRIE"):
                id_del = df_master[df_master['Titulo'] == del_serie].iloc[0]['ID_TMDB']
                save_master(df_master[df_master['ID_TMDB'] != id_del])
                save_log(df_log[df_log['ID_TMDB'] != id_del])
                st.success("Deletada."); st.rerun()