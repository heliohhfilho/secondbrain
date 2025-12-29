import streamlit as st
import pandas as pd
import requests
from datetime import date
from modules import conexoes

# --- API FIPE (Brasil) ---
FIPE_BASE_URL = "https://parallelum.com.br/fipe/api/v1"

# --- FUNÇÕES DE CACHE (Para não travar o app) ---
@st.cache_data(ttl=3600) # Cache de 1 hora
def get_marcas():
    url = f"{FIPE_BASE_URL}/carros/marcas"
    try: return requests.get(url).json()
    except: return []

@st.cache_data(ttl=600)
def get_modelos(marca_id):
    url = f"{FIPE_BASE_URL}/carros/marcas/{marca_id}/modelos"
    try: return requests.get(url).json()['modelos']
    except: return []

@st.cache_data(ttl=600)
def get_anos(marca_id, modelo_id):
    url = f"{FIPE_BASE_URL}/carros/marcas/{marca_id}/modelos/{modelo_id}/anos"
    try: return requests.get(url).json()
    except: return []

def get_fipe_details(marca_id, modelo_id, ano_id):
    # Sem cache aqui, queremos o preço fresco
    url = f"{FIPE_BASE_URL}/carros/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
    try: return requests.get(url).json()
    except: return None

# --- DADOS & SAVE ---
def load_data():
    cols = ["ID", "Marca", "Modelo", "Ano_Modelo", "Placa", "Fipe_Ref", "Preco_Negociado", "KM", "Zero_Cem", "Consumo_Medio", "Status", "Data_Add"]
    df = conexoes.load_gsheet("Carros", cols)
    if not df.empty:
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Fipe_Ref"] = pd.to_numeric(df["Fipe_Ref"], errors='coerce').fillna(0.0)
        df["Preco_Negociado"] = pd.to_numeric(df["Preco_Negociado"], errors='coerce').fillna(0.0)
        df["Zero_Cem"] = pd.to_numeric(df["Zero_Cem"], errors='coerce').fillna(0.0)
    return df

def save_data(df):
    df_s = df.copy()
    conexoes.save_gsheet("Carros", df_s)

# --- RENDERIZAÇÃO ---
def render_page():
    st.header("🏎️ Garage Analytics: Compra & Venda")
    df = load_data()

    tab_finder, tab_garage, tab_calc = st.tabs(["🔍 Buscador FIPE (Finder)", "🚗 Minha Garagem", "🧮 Calculadora de Viabilidade"])

    # ------------------------------------------------------------------
    # ABA 1: FINDER (INTEGRAÇÃO API)
    # ------------------------------------------------------------------
    with tab_finder:
        st.subheader("Analisar Oportunidade de Mercado")
        
        # 1. Seleção em Cascata (Marca -> Modelo -> Ano)
        marcas = get_marcas()
        if not marcas:
            st.error("Erro ao conectar na API FIPE.")
        else:
            marcas_dict = {m['nome']: m['codigo'] for m in marcas}
            marca_sel = st.selectbox("1. Selecione a Marca", options=marcas_dict.keys())
            
            if marca_sel:
                id_marca = marcas_dict[marca_sel]
                modelos = get_modelos(id_marca)
                modelos_dict = {m['nome']: m['codigo'] for m in modelos}
                modelo_sel = st.selectbox("2. Selecione o Modelo", options=modelos_dict.keys())
                
                if modelo_sel:
                    id_modelo = modelos_dict[modelo_sel]
                    anos = get_anos(id_marca, id_modelo)
                    anos_dict = {a['nome']: a['codigo'] for a in anos}
                    ano_sel = st.selectbox("3. Selecione o Ano/Versão", options=anos_dict.keys())
                    
                    if ano_sel:
                        # Busca o Preço Final
                        id_ano = anos_dict[ano_sel]
                        if st.button("Buscar Dados FIPE", type="primary"):
                            dados = get_fipe_details(id_marca, id_modelo, id_ano)
                            st.session_state['fipe_temp'] = dados # Salva na sessão

        # Exibição do Resultado e Input Humano
        if 'fipe_temp' in st.session_state:
            fipe = st.session_state['fipe_temp']
            st.divider()
            
            c_val, c_info = st.columns([1, 2])
            valor_fipe_float = float(fipe['Valor'].replace("R$ ", "").replace(".", "").replace(",", "."))
            
            with c_val:
                st.metric("Tabela FIPE", fipe['Valor'])
                st.caption(f"Ref: {fipe['MesReferencia']}")
            
            with c_info:
                st.markdown(f"**Veículo:** {fipe['Modelo']}")
                st.markdown(f"**Ano:** {fipe['AnoModelo']} | **Combustível:** {fipe['Combustivel']}")
            
            # INPUTS DE VIABILIDADE (INPUT HUMANO)
            with st.form("analise_compra"):
                st.subheader("🛠️ Dados da Unidade Específica")
                c1, c2 = st.columns(2)
                preco_neg = c1.number_input("Preço Pedido (R$)", min_value=0.0, value=valor_fipe_float, step=500.0)
                km_atual = c2.number_input("Quilometragem", min_value=0, value=50000, step=1000)
                
                st.markdown("---")
                st.caption("🏎️ Performance & Eficiência (Preencher Manualmente)")
                c3, c4 = st.columns(2)
                zero_cem = c3.number_input("0-100 km/h (s)", min_value=0.0, value=9.0, step=0.1)
                consumo = c4.number_input("Consumo Médio (km/l)", min_value=0.0, value=10.0, step=0.1)
                
                # CÁLCULO DE SCORE
                delta_preco = (preco_neg - valor_fipe_float) / valor_fipe_float # % acima ou abaixo
                score_eco = (consumo * 2) # Peso 2 para consumo
                score_fun = (15 - zero_cem) * 3 # Quanto menor o tempo, maior a nota (Peso 3)
                score_fin = (1 - delta_preco) * 100 # Se pagar menos, score sobe
                
                viabilidade = (score_fin * 0.5) + (score_eco * 0.2) + (score_fun * 0.3)
                
                placa = st.text_input("Placa (Opcional)")
                
                if st.form_submit_button("Salvar na Garagem"):
                    new_id = 1 if df.empty else df['ID'].max() + 1
                    novo = {
                        "ID": new_id, "Marca": fipe['Marca'], "Modelo": fipe['Modelo'],
                        "Ano_Modelo": fipe['AnoModelo'], "Placa": placa,
                        "Fipe_Ref": valor_fipe_float, "Preco_Negociado": preco_neg,
                        "KM": km_atual, "Zero_Cem": zero_cem, "Consumo_Medio": consumo,
                        "Status": "Em Análise", "Data_Add": str(date.today())
                    }
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df)
                    st.success(f"Carro salvo! Score de Viabilidade: {int(viabilidade)}")
                    del st.session_state['fipe_temp']
                    st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: GARAGEM (LISTA SALVA)
    # ------------------------------------------------------------------
    with tab_garage:
        if df.empty:
            st.info("Garagem vazia.")
        else:
            for idx, row in df.iterrows():
                delta = row['Preco_Negociado'] - row['Fipe_Ref']
                delta_perc = (delta / row['Fipe_Ref']) * 100
                
                with st.container(border=True):
                    c_tit, c_kpi = st.columns([3, 2])
                    
                    with c_tit:
                        st.subheader(f"{row['Modelo']}")
                        st.caption(f"{row['Marca']} | {row['Ano_Modelo']} | {row['KM']} km")
                        st.text(f"0-100: {row['Zero_Cem']}s | Consumo: {row['Consumo_Medio']} km/l")
                    
                    with c_kpi:
                        if delta < 0:
                            st.metric("Preço", f"R$ {row['Preco_Negociado']:,.2f}", f"{delta_perc:.1f}% abaixo FIPE", delta_color="normal")
                        else:
                            st.metric("Preço", f"R$ {row['Preco_Negociado']:,.2f}", f"+{delta_perc:.1f}% sobre FIPE", delta_color="inverse")
                        
                        st.caption(f"FIPE Ref: R$ {row['Fipe_Ref']:,.2f}")
                    
                    # Botões de Ação
                    col_b1, col_b2 = st.columns(2)
                    if col_b1.button("✅ Comprado", key=f"buy_{row['ID']}"):
                        df.at[idx, 'Status'] = 'Comprado'
                        save_data(df); st.rerun()
                    
                    if col_b2.button("🗑️ Deletar", key=f"del_{row['ID']}"):
                        df = df[df['ID'] != row['ID']]
                        save_data(df); st.rerun()

    # ------------------------------------------------------------------
    # ABA 3: COMPARATIVO (ENGENHARIA PURA)
    # ------------------------------------------------------------------
    with tab_calc:
        if len(df) >= 2:
            st.subheader("📊 Comparativo Técnico")
            # Selecionar 2 carros para duelo
            opcoes = df['Modelo'].unique()
            car1 = st.selectbox("Carro 1", opcoes, index=0)
            car2 = st.selectbox("Carro 2", opcoes, index=1 if len(opcoes)>1 else 0)
            
            if car1 and car2:
                d1 = df[df['Modelo'] == car1].iloc[0]
                d2 = df[df['Modelo'] == car2].iloc[0]
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown(f"### {d1['Marca']}")
                    st.image("https://img.icons8.com/ios/100/car--v1.png", width=50) # Placeholder
                    st.metric("0-100 km/h", f"{d1['Zero_Cem']} s")
                    st.metric("Consumo", f"{d1['Consumo_Medio']} km/l")
                    st.metric("Preço", f"R$ {d1['Preco_Negociado']/1000:.1f}k")

                with col2:
                    st.markdown(f"### {d2['Marca']}")
                    st.image("https://img.icons8.com/ios/100/car--v1.png", width=50) # Placeholder
                    delta_0100 = d2['Zero_Cem'] - d1['Zero_Cem']
                    delta_cons = d2['Consumo_Medio'] - d1['Consumo_Medio']
                    delta_price = d2['Preco_Negociado'] - d1['Preco_Negociado']

                    st.metric("0-100 km/h", f"{d2['Zero_Cem']} s", f"{delta_0100:.1f}s", delta_color="inverse")
                    st.metric("Consumo", f"{d2['Consumo_Medio']} km/l", f"{delta_cons:.1f} km/l")
                    st.metric("Preço", f"R$ {d2['Preco_Negociado']/1000:.1f}k", f"R$ {delta_price/1000:.1f}k", delta_color="inverse")
        else:
            st.info("Adicione pelo menos 2 carros para comparar.")