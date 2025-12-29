import streamlit as st
import pandas as pd
from datetime import date
from modules import conexoes # Garanta que o nome seja conexoes.py conforme seu projeto

def load_data():
    """Carrega os dados das séries da aba 'Series' do Google Sheets"""
    cols = ["ID", "Titulo", "Temporada", "Total_Episodios", "Eps_Assistidos", "Status", "Onde_Assistir"]
    df = conexoes.load_gsheet("Series", cols)
    
    if not df.empty:
        # Saneamento de tipos para garantir cálculos de progresso
        df["Temporada"] = pd.to_numeric(df["Temporada"], errors='coerce').fillna(1).astype(int)
        df["Total_Episodios"] = pd.to_numeric(df["Total_Episodios"], errors='coerce').fillna(1).astype(int)
        df["Eps_Assistidos"] = pd.to_numeric(df["Eps_Assistidos"], errors='coerce').fillna(0).astype(int)
    return df

def save_data(df):
    """Sincroniza o DataFrame de séries com o Google Sheets"""
    # Converte tipos numéricos para string para evitar erros de serialização no GSheets
    df_save = df.copy()
    conexoes.save_gsheet("Series", df_save)

def render_page():
    st.header("📺 TV Time: Séries & Progresso")
    st.caption("Acompanhe suas maratonas e organize o que falta ver.")
    
    df = load_data()
    
    # --- SIDEBAR: ADICIONAR / ATUALIZAR ---
    with st.sidebar:
        st.subheader("➕ Nova Série/Temporada")
        with st.form("form_series"):
            f_titulo = st.text_input("Título da Série")
            f_streaming = st.selectbox("Onde Assistir?", ["Netflix", "Prime Video", "HBO Max", "Disney+", "Apple TV", "Crunchyroll", "Torresmo", "Outros"])
            f_temp = st.number_input("Temporada n°", 1, 50, 1)
            f_total_eps = st.number_input("Total de Episódios", 1, 100, 10)
            f_vistos = st.number_input("Já Assistidos", 0, 100, 0)
            f_status = st.selectbox("Status", ["Assistindo", "Na Fila", "Pausado", "Concluído"])
            
            if st.form_submit_button("Salvar na Nuvem"):
                if f_titulo:
                    # Gera um ID simples combinando Título e Temporada
                    new_id = f"{f_titulo.replace(' ', '')}_T{f_temp}"
                    
                    novo_registro = {
                        "ID": new_id,
                        "Titulo": f_titulo,
                        "Temporada": f_temp,
                        "Total_Episodios": f_total_eps,
                        "Eps_Assistidos": f_vistos,
                        "Status": f_status,
                        "Onde_Assistir": f_streaming
                    }
                    
                    # Se o ID já existe (Update), remove o antigo antes de adicionar o novo
                    if not df.empty and new_id in df['ID'].values:
                        df = df[df['ID'] != new_id]
                        
                    df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
                    save_data(df)
                    st.success(f"{f_titulo} sincronizada!")
                    st.rerun()

    # --- DASHBOARD DE PROGRESSO ---
    if not df.empty:
        # Ordenar por Status (Assistindo primeiro)
        df = df.sort_values(by=["Status", "Titulo"], ascending=[True, True])
        
        for idx, row in df.iterrows():
            # Lógica de Progresso Matemático
            total = int(row['Total_Episodios'])
            vistos = int(row['Eps_Assistidos'])
            progresso = vistos / total if total > 0 else 0
            restam = total - vistos
            
            with st.container(border=True):
                col_info, col_metrics, col_actions = st.columns([3, 2, 1])
                
                with col_info:
                    st.markdown(f"### {row['Titulo']} (T{row['Temporada']})")
                    st.caption(f"📍 {row['Onde_Assistir']} | Status: **{row['Status']}**")
                    st.progress(min(progresso, 1.0))
                
                with col_metrics:
                    st.metric("Vistos", f"{vistos}/{total}", f"{restam} p/ fim" if restam > 0 else "Finalizado")
                
                with col_actions:
                    # Botão rápido para adicionar +1 episódio assistido
                    if vistos < total:
                        if st.button("➕1", key=f"add_{row['ID']}"):
                            df.at[idx, 'Eps_Assistidos'] = vistos + 1
                            if (vistos + 1) == total:
                                df.at[idx, 'Status'] = "Concluído"
                            save_data(df)
                            st.rerun()
                    
                    if st.button("🗑️", key=f"del_{row['ID']}"):
                        df = df.drop(idx)
                        save_data(df)
                        st.rerun()
    else:
        st.info("Sua lista de séries está vazia. Adicione a primeira na barra lateral.")