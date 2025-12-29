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
        # Garante booleano para os checkboxes funcionarem
        df_log["Visto"] = df_log["Visto"].astype(str).str.upper() == "TRUE"
        
    return df_master, df_log

def save_log(df):
    df_save = df.copy()
    # Converte booleano para string "TRUE"/"FALSE" pro GSheets
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

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎬 TV Time: Antologia & Tracker")
    df_master, df_log = load_data()

    tab_track, tab_add, tab_cal = st.tabs(["📺 Minhas Séries", "🔍 Adicionar", "🗓️ Calendário"])

    # ------------------------------------------------------------------
    # ABA 1: TRACKER COM CHECKLIST (ANTOLOGIA)
    # ------------------------------------------------------------------
    with tab_track:
        if df_master.empty:
            st.info("Nenhuma série ativa.")
        else:
            ativas = df_master[df_master['Status'] == 'Ativo']
            
            for _, serie in ativas.iterrows():
                # Filtra apenas episódios desta série
                # Mantém o índice original para poder salvar depois!
                mask_serie = df_log['ID_TMDB'] == str(serie['ID_TMDB'])
                df_s = df_log[mask_serie].sort_values(['Temporada', 'Episodio'])
                
                # Métricas Gerais
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
                        st.progress(progresso)
                        st.caption(f"Progresso: {vistos}/{total_eps} episódios ({int(progresso*100)}%)")
                        
                        # --- MODO ANTOLOGIA / LISTA DE EPISÓDIOS ---
                        with st.expander("📂 Abrir Lista de Episódios (Checklist)", expanded=False):
                            # Seletor de Temporada para não poluir a tela
                            temps = sorted(df_s['Temporada'].unique())
                            if not temps:
                                st.warning("Sem episódios. Tente 'Forçar Sincronização'.")
                            else:
                                t_select = st.selectbox(f"Selecionar Temporada ({serie['Titulo']})", temps)
                                
                                # Filtra para edição visual, mas guardamos o Index para salvar
                                df_view = df_s[df_s['Temporada'] == t_select][['Episodio', 'Nome_Epi', 'Visto', 'Nota', 'Data_Estreia']]
                                
                                # TABELA EDITÁVEL
                                edited_df = st.data_editor(
                                    df_view,
                                    column_config={
                                        "Visto": st.column_config.CheckboxColumn("Visto?", help="Marque para concluir"),
                                        "Nota": st.column_config.NumberColumn("Nota (0-5)", min_value=0, max_value=5, step=1),
                                        "Episodio": st.column_config.TextColumn("Ep."),
                                        "Nome_Epi": st.column_config.TextColumn("Título", width="medium"),
                                        "Data_Estreia": st.column_config.TextColumn("Data", disabled=True),
                                    },
                                    disabled=["Episodio", "Nome_Epi", "Data_Estreia"],
                                    hide_index=True,
                                    key=f"edit_{serie['ID_TMDB']}_{t_select}"
                                )
                                
                                # BOTÃO DE SALVAR
                                if st.button("💾 Salvar Progresso", key=f"save_{serie['ID_TMDB']}_{t_select}"):
                                    # Atualiza o DataFrame Principal (df_log) usando os índices do editado
                                    # O Streamlit retorna o dataframe editado mantendo os índices originais do pandas
                                    df_log.loc[edited_df.index, ['Visto', 'Nota']] = edited_df[['Visto', 'Nota']]
                                    
                                    # Atualiza data de visto para hoje onde foi marcado como Visto recentemente
                                    # (Lógica simplificada: se tá Visto e sem data, põe hoje)
                                    mask_new_seen = (df_log['Visto'] == True) & (df_log['Data_Visto'] == "")
                                    df_log.loc[mask_new_seen, 'Data_Visto'] = str(date.today())
                                    
                                    save_log(df_log)
                                    st.success("Checklist atualizado!")
                                    st.rerun()

                        # Botão de Emergência (Sync)
                        if total_eps == 0:
                            if st.button("🔄 Baixar Episódios", key=f"sync_{serie['ID_TMDB']}"):
                                eps = fetch_all_episodes(serie['ID_TMDB'], serie['Titulo'], serie['Total_Seasons'])
                                if eps:
                                    df_log = pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True)
                                    save_log(df_log)
                                    st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR
    # ------------------------------------------------------------------
    with tab_add:
        q = st.text_input("Buscar Série", placeholder="Black Mirror")
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
                                # Pega seasons real
                                try:
                                    det = requests.get(f"{TMDB_BASE_URL}/tv/{r['id']}", headers=HEADERS).json()
                                    new_m['Total_Seasons'] = det.get('number_of_seasons', 1)
                                except: pass
                                
                                conexoes.save_gsheet("Series_Master", pd.concat([df_master, pd.DataFrame([new_m])], ignore_index=True))
                                eps = fetch_all_episodes(r['id'], r['name'], new_m['Total_Seasons'])
                                if eps: save_log(pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True))
                                st.success("Série adicionada!"); st.rerun()
                            else: st.warning("Já existe.")
            except: pass

    # ------------------------------------------------------------------
    # ABA 3: CALENDÁRIO
    # ------------------------------------------------------------------
    with tab_cal:
        st.subheader("🗓️ Agenda de Lançamentos")
        if not df_log.empty:
            hj = date.today().strftime('%Y-%m-%d')
            # Filtra episódios futuros de séries ativas
            mask_fut = (df_log['Data_Estreia'] >= hj) & (df_log['Visto'] == False)
            df_fut = df_log[mask_fut].sort_values('Data_Estreia').head(15)
            
            if not df_fut.empty:
                for _, row in df_fut.iterrows():
                    st.info(f"**{row['Data_Estreia']}**: {row['Titulo']} - T{row['Temporada']}E{row['Episodio']} ({row['Nome_Epi']})")
            else:
                st.write("Sem estreias previstas.")