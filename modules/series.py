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

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎬 TV Time: Batch Mode")
    st.caption("Edite à vontade. A sincronização só ocorre quando você clicar em Salvar.")
    
    df_master, df_log = load_data()

    tab_track, tab_add, tab_cal = st.tabs(["📺 Gerenciar Séries", "🔍 Adicionar Nova", "🗓️ Calendário"])

    # ------------------------------------------------------------------
    # ABA 1: GERENCIADOR EM LOTE (BATCH EDITOR)
    # ------------------------------------------------------------------
    with tab_track:
        if df_master.empty:
            st.info("Nenhuma série ativa.")
        else:
            # 1. Selecionar Série (Para não carregar tudo de uma vez)
            ativas = df_master[df_master['Status'] == 'Ativo']
            opcoes_series = ativas['Titulo'].unique()
            serie_sel = st.selectbox("Selecione a Série para editar:", opcoes_series)
            
            if serie_sel:
                # Dados da Série Selecionada
                row_master = ativas[ativas['Titulo'] == serie_sel].iloc[0]
                
                # Filtra Log
                mask_serie = df_log['ID_TMDB'] == str(row_master['ID_TMDB'])
                df_s = df_log[mask_serie].sort_values(['Temporada', 'Episodio'])
                
                # 2. Selecionar Temporada (Crucial para performance visual)
                temps = sorted(df_s['Temporada'].unique())
                if not temps:
                    st.warning("Sem episódios baixados.")
                    if st.button("🔄 Baixar Episódios Agora"):
                        eps = fetch_all_episodes(row_master['ID_TMDB'], row_master['Titulo'], row_master['Total_Seasons'])
                        if eps:
                            df_log = pd.concat([df_log, pd.DataFrame(eps)], ignore_index=True)
                            save_log(df_log)
                            st.rerun()
                else:
                    # Tabs por Temporada ou Selectbox (Selectbox é mais limpo se tiver muitas)
                    t_select = st.selectbox(f"Temporada de {serie_sel}", temps)
                    
                    # Filtra Temporada Específica
                    mask_view = (df_log['ID_TMDB'] == str(row_master['ID_TMDB'])) & (df_log['Temporada'] == t_select)
                    df_view = df_log.loc[mask_view, ['Episodio', 'Nome_Epi', 'Data_Estreia', 'Visto', 'Nota']]
                    
                    # Layout do Editor
                    c1, c2 = st.columns([1, 4])
                    if row_master['Poster_URL']: c1.image(f"https://image.tmdb.org/t/p/w200{row_master['Poster_URL']}")
                    
                    with c2:
                        st.info("📝 Marque tudo o que assistiu abaixo. O Google Drive só será atualizado quando clicar no botão 'Salvar'.")
                        
                        # --- O GRANDE SEGREDO: DATA EDITOR ---
                        # O editor roda localmente na memória do navegador/servidor
                        edited_df = st.data_editor(
                            df_view,
                            column_config={
                                "Visto": st.column_config.CheckboxColumn("Visto", help="Check para marcar como assistido"),
                                "Nota": st.column_config.NumberColumn("Nota", min_value=0, max_value=5, step=1, format="%d ⭐"),
                                "Episodio": st.column_config.TextColumn("Ep."),
                                "Nome_Epi": st.column_config.TextColumn("Título", disabled=True),
                                "Data_Estreia": st.column_config.TextColumn("Estreia", disabled=True),
                            },
                            hide_index=True,
                            use_container_width=True,
                            height=400, # Barra de rolagem se for muito grande
                            key=f"editor_{row_master['ID_TMDB']}_{t_select}"
                        )
                        
                        # --- BOTÃO DE AÇÃO (GATILHO ÚNICO) ---
                        col_save, col_info = st.columns([1, 2])
                        
                        # Detecta mudanças para avisar o usuário (opcional, mas legal)
                        changes_made = not edited_df.equals(df_view)
                        
                        if changes_made:
                            col_info.warning("⚠️ Você tem alterações não salvas!")
                        
                        if col_save.button("💾 SALVAR ALTERAÇÕES NA NUVEM", type="primary"):
                            # Aqui acontece a mágica:
                            # 1. Pegamos os índices originais
                            indices_alterados = edited_df.index
                            
                            # 2. Atualizamos o DF principal (df_log) com os dados editados
                            df_log.loc[indices_alterados, ['Visto', 'Nota']] = edited_df[['Visto', 'Nota']]
                            
                            # 3. Atualizamos Data_Visto automaticamente para quem virou TRUE agora
                            # (Lógica: Se Visto=True e Data_Visto está vazia, põe hoje)
                            mask_new_seen = (df_log['Visto'] == True) & (df_log['Data_Visto'] == "")
                            df_log.loc[mask_new_seen, 'Data_Visto'] = str(date.today())
                            
                            # 4. SÓ AGORA chamamos a API do Google (1 request apenas)
                            save_log(df_log)
                            
                            st.success("Sincronizado com sucesso!")
                            st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR (Mesma lógica robusta)
    # ------------------------------------------------------------------
    with tab_add:
        q = st.text_input("Buscar Série", placeholder="Stranger Things")
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

    # ------------------------------------------------------------------
    # ABA 3: CALENDÁRIO
    # ------------------------------------------------------------------
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