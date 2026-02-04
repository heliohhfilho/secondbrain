import streamlit as st
import pandas as pd
import requests
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from datetime import date
from modules import conexoes # Mantendo sua conexão original

# --- CONFIGURAÇÕES VISUAIS (ESTILO TÉCNICO) ---
plt.style.use('bmh')

# --- API FIPE ---
FIPE_BASE_URL = "https://parallelum.com.br/fipe/api/v1"

# --- CACHE & NETWORK ---
@st.cache_data(ttl=3600)
def get_marcas(tipo_veiculo):
    url = f"{FIPE_BASE_URL}/{tipo_veiculo}/marcas"
    try: return requests.get(url).json()
    except: return []

@st.cache_data(ttl=600)
def get_modelos(tipo_veiculo, marca_id):
    url = f"{FIPE_BASE_URL}/{tipo_veiculo}/marcas/{marca_id}/modelos"
    try: return requests.get(url).json()['modelos']
    except: return []

@st.cache_data(ttl=600)
def get_anos(tipo_veiculo, marca_id, modelo_id):
    url = f"{FIPE_BASE_URL}/{tipo_veiculo}/marcas/{marca_id}/modelos/{modelo_id}/anos"
    try: return requests.get(url).json()
    except: return []

def get_fipe_details(tipo_veiculo, marca_id, modelo_id, ano_id):
    url = f"{FIPE_BASE_URL}/{tipo_veiculo}/marcas/{marca_id}/modelos/{modelo_id}/anos/{ano_id}"
    try: return requests.get(url).json()
    except: return None

# --- LÓGICA DE INTELIGÊNCIA TEMPORAL (DO SCRIPT A PARA O B) ---
def get_historico_precos(tipo_veiculo, marca_id, modelo_id, lista_anos_codigos):
    """
    Itera sobre os anos disponíveis do modelo para construir o gráfico de desvalorização.
    Limita aos últimos 6 anos para performance.
    """
    dataset = []
    # Pega apenas os 6 anos mais recentes para não travar a API
    alvo = lista_anos_codigos[:6] 
    
    for item_ano in alvo:
        url = f"{FIPE_BASE_URL}/{tipo_veiculo}/marcas/{marca_id}/modelos/{modelo_id}/anos/{item_ano['codigo']}"
        try:
            r = requests.get(url).json()
            valor = float(r['Valor'].replace("R$ ", "").replace(".", "").replace(",", "."))
            # Tratamento para ano: Se for "32000" é Zero KM, convertemos para ano atual + 1 ou label específico
            ano_num = r['AnoModelo']
            dataset.append({'Ano': ano_num, 'Preco': valor, 'Label': item_ano['nome']})
        except:
            continue
    
    return pd.DataFrame(dataset).sort_values('Ano')

def plotar_grafico_tecnico(df_hist, modelo_nome):
    """Gera o objeto Figure do Matplotlib para renderizar no Streamlit"""
    fig, ax = plt.subplots(figsize=(10, 5))
    
    ax.plot(df_hist['Ano'], df_hist['Preco'], marker='o', linewidth=2.5, color='#2980b9')
    ax.set_title(f"Curva de Desvalorização: {modelo_nome}", fontweight='bold', fontsize=12)
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter('R$ {x:,.0f}'))
    ax.grid(True, linestyle='--', alpha=0.6)
    
    # Anotação no valor mais recente
    if not df_hist.empty:
        ult = df_hist.iloc[-1]
        ax.annotate(f"Ref: R$ {ult['Preco']/1000:.1f}k", 
                   (ult['Ano'], ult['Preco']), 
                   xytext=(0, 10), textcoords='offset points', 
                   ha='center', fontweight='bold',
                   bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#2980b9", alpha=0.9))
    
    return fig

# --- CÁLCULO FINANCEIRO ---
def calcular_financiamento(valor_total, entrada, taxa_mensal, meses):
    principal = valor_total - entrada
    if principal <= 0: return 0, 0
    
    i = taxa_mensal / 100
    if i == 0:
        parcela = principal / meses
    else:
        # Fórmula Price (PMT)
        parcela = principal * (i * (1 + i)**meses) / ((1 + i)**meses - 1)
    
    total_pago = (parcela * meses) + entrada
    return parcela, total_pago

# --- IO DADOS ---
def load_data():
    cols = ["ID", "Tipo", "Marca", "Modelo", "Ano_Modelo", "Placa", "Fipe_Ref", "Preco_Negociado", "KM", "Zero_Cem", "Consumo_Medio", "Status", "Data_Add"]
    df = conexoes.load_gsheet("Carros", cols)
    
    if df.empty: df = pd.DataFrame(columns=cols)
    else:
        for col in cols:
            if col not in df.columns: df[col] = 0 if col in ["ID", "Fipe_Ref", "Preco_Negociado"] else ""

    # Safe Cast
    numeric_cols = ["ID", "Fipe_Ref", "Preco_Negociado", "KM", "Zero_Cem", "Consumo_Medio"]
    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        
    return df

def save_data(df):
    conexoes.save_gsheet("Carros", df)

# --- APP PRINCIPAL ---
def render_page():
    st.set_page_config(page_title="Garage Engineering", layout="wide")
    st.header("🏎️ Garage Analytics: Engineering Edition")
    
    df = load_data()
    
    # Sidebar de Controle
    with st.sidebar:
        st.subheader("⚙️ Parâmetros de Busca")
        tipo_veiculo = st.radio("Categoria:", ["carros", "motos"], horizontal=True)

    tab_finder, tab_garage, tab_calc = st.tabs(["🔍 Buscador & Análise", "🚗 Garagem Virtual", "⚔️ Comparativo"])

    # ==============================================================================
    # TAB 1: FINDER (COM LÓGICA DO SCRIPT A)
    # ==============================================================================
    with tab_finder:
        c_search, c_results = st.columns([1, 2])
        
        with c_search:
            st.subheader("1. Definição do Veículo")
            marcas = get_marcas(tipo_veiculo)
            marcas_dict = {m['nome']: m['codigo'] for m in marcas}
            
            marca_sel = st.selectbox("Marca", options=marcas_dict.keys())
            
            id_modelo, id_ano = None, None
            
            if marca_sel:
                id_marca = marcas_dict[marca_sel]
                modelos = get_modelos(tipo_veiculo, id_marca)
                modelos_dict = {m['nome']: m['codigo'] for m in modelos}
                modelo_sel = st.selectbox("Modelo", options=modelos_dict.keys())
                
                if modelo_sel:
                    id_modelo = modelos_dict[modelo_sel]
                    anos = get_anos(tipo_veiculo, id_marca, id_modelo)
                    # Ordena anos para pegar os mais recentes primeiro na lista
                    anos_dict = {a['nome']: a['codigo'] for a in anos}
                    ano_sel = st.selectbox("Ano/Versão", options=anos_dict.keys())
                    
                    if ano_sel:
                        id_ano = anos_dict[ano_sel]
                        if st.button("🔎 Executar Análise Técnica", type="primary"):
                            # Pega dado pontual
                            dados_fipe = get_fipe_details(tipo_veiculo, id_marca, id_modelo, id_ano)
                            # Pega histórico (Loop do Script A)
                            df_hist = get_historico_precos(tipo_veiculo, id_marca, id_modelo, anos)
                            
                            st.session_state['analise_atual'] = {
                                'fipe': dados_fipe,
                                'hist': df_hist,
                                'tipo': tipo_veiculo
                            }

        with c_results:
            if 'analise_atual' in st.session_state:
                data = st.session_state['analise_atual']
                fipe = data['fipe']
                df_hist = data['hist']
                
                valor_fipe_float = float(fipe['Valor'].replace("R$ ", "").replace(".", "").replace(",", "."))

                # HEADER DO RELATÓRIO
                st.info(f"Relatório Técnico: {fipe['Modelo']}")
                m1, m2, m3 = st.columns(3)
                m1.metric("Valor de Referência", fipe['Valor'])
                m2.metric("Ano Modelo", fipe['AnoModelo'])
                m3.metric("Código Fipe", fipe['CodigoFipe'])
                
                # GRÁFICO (Importado do Script A)
                if not df_hist.empty:
                    fig = plotar_grafico_tecnico(df_hist, fipe['Modelo'])
                    st.pyplot(fig)
                
                st.divider()
                
                # CÁLCULO DE PARCELAMENTO & VIABILIDADE
                c_fin, c_tec = st.columns(2)
                
                with c_fin:
                    st.subheader("💰 Simulação Financeira")
                    input_preco = st.number_input("Preço Negociado (R$)", value=valor_fipe_float, step=500.0)
                    col_p1, col_p2, col_p3 = st.columns(3)
                    entrada = col_p1.number_input("Entrada", value=valor_fipe_float*0.2)
                    taxa = col_p2.number_input("Juros a.m (%)", value=1.5, step=0.1)
                    n_parc = col_p3.number_input("Parcelas", value=48, step=12)
                    
                    v_parcela, v_total = calcular_financiamento(input_preco, entrada, taxa, n_parc)
                    
                    st.markdown(f"""
                    <div style='background-color: #f0f2f6; padding: 10px; border-radius: 5px;'>
                        <b>Parcela Estimada:</b> R$ {v_parcela:,.2f}<br>
                        <small>Total Final: R$ {v_total:,.2f} (Ágio: {((v_total/input_preco)-1)*100:.1f}%)</small>
                    </div>
                    """, unsafe_allow_html=True)

                with c_tec:
                    st.subheader("⚙️ Dados de Compra")
                    with st.form("salvar_garagem"):
                        km = st.number_input("KM Atual", value=0)
                        placa = st.text_input("Placa (Opcional)")
                        
                        # Score Simplificado
                        delta = (input_preco - valor_fipe_float) / valor_fipe_float
                        str_delta = f"{delta*100:.1f}%"
                        if delta < 0: st.success(f"Oportunidade: {str_delta} abaixo da FIPE")
                        else: st.warning(f"Sobrepreço: {str_delta} acima da FIPE")
                        
                        if st.form_submit_button("💾 Salvar na Garagem"):
                            new_id = 1 if df.empty else df['ID'].max() + 1
                            novo = {
                                "ID": new_id, "Tipo": data['tipo'], "Marca": fipe['Marca'], 
                                "Modelo": fipe['Modelo'], "Ano_Modelo": fipe['AnoModelo'], 
                                "Placa": placa, "Fipe_Ref": valor_fipe_float, 
                                "Preco_Negociado": input_preco, "KM": km, 
                                "Zero_Cem": 0, "Consumo_Medio": 0, # Placeholder
                                "Status": "Em Análise", "Data_Add": str(date.today())
                            }
                            df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                            save_data(df)
                            st.toast("Veículo salvo com sucesso!")
                            st.rerun()

    # ==============================================================================
    # TAB 2: GARAGE (Visualização)
    # ==============================================================================
    with tab_garage:
        if df.empty:
            st.warning("Nenhum veículo monitorado.")
        else:
            st.dataframe(df.style.format({"Fipe_Ref": "R$ {:,.2f}", "Preco_Negociado": "R$ {:,.2f}"}))
            
            # Cards Detalhados
            for idx, row in df.iterrows():
                with st.expander(f"{row['Tipo'].upper()} | {row['Modelo']} ({row['Ano_Modelo']})"):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Preço Alvo", f"R$ {row['Preco_Negociado']:,.2f}")
                    c2.metric("Fipe na Data", f"R$ {row['Fipe_Ref']:,.2f}")
                    
                    if st.button("🗑️ Remover", key=f"del_{row['ID']}"):
                        df = df[df['ID'] != row['ID']]
                        save_data(df)
                        st.rerun()

    # ==============================================================================
    # TAB 3: ENGENHARIA COMPARATIVA
    # ==============================================================================
    with tab_calc:
        st.subheader("Matriz de Comparação")
        if len(df) < 2:
            st.info("Adicione pelo menos 2 veículos na garagem para comparar.")
        else:
            sel_a = st.selectbox("Veículo A", df['Modelo'].unique(), key='va')
            sel_b = st.selectbox("Veículo B", df['Modelo'].unique(), key='vb')
            
            if sel_a and sel_b:
                dA = df[df['Modelo'] == sel_a].iloc[0]
                dB = df[df['Modelo'] == sel_b].iloc[0]
                
                col_a, col_meio, col_b = st.columns([1, 0.2, 1])
                
                with col_a:
                    st.markdown(f"### {dA['Marca']}")
                    st.caption(dA['Modelo'])
                    st.metric("Investimento", f"R$ {dA['Preco_Negociado']:,.0f}")
                    st.metric("KM", f"{dA['KM']:,}")

                with col_b:
                    st.markdown(f"### {dB['Marca']}")
                    st.caption(dB['Modelo'])
                    diff_preco = dB['Preco_Negociado'] - dA['Preco_Negociado']
                    st.metric("Investimento", f"R$ {dB['Preco_Negociado']:,.0f}", f"{diff_preco:,.0f}", delta_color="inverse")
                    diff_km = dB['KM'] - dA['KM']
                    st.metric("KM", f"{dB['KM']:,}", f"{diff_km:,}", delta_color="inverse")

if __name__ == "__main__":
    render_page()