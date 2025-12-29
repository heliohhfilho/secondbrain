import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut

# --- ARQUIVOS ---
FILE_PATH = os.path.join('data', 'viagens.csv')
LOGISTICS_PATH = os.path.join('data', 'viagens_logistica.csv')
HOTELS_PATH = os.path.join('data', 'viagens_hoteis.csv')

# --- FUNÇÕES ---
def load_data(path, columns):
    if not os.path.exists(path):
        return pd.DataFrame(columns=columns)
    
    df = pd.read_csv(path)
    
    # --- AUTO-CORREÇÃO DE SCHEMA (FIX PARA KEYERROR) ---
    for col in columns:
        if col not in df.columns:
            # Se a coluna nova não existe, cria ela com valor padrão
            if "Valor" in col or "Cotacao" in col or "lat" in col or "lon" in col:
                df[col] = 0.0
            elif col == "Moeda":
                df[col] = "BRL"
            elif col == "Pago":
                df[col] = False
            else:
                df[col] = "" # Texto vazio para colunas de texto
                
    # Garante tipagem correta para evitar NAN visual
    if "Valor_Final_BRL" in df.columns:
        df["Valor_Final_BRL"] = df["Valor_Final_BRL"].fillna(0.0)
    
    return df

def save_data(df, path):
    df.to_csv(path, index=False)

def get_lat_lon(endereco):
    geolocator = Nominatim(user_agent="second_brain_app_fix")
    try:
        location = geolocator.geocode(endereco, timeout=10)
        if location: return location.latitude, location.longitude
    except: pass
    return None, None

def render_page():
    st.header("🌍 Travel CRM & Intelligence")
    
    # Carrega com Schema Blindado
    df_fin = load_data(FILE_PATH, ["Viagem", "Categoria", "Item", "Valor_Moeda_Original", "Moeda", "Cotacao", "Valor_Final_BRL", "Pago", "Data_Ida", "Data_Volta"])
    df_log = load_data(LOGISTICS_PATH, ["Viagem", "Tipo", "Origem", "Destino", "Data_Hora_Ida", "Data_Hora_Volta", "Detalhes"])
    df_hotels = load_data(HOTELS_PATH, ["Viagem", "Nome", "Endereco", "Checkin", "Checkout", "lat", "lon"])

    with st.sidebar:
        st.subheader("✈️ Seleção")
        viagens = list(set(df_fin['Viagem'].unique().tolist()))
        mode = st.radio("Modo", ["Existente", "Nova"])
        
        selected_trip = None
        dates = (date.today(), date.today())
        
        if mode == "Nova":
            nome = st.text_input("Destino")
            d1, d2 = st.columns(2)
            ida = d1.date_input("Ida")
            volta = d2.date_input("Volta")
            if st.button("Criar"):
                # Cria linha dummy para inicializar
                row = {"Viagem": nome, "Categoria": "Setup", "Item": "Setup", "Valor_Final_BRL": 0.0, "Data_Ida": ida, "Data_Volta": volta, "Pago": True}
                df_fin = pd.concat([df_fin, pd.DataFrame([row])], ignore_index=True)
                save_data(df_fin, FILE_PATH)
                st.rerun()
        else:
            if viagens:
                selected_trip = st.selectbox("Viagem", viagens)
                if not df_fin[df_fin['Viagem'] == selected_trip].empty:
                    r = df_fin[df_fin['Viagem'] == selected_trip].iloc[0]
                    dates = (pd.to_datetime(r['Data_Ida']).date(), pd.to_datetime(r['Data_Volta']).date())

    if not selected_trip: return

    st.markdown(f"## 📍 {selected_trip}")
    t1, t2, t3, t4 = st.tabs(["💰 Financeiro", "🛫 Logística", "🏨 Hotéis", "📊 BI"])

    # ABA 1: FINANCEIRO
    with t1:
        df_trip = df_fin[df_fin['Viagem'] == selected_trip]
        total = df_trip['Valor_Final_BRL'].sum()
        pago = df_trip[df_trip['Pago'] == True]['Valor_Final_BRL'].sum()
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Custo Total", f"R$ {total:,.2f}")
        c2.metric("Pago", f"R$ {pago:,.2f}")
        c3.metric("Falta", f"R$ {total - pago:,.2f}")
        
        st.divider()
        with st.expander("Novo Custo"):
            desc = st.text_input("Descrição")
            val = st.number_input("Valor (BRL)", min_value=0.0)
            if st.button("Adicionar"):
                n = {
                    "Viagem": selected_trip, "Categoria": "Geral", "Item": desc,
                    "Valor_Final_BRL": val, "Pago": False, "Data_Ida": dates[0], "Data_Volta": dates[1]
                }
                df_fin = pd.concat([df_fin, pd.DataFrame([n])], ignore_index=True)
                save_data(df_fin, FILE_PATH)
                st.rerun()
                
        edited = st.data_editor(df_trip[["Item", "Valor_Final_BRL", "Pago"]], key="edit_viagem", num_rows="dynamic")
        # Logica simples de salvamento (pode ser melhorada com ID)
        # Aqui apenas visualização básica, a edição completa requer IDs unicos

    # ABA 2: LOGISTICA
    with t2:
        with st.expander("Cadastrar Voo"):
            c1, c2 = st.columns(2)
            orig = c1.text_input("Origem (Ex: FLN)")
            dest = c2.text_input("Destino (Ex: GRU)")
            d_ida = c1.date_input("Data Ida")
            h_ida = c1.time_input("Hora Ida")
            d_volta = c2.date_input("Data Volta")
            h_volta = c2.time_input("Hora Volta")
            det = st.text_input("Voo/Cia")
            
            if st.button("Salvar Voo"):
                n = {
                    "Viagem": selected_trip, "Tipo": "Aereo", "Origem": orig, "Destino": dest,
                    "Data_Hora_Ida": datetime.combine(d_ida, h_ida),
                    "Data_Hora_Volta": datetime.combine(d_volta, h_volta), "Detalhes": det
                }
                df_log = pd.concat([df_log, pd.DataFrame([n])], ignore_index=True)
                save_data(df_log, LOGISTICS_PATH)
                st.rerun()
        
        # Cards
        df_l = df_log[df_log['Viagem'] == selected_trip]
        for _, row in df_l.iterrows():
            # Tratamento visual para Nan
            orig_txt = str(row['Origem']) if pd.notnull(row['Origem']) and row['Origem'] != "" else "???"
            dest_txt = str(row['Destino']) if pd.notnull(row['Destino']) and row['Destino'] != "" else "???"
            
            st.info(f"✈️ **{orig_txt}** ➝ **{dest_txt}** | {row['Detalhes']}")

    # ABA 3: BI
    with t3:
        pass # Placeholder
    with t4:
        pass # Placeholder