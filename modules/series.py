import streamlit as st
import pandas as pd
from datetime import date
from modules import conexoes

def load_data():
    """Carrega dados com proteção contra KeyError"""
    # Definição exata das colunas que o código espera
    cols_esperadas = ["ID_Serie", "Titulo", "Temporada", "Qtd_Episodios", "Vistos_Nesta_Temp", "Onde_Assistir"]
    
    df = conexoes.load_gsheet("Series", cols_esperadas)
    
    if df.empty:
        return pd.DataFrame(columns=cols_esperadas)
    
    # --- SCHEMA SHIELD: Garante que as colunas existam antes de converter tipo ---
    for col in cols_esperadas:
        if col not in df.columns:
            df[col] = 0 if "Qtd" in col or "Vistos" in col or "Temporada" in col else ""

    # Converte tipos para operações matemáticas
    df["Temporada"] = pd.to_numeric(df["Temporada"], errors='coerce').fillna(1).astype(int)
    df["Qtd_Episodios"] = pd.to_numeric(df["Qtd_Episodios"], errors='coerce').fillna(1).astype(int)
    df["Vistos_Nesta_Temp"] = pd.to_numeric(df["Vistos_Nesta_Temp"], errors='coerce').fillna(0).astype(int)
    
    return df

def save_data(df):
    """Salva no GSheets convertendo para string para evitar erros de API"""
    df_save = df.copy()
    conexoes.save_gsheet("Series", df_save)

def render_page():
    st.header("📺 TV Time: Tracker de Precisão")
    st.caption("Acompanhe o progresso exato de cada temporada.")
    
    df = load_data()

    # --- INPUT: CADASTRO DE NOVA TEMPORADA ---
    with st.expander("➕ Cadastrar Nova Temporada"):
        with st.form("add_temp"):
            c1, c2 = st.columns(2)
            f_nome = c1.text_input("Nome da Série")
            f_onde = c1.selectbox("Onde Assistir?", ["Netflix", "Disney+", "Prime Video", "HBO Max", "Apple TV", "Drive", "Torresmo"])
            f_temp = c2.number_input("Temporada Nº", min_value=1, step=1)
            f_eps = c2.number_input("Total de Episódios", min_value=1, step=1)
            
            if st.form_submit_button("Registrar Temporada"):
                if f_nome:
                    new_id = f"{f_nome.replace(' ', '')}_T{f_temp}"
                    novo = {
                        "ID_Serie": new_id, "Titulo": f_nome, "Temporada": f_temp, 
                        "Qtd_Episodios": f_eps, "Vistos_Nesta_Temp": 0, "Onde_Assistir": f_onde
                    }
                    # Upsert: se já existe a temporada, remove antes de adicionar a nova versão
                    if not df.empty:
                        df = df[df['ID_Serie'] != new_id]
                    
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df)
                    st.success("Temporada salva na nuvem!")
                    st.rerun()

    # --- VISUALIZAÇÃO: O QUE ASSISTIR AGORA? ---
    if not df.empty:
        series_unicas = df["Titulo"].unique()
        
        for serie in series_unicas:
            # Filtra e ordena temporadas da série específica
            df_s = df[df["Titulo"] == serie].sort_values("Temporada")
            
            # Localiza a primeira temporada que ainda tem episódios pendentes
            temp_atual_idx = df_s[df_s["Vistos_Nesta_Temp"] < df_s["Qtd_Episodios"]].first_valid_index()
            
            with st.container(border=True):
                if temp_atual_idx is not None:
                    row = df.loc[temp_atual_idx]
                    proximo_epi = int(row['Vistos_Nesta_Temp']) + 1
                    
                    # Cálculo de progresso total da série (soma de todas as temps cadastradas)
                    total_eps_serie = df_s["Qtd_Episodios"].sum()
                    total_vistos_serie = df_s["Vistos_Nesta_Temp"].sum()
                    progresso_global = total_vistos_serie / total_eps_serie if total_eps_serie > 0 else 0
                    
                    c1, c2, c3 = st.columns([3, 2, 1])
                    with c1:
                        st.subheader(serie)
                        st.markdown(f"🚀 **Próximo: T{row['Temporada']} - E{proximo_epi}**")
                        st.progress(min(progresso_global, 1.0))
                        st.caption(f"📍 {row['Onde_Assistir']}")
                    
                    with c2:
                        st.metric("Na Temporada", f"{row['Vistos_Nesta_Temp']}/{row['Qtd_Episodios']}")
                        st.caption(f"Total: {total_vistos_serie} assistidos")
                    
                    with c3:
                        if st.button("➕1", key=f"btn_{row['ID_Serie']}"):
                            df.at[temp_atual_idx, "Vistos_Nesta_Temp"] += 1
                            save_data(df)
                            st.rerun()
                else:
                    st.success(f"🎉 {serie}: Maratona Concluída!")
                    if st.button("Remover Série", key=f"del_{serie}"):
                        df = df[df["Titulo"] != serie]
                        save_data(df)
                        st.rerun()
    else:
        st.info("Nenhuma série cadastrada. Use a barra lateral ou o formulário acima.")