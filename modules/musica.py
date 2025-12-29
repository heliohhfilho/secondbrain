import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import os

from modules import conexoes

PATH_MUSICA = os.path.join('data', 'musica_log.csv')

def load_data():
    cols = [
        "ID", "Album", "Artista", "Genero", "Ano_Lancamento",
        "Nota_0_10", "Top_Tracks", "Skip_Tracks", "Review_Curta", 
        "Data_Ouvido", "Tracklist_Raw"
    ]
    df = conexoes.load_gsheet("Musica", cols)
    
    if not df.empty:
        # Saneamento de tipos para métricas e sliders
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Nota_0_10"] = pd.to_numeric(df["Nota_0_10"], errors='coerce').fillna(0.0)
        df["Ano_Lancamento"] = pd.to_numeric(df["Ano_Lancamento"], errors='coerce').fillna(2025).astype(int)
    return df

def save_data(df):
    # Converte tipos para GSheets (Datas e Texto Longo)
    df_save = df.copy()
    if "Data_Ouvido" in df_save.columns:
        df_save["Data_Ouvido"] = df_save["Data_Ouvido"].astype(str)
    # Garante que a tracklist seja salva como string pura
    if "Tracklist_Raw" in df_save.columns:
        df_save["Tracklist_Raw"] = df_save["Tracklist_Raw"].astype(str)
        
    conexoes.save_gsheet("Musica", df_save)

def render_page():
    st.header("🎧 Sound Lab: Music Tracker")
    df = load_data()
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.subheader("➕ Registrar Audição")
        with st.form("form_music"):
            m_album = st.text_input("Nome do Álbum")
            m_artista = st.text_input("Artista")
            m_genero = st.selectbox("Gênero", ["Rock", "Pop", "Hip-Hop", "Eletrônica", "Jazz", "MPB", "Metal", "Indie", "Outro"])
            m_ano = st.number_input("Ano", 1950, 2026, 2025)
            m_nota = st.slider("Nota", 0.0, 10.0, 8.0)
            
            st.markdown("---")
            st.caption("Detalhes das Faixas")
            # Novo campo para colar a tracklist inteira
            m_tracklist = st.text_area("Tracklist Completa (Uma música por linha)", height=150, placeholder="Música 1\nMúsica 2\nMúsica 3...")
            
            m_top = st.text_input("🔥 Favoritas (Digite parte do nome, separado por vírgula)")
            m_skip = st.text_input("⏭️ Skips (Digite parte do nome, separado por vírgula)")
            m_review = st.text_area("Mini Review")
            
            if st.form_submit_button("Salvar"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, "Album": m_album, "Artista": m_artista,
                    "Genero": m_genero, "Ano_Lancamento": m_ano,
                    "Nota_0_10": m_nota, 
                    "Top_Tracks": m_top, "Skip_Tracks": m_skip, 
                    "Review_Curta": m_review, "Data_Ouvido": date.today(),
                    "Tracklist_Raw": m_tracklist
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Salvo!")
                st.rerun()

    # --- VISUALIZAÇÃO ---
    if not df.empty:
        # KPIS
        col_kpi = st.columns(4)
        col_kpi[0].metric("Álbuns", len(df))
        col_kpi[1].metric("Nota Média", f"{df['Nota_0_10'].mean():.1f}")
        col_kpi[2].metric("Gênero Top", df['Genero'].mode()[0])
        col_kpi[3].metric("Artista Top", df['Artista'].mode()[0])
        
        st.divider()
        
        # LISTA DE ÁLBUNS
        for idx, row in df.sort_values("Data_Ouvido", ascending=False).iterrows():
            with st.container(border=True):
                # Header do Card
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"### 💿 {row['Album']}")
                c1.caption(f"{row['Artista']} | {row['Genero']} | {row['Ano_Lancamento']}")
                
                cor = "green" if row['Nota_0_10'] >= 8 else "orange" if row['Nota_0_10'] >= 5 else "red"
                c2.markdown(f"<h2 style='color:{cor}; text-align:right'>{row['Nota_0_10']}</h2>", unsafe_allow_html=True)
                
                st.markdown(f"> *{row['Review_Curta']}*")
                
                # TRACKLIST VISUALIZER
                if pd.notna(row.get('Tracklist_Raw')) and row['Tracklist_Raw']:
                    with st.expander("🎼 Ver Tracklist & Veredito"):
                        # Processa as listas
                        raw_tracks = str(row['Tracklist_Raw']).split('\n')
                        tops = [x.strip().lower() for x in str(row['Top_Tracks']).split(',')] if pd.notna(row['Top_Tracks']) else []
                        skips = [x.strip().lower() for x in str(row['Skip_Tracks']).split(',')] if pd.notna(row['Skip_Tracks']) else []
                        
                        for track in raw_tracks:
                            track_clean = track.strip()
                            if not track_clean: continue
                            
                            # Lógica de Ícone (Busca substring)
                            icon = "🎵" # Neutro
                            style = "color: #b0b0b0;" # Cinza
                            
                            # Verifica se é Top
                            for t in tops:
                                if t and t in track_clean.lower():
                                    icon = "🔥" # Ou ⭐
                                    style = "color: #FFD700; font-weight: bold;" # Dourado
                                    break
                            
                            # Verifica se é Skip
                            for s in skips:
                                if s and s in track_clean.lower():
                                    icon = "⏭️" # Ou ❌
                                    style = "color: #FF4B4B; text-decoration: line-through;" # Vermelho riscado
                                    break
                            
                            st.markdown(f"<span style='{style}'>{icon} {track_clean}</span>", unsafe_allow_html=True)
                
                # Footer do Card
                st.caption(f"Ouvido em: {row['Data_Ouvido']}")
                if st.button("Remover", key=f"del_{row['ID']}"):
                    df = df[df['ID'] != row['ID']]
                    save_data(df)
                    st.rerun()