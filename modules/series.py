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
    st.header("📺 TV Time: Tracker de Precisão")
    
    # Carregamento com Cache para evitar Erro 429
    cols = ["ID_Serie", "Titulo", "Temporada", "Qtd_Episodios", "Vistos_Nesta_Temp", "Onde_Assistir"]
    df = conexoes.load_gsheet("Series", cols)

    if not df.empty:
        df["Temporada"] = df["Temporada"].astype(int)
        df["Qtd_Episodios"] = df["Qtd_Episodios"].astype(int)
        df["Vistos_Nesta_Temp"] = df["Vistos_Nesta_Temp"].astype(int)

    # --- INPUT: CADASTRO DE TEMPORADA ESPECÍFICA ---
    with st.expander("➕ Cadastrar Nova Temporada"):
        with st.form("add_temp"):
            col1, col2 = st.columns(2)
            nome = col1.text_input("Nome da Série (Ex: Grey's Anatomy)")
            onde = col1.selectbox("Onde?", ["Netflix", "Disney+", "Prime", "Drive"])
            temp_n = col2.number_input("Temporada Nº", min_value=1, step=1)
            eps_n = col2.number_input("Total de Episódios desta Temporada", min_value=1, step=1)
            
            if st.form_submit_button("Registrar Temporada"):
                # Lógica de append via conexoes.save_gsheet
                st.success("Temporada registrada!")

    # --- VISUALIZAÇÃO: O QUE ASSISTIR AGORA? ---
    if not df.empty:
        series_unicas = df["Titulo"].unique()
        
        for serie in series_unicas:
            df_s = df[df["Titulo"] == serie].sort_values("Temporada")
            
            # Localizar a temporada atual (a primeira não finalizada)
            temp_atual_row = df_s[df_s["Vistos_Nesta_Temp"] < df_s["Qtd_Episodios"]].first_valid_index()
            
            with st.container(border=True):
                if temp_atual_row is not None:
                    row = df.loc[temp_atual_row]
                    proximo_epi = row['Vistos_Nesta_Temp'] + 1
                    progresso_total = (df_s["Vistos_Nesta_Temp"].sum() / df_s["Qtd_Episodios"].sum())
                    
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.subheader(serie)
                        st.markdown(f"🚀 **Próximo: T{row['Temporada']} - E{proximo_epi}**")
                        st.caption(f"📍 {row['Onde_Assistir']}")
                        st.progress(progresso_total)
                    
                    with c2:
                        st.metric("Na Temporada", f"{row['Vistos_Nesta_Temp']}/{row['Qtd_Episodios']}")
                        st.caption(f"Total da Série: {df_s['Vistos_Nesta_Temp'].sum()} assistidos")
                    
                    with c3:
                        if st.button("✅ Vi este!", key=f"btn_{row['ID_Serie']}_{row['Temporada']}"):
                            # Incrementa e salva
                            df.at[temp_atual_row, "Vistos_Nesta_Temp"] += 1
                            conexoes.save_gsheet("Series", df)
                            st.rerun()
                else:
                    st.success(f"🎉 {serie}: Você assistiu tudo!")
                    if st.button("Excluir Série", key=f"del_{serie}"):
                        df = df[df["Titulo"] != serie]
                        conexoes.save_gsheet("Series", df)
                        st.rerun()
    else:
        st.info("Nenhuma série no radar.")