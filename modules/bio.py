import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta
import os
import math
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols = [
        "Data", "Peso_kg", "Altura_m", "Idade", "Gordura_Perc", 
        "Pescoco_cm", "Cintura_cm", "Biceps_cm", "Peito_cm", "Coxa_cm",
        "Sono_hrs", "Humor_0_10", "Treino_Tipo", "Obs",
        "Agua_L", "Calorias_Ingeridas", "Objetivo_Tipo"
    ]
    
    df = conexoes.load_gsheet("Bio", cols)
    
    # --- SANEAMENTO DE DADOS (Cast de Tipos para o Motor Científico) ---
    if not df.empty:
        # Colunas que precisam ser float/int para cálculos
        cols_float = ["Peso_kg", "Altura_m", "Gordura_Perc", "Pescoco_cm", "Cintura_cm", 
                      "Biceps_cm", "Peito_cm", "Coxa_cm", "Sono_hrs", "Agua_L"]
        for col in cols_float:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        df["Idade"] = pd.to_numeric(df["Idade"], errors='coerce').fillna(26).astype(int)
        df["Calorias_Ingeridas"] = pd.to_numeric(df["Calorias_Ingeridas"], errors='coerce').fillna(0).astype(int)
        
    return df

def save_data(df):
    conexoes.save_gsheet("Bio", df)

# --- MOTORES CIENTÍFICOS (Mantidos conforme original) ---
def calcular_bf_marinha(altura_m, cintura_cm, pescoco_cm):
    if cintura_cm == 0 or pescoco_cm == 0 or altura_m == 0: return 0.0
    try:
        log_cin_pes = math.log10(cintura_cm - pescoco_cm)
        log_alt = math.log10(altura_m * 100)
        bf = 495 / (1.0324 - 0.19077 * log_cin_pes + 0.15456 * log_alt) - 450
        return round(max(2.0, bf), 1)
    except: return 0.0

def calcular_gasto_calorico(peso, altura_m, idade, treino_tipo, objetivo):
    tmb = 88.36 + (13.4 * peso) + (4.8 * (altura_m * 100)) - (5.7 * idade)
    fator = 1.2 
    if treino_tipo in ["Musculação", "Cardio", "Esporte"]: fator = 1.55 
    gasto_total = tmb * fator
    meta_calorica = gasto_total
    if objetivo == "Emagrecer (Cut)": meta_calorica -= 500 
    elif objetivo == "Crescer (Bulk)": meta_calorica += 300 
    return int(tmb), int(gasto_total), int(meta_calorica)

def render_page():
    st.header("🧬 Bio-Data: O Laboratório")
    df = load_data()
    
    with st.sidebar:
        st.subheader("⚙️ Configuração Pessoal")
        last_global = df.sort_values("Data").iloc[-1] if not df.empty else None
        
        def get_global(col, default):
            if last_global is not None and col in last_global:
                val = last_global[col]
                return float(val) if val != "" else default
            return default
        
        idade = st.number_input("Idade", 18, 100, int(get_global("Idade", 26)))
        altura = st.number_input("Altura (m)", 1.00, 2.50, get_global("Altura_m", 1.72), 0.01)
        
        obj_options = ["Emagrecer (Cut)", "Manter", "Crescer (Bulk)"]
        obj_atual = str(last_global['Objetivo_Tipo']) if last_global is not None else "Manter"
        idx_obj = obj_options.index(obj_atual) if obj_atual in obj_options else 1
        objetivo = st.selectbox("Objetivo Atual", obj_options, index=idx_obj)

        st.divider()
        st.subheader("📝 Input Diário")
        dt_selecionada = st.date_input("Data de Registro", value=date.today())
        data_str = str(dt_selecionada)
        
        row_hoje = df[df['Data'] == data_str]
        existe_hoje = not row_hoje.empty
        
        def get_val(col, default, is_static=True):
            if existe_hoje: return row_hoje.iloc[0][col]
            elif is_static and last_global is not None: return last_global[col]
            else: return default

        with st.expander("🌅 Manhã (Jejum - Estático)", expanded=not existe_hoje):
            peso = st.number_input("Peso (kg)", 40.0, 150.0, float(get_val("Peso_kg", 80.0, True)), 0.1)
            pescoco = st.number_input("Pescoço (cm)", 20.0, 60.0, float(get_val("Pescoco_cm", 38.0, True)))
            cintura = st.number_input("Cintura (cm)", 50.0, 150.0, float(get_val("Cintura_cm", 90.0, True)))
            
            if st.checkbox("Editar Outras Medidas"):
                biceps = st.number_input("Bíceps", 0.0, 100.0, float(get_val("Biceps_cm", 0.0, True)))
                peito = st.number_input("Peito", 0.0, 200.0, float(get_val("Peito_cm", 0.0, True)))
                coxa = st.number_input("Coxa", 0.0, 100.0, float(get_val("Coxa_cm", 0.0, True)))
            else:
                biceps = float(get_val("Biceps_cm", 0.0, True))
                peito = float(get_val("Peito_cm", 0.0, True))
                coxa = float(get_val("Coxa_cm", 0.0, True))

            bf_auto = calcular_bf_marinha(altura, cintura, pescoco)
            st.caption(f"BF Estimado: **{bf_auto}%**")

        with st.expander("🌙 Dia/Noite (Acumulado)", expanded=True):
            agua_meta = peso * 0.035
            agua = st.number_input("Água (L)", 0.0, 10.0, float(get_val("Agua_L", 0.0, False)), 0.5)
            calorias = st.number_input("Calorias (kcal)", 0, 10000, int(get_val("Calorias_Ingeridas", 0, False)), step=50)
            
            treino_opts = ["Descanso", "Musculação", "Cardio", "Esporte"]
            t_atual = row_hoje.iloc[0]['Treino_Tipo'] if existe_hoje else "Descanso"
            treino = st.selectbox("Treino", treino_opts, index=treino_opts.index(t_atual) if t_atual in treino_opts else 0)
            
            sono = st.slider("Sono (h)", 0.0, 12.0, float(get_val("Sono_hrs", 7.0, True)), 0.5)
            humor = st.slider("Energia (1-10)", 1, 10, int(get_val("Humor_0_10", 7, True)))
            obs = st.text_input("Obs", get_val("Obs", "", False))

        if st.button("💾 Salvar Registro"):
            novo_registro = {
                "Data": data_str, "Idade": idade, "Altura_m": altura, "Objetivo_Tipo": objetivo,
                "Peso_kg": peso, "Gordura_Perc": bf_auto,
                "Pescoco_cm": pescoco, "Cintura_cm": cintura, "Biceps_cm": biceps, "Peito_cm": peito, "Coxa_cm": coxa,
                "Agua_L": agua, "Calorias_Ingeridas": calorias, "Treino_Tipo": treino,
                "Sono_hrs": sono, "Humor_0_10": humor, "Obs": obs
            }
            df = df[df['Data'] != data_str]
            df = pd.concat([df, pd.DataFrame([novo_registro])], ignore_index=True)
            save_data(df)
            st.success("Dados Atualizados!")
            st.rerun()

    # --- DASHBOARD (Lógica de exibição mantida) ---
    if df.empty:
        st.info("Preencha seus dados na barra lateral.")
        return

    df['Data_dt'] = pd.to_datetime(df['Data'])
    df = df.sort_values("Data_dt")
    current = df.iloc[-1]
    
    tmb, gasto_total, meta_calorica = calcular_gasto_calorico(
        current['Peso_kg'], current['Altura_m'], current['Idade'], current['Treino_Tipo'], current['Objetivo_Tipo']
    )
    
    st.subheader(f"🍽️ Nutrição & Metas ({current['Objetivo_Tipo']})")
    c1, c2, c3, c4, c5 = st.columns(5)
    
    saldo = current['Calorias_Ingeridas'] - gasto_total
    c1.metric("Ingerido/Gasto", f"{int(current['Calorias_Ingeridas'])} / {gasto_total}", f"{int(saldo)} kcal")
    c2.metric("BF Marinha", f"{current['Gordura_Perc']}%")
    
    massa_magra = current['Peso_kg'] * (1 - (current['Gordura_Perc']/100))
    c3.metric("Hidratação", f"{current['Agua_L']}L", f"Meta: {current['Peso_kg']*0.035:.1f}L")
    c4.metric("Peso", f"{current['Peso_kg']} kg", f"{massa_magra:.1f}kg Magra")
    c5.metric("Basal (TMB)", f"{tmb} kcal")

    st.divider()
    t1, t2, t3 = st.tabs(["📊 Calorias", "📉 Composição", "📝 Histórico"])
    
    with t1:
        df_chart = df.copy()
        df_chart['Gasto_Calc'] = df_chart.apply(lambda x: calcular_gasto_calorico(x['Peso_kg'], x['Altura_m'], x['Idade'], x['Treino_Tipo'], x['Objetivo_Tipo'])[1], axis=1)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_chart['Data_dt'], y=df_chart['Calorias_Ingeridas'], name='Ingerido', marker_color='#3498db'))
        fig.add_trace(go.Scatter(x=df_chart['Data_dt'], y=df_chart['Gasto_Calc'], name='Gasto Total', line=dict(color='red', width=3, dash='dot')))
        st.plotly_chart(fig, width=True)

    with t2:
        df_chart['Kg_Gordura'] = df_chart['Peso_kg'] * (df_chart['Gordura_Perc']/100)
        df_chart['Kg_Magra'] = df_chart['Peso_kg'] - df_chart['Kg_Gordura']
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(x=df_chart['Data_dt'], y=df_chart['Kg_Magra'], stackgroup='one', name='Massa Magra', marker_color='#2ecc71'))
        fig2.add_trace(go.Scatter(x=df_chart['Data_dt'], y=df_chart['Kg_Gordura'], stackgroup='one', name='Gordura', marker_color='#e74c3c'))
        st.plotly_chart(fig2, width=True)

    with t3:
        st.dataframe(df.sort_values("Data_dt", ascending=False), width=True)