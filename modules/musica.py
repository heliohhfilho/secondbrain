import streamlit as st
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from datetime import date
from modules import conexoes

# --- CONFIGURAÇÃO API SPOTIFY ---
try:
    sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=st.secrets['SPOTIPY_CLIENT_ID'],
        client_secret=st.secrets['SPOTIPY_CLIENT_SECRET']
    ))
    API_AVAILABLE = True
except:
    API_AVAILABLE = False

# --- FUNÇÕES DE DADOS ---
def load_data():
    cols = ["ID", "Album", "Artista", "Ano", "Genero", "Capa_URL", "Nota", "Top_Tracks", "Skip_Tracks", "Review", "Data_Ouvido", "Tracklist_Raw"]
    df = conexoes.load_gsheet("Musica", cols)
    
    if not df.empty:
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Ano"] = pd.to_numeric(df["Ano"], errors='coerce').fillna(0).astype(int)
        df["Nota"] = pd.to_numeric(df["Nota"], errors='coerce').fillna(0.0)
    return df

def save_data(df):
    df_save = df.copy()
    # Garante string para evitar erro JSON
    if "Tracklist_Raw" in df_save.columns: df_save["Tracklist_Raw"] = df_save["Tracklist_Raw"].astype(str)
    conexoes.save_gsheet("Musica", df_save)

# --- INTEGRAÇÃO SPOTIFY ---
def search_album(query):
    if not API_AVAILABLE: return []
    try:
        results = sp.search(q=query, type='album', limit=5)
        return results['albums']['items']
    except: return []

def get_album_details(album_id):
    if not API_AVAILABLE: return None
    try:
        album = sp.album(album_id)
        # Busca Tracklist
        tracks = [t['name'] for t in album['tracks']['items']]
        tracklist_str = "\n".join(tracks)
        
        return {
            "Album": album['name'],
            "Artista": album['artists'][0]['name'],
            "Ano": int(album['release_date'][:4]) if album['release_date'] else 0,
            "Capa_URL": album['images'][0]['url'] if album['images'] else "",
            "Tracklist_Raw": tracklist_str
        }
    except: return None

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🎧 Sound Lab: Vinyl Collection")
    
    if not API_AVAILABLE:
        st.error("⚠️ Configure SPOTIPY_CLIENT_ID e SECRET no secrets.toml para usar a busca automática.")

    df = load_data()
    
    tab_gallery, tab_add, tab_stats = st.tabs(["💿 Minha Estante", "🔍 Adicionar Álbum", "📊 Stats"])

    # ------------------------------------------------------------------
    # ABA 1: GALERIA (ESTILO VINIL)
    # ------------------------------------------------------------------
    with tab_gallery:
        if df.empty:
            st.info("Nenhum álbum na coleção.")
        else:
            # Filtros
            filtro_gen = st.multiselect("Filtrar Gênero", df['Genero'].unique())
            df_view = df if not filtro_gen else df[df['Genero'].isin(filtro_gen)]
            
            # Grid de Capas
            cols = st.columns(4) # 4 Vinis por linha
            for idx, (i, row) in enumerate(df_view.iterrows()):
                with cols[idx % 4]:
                    with st.container(border=True):
                        # Capa do Álbum
                        if row['Capa_URL']:
                            st.image(row['Capa_URL'], use_column_width=True)
                        else:
                            st.image("https://via.placeholder.com/300?text=Vinyl", use_column_width=True)
                        
                        st.markdown(f"**{row['Album']}**")
                        st.caption(f"{row['Artista']} ({row['Ano']})")
                        
                        # Nota Colorida
                        color = "green" if row['Nota'] >= 9 else "orange" if row['Nota'] >= 7 else "red"
                        st.markdown(f"Nota: :{color}[**{row['Nota']}**]")
                        
                        # Popover com Detalhes (O Verso do Vinil)
                        with st.popover("🔎 Ver Encarte"):
                            st.markdown(f"### {row['Album']}")
                            st.write(f"**Review:** _{row['Review']}_")
                            
                            st.divider()
                            st.markdown("#### 🎼 Tracklist & Veredito")
                            
                            # Processamento visual da tracklist
                            tracks = str(row['Tracklist_Raw']).split('\n')
                            tops = [t.strip().lower() for t in str(row['Top_Tracks']).split(',')]
                            skips = [s.strip().lower() for s in str(row['Skip_Tracks']).split(',')]
                            
                            for t in tracks:
                                icon = "⚫"
                                style = "color: grey"
                                t_lower = t.lower()
                                
                                # Lógica de Destaque
                                is_top = any(fav in t_lower for fav in tops if fav)
                                is_skip = any(sk in t_lower for sk in skips if sk)
                                
                                if is_top:
                                    icon = "🔥"
                                    style = "color: #FFD700; font-weight: bold"
                                elif is_skip:
                                    icon = "⏭️"
                                    style = "color: #FF4B4B; text-decoration: line-through"
                                    
                                st.markdown(f"<span style='{style}'>{icon} {t}</span>", unsafe_allow_html=True)
                                
                            st.divider()
                            if st.button("🗑️ Remover da Estante", key=f"del_{row['ID']}"):
                                save_data(df.drop(i)); st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: ADICIONAR (BUSCA AUTOMÁTICA)
    # ------------------------------------------------------------------
    with tab_add:
        query = st.text_input("Buscar Álbum (Spotify)", placeholder="Ex: Dark Side of the Moon")
        
        if query and API_AVAILABLE:
            results = search_album(query)
            if results:
                for album in results:
                    with st.expander(f"{album['name']} - {album['artists'][0]['name']} ({album['release_date'][:4]})"):
                        c1, c2 = st.columns([1, 3])
                        if album['images']: c1.image(album['images'][0]['url'])
                        
                        with c2:
                            if st.button("💿 Selecionar este Álbum", key=f"sel_{album['id']}"):
                                # Pega detalhes completos (incluindo tracklist)
                                details = get_album_details(album['id'])
                                st.session_state['temp_album'] = details
                                st.rerun()
            else:
                st.warning("Nenhum álbum encontrado.")

        # Formulário de Avaliação (Abre se um álbum foi selecionado)
        if 'temp_album' in st.session_state:
            sel = st.session_state['temp_album']
            st.divider()
            st.subheader(f"Avaliar: {sel['Album']}")
            
            with st.form("save_album"):
                c_gen, c_nota = st.columns(2)
                genero = c_gen.selectbox("Gênero Principal", ["Rock", "Pop", "Jazz", "Hip-Hop", "Metal", "Indie", "Eletrônica", "R&B", "MPB", "Clássica"])
                nota = c_nota.slider("Nota (0-10)", 0.0, 10.0, 8.0, 0.1)
                
                review = st.text_area("Review Curta")
                
                st.markdown("---")
                st.caption("Copie nomes da Tracklist abaixo para os campos de Top/Skip")
                with st.expander("Ver Tracklist para Copiar"):
                    st.text(sel['Tracklist_Raw'])
                
                top = st.text_input("🔥 Top Tracks (separar por vírgula)")
                skip = st.text_input("⏭️ Skips (separar por vírgula)")
                
                if st.form_submit_button("💾 Salvar na Coleção"):
                    new_id = 1 if df.empty else df['ID'].max() + 1
                    novo_reg = {
                        "ID": new_id,
                        "Album": sel['Album'],
                        "Artista": sel['Artista'],
                        "Ano": sel['Ano'],
                        "Genero": genero,
                        "Capa_URL": sel['Capa_URL'],
                        "Nota": nota,
                        "Top_Tracks": top,
                        "Skip_Tracks": skip,
                        "Review": review,
                        "Data_Ouvido": str(date.today()),
                        "Tracklist_Raw": sel['Tracklist_Raw']
                    }
                    df = pd.concat([df, pd.DataFrame([novo_reg])], ignore_index=True)
                    save_data(df)
                    del st.session_state['temp_album'] # Limpa seleção
                    st.success("Vinil adicionado à estante!"); st.rerun()

    # ------------------------------------------------------------------
    # ABA 3: STATS
    # ------------------------------------------------------------------
    with tab_stats:
        if not df.empty:
            st.metric("Total de Discos", len(df))
            st.markdown("#### Gêneros Mais Ouvidos")
            st.bar_chart(df['Genero'].value_counts())
            
            # Melhores do Ano
            best = df[df['Nota'] >= 9.0]
            if not best.empty:
                st.markdown("#### 🏆 Hall da Fama (Nota 9+)")
                for _, row in best.iterrows():
                    st.write(f"• **{row['Album']}** - {row['Artista']}")