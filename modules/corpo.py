import streamlit as st
import pandas as pd
from modules import conexoes
import numpy as np
from sklearn.linear_model import LinearRegression
import plotly.graph_objects as go
from datetime import date
import math

#from modules.normalizacao_dados import preencher_dias_vazios

st.set_page_config(page_title="Corpo", layout="wide", page_icon="🧬")

#preencher_dias_vazios()

def load_data():
    # 1. Definição do Schema Completo
    expected_cols = [
        "Data", "Peso_kg", "Altura_m", "Idade", "Gordura_Perc", 
        "Pescoco_cm", "Cintura_cm", "Quadril_cm",
        "Biceps_cm", "Peito_cm", "Coxa_cm",
        "Sono_hrs", "Humor_0_10", "Treino_Tipo", "Obs",
        "Agua_L", "Calorias_Ingeridas", "Objetivo_Tipo",
        "Meta_Peso_kg", "Meta_BF_perc", 
        "Prot_g", "Carb_g", "Gord_g", "Calorias_Gastas", "Massa_Magra"
    ]
    
    # 2. Carregamento com tratamento de erro
    try:
        # AQUI ESTAVA O ERRO: Passando expected_cols como filtro
        df = conexoes.load_gsheet("Bio", expected_cols) 
    except Exception as e:
        st.error(f"Erro na conexão: {e}") # Mostra o erro real se houver
        df = pd.DataFrame(columns=expected_cols)

    # 3. AUTO-REPAIR: Se a planilha vier sem as colunas novas, adiciona elas com 0
    if not df.empty:
        for col in expected_cols:
            if col not in df.columns:
                if col in ["Data", "Obs", "Treino_Tipo", "Objetivo_Tipo"]:
                    df[col] = ""
                else:
                    df[col] = 0.0
    
    # 4. SANEAMENTO (Cast de Tipos)
    if not df.empty:
        cols_float = ["Peso_kg", "Altura_m", "Gordura_Perc", "Pescoco_cm", "Cintura_cm", "Quadril_cm",
                      "Biceps_cm", "Peito_cm", "Coxa_cm", "Sono_hrs", "Agua_L", 
                      "Meta_Peso_kg", "Meta_BF_perc", "Prot_g", "Carb_g", "Gord_g", "Calorias_Gastas"]
        
        for col in cols_float:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
        
        if "Idade" in df.columns:
            df["Idade"] = pd.to_numeric(df["Idade"], errors='coerce').fillna(26).astype(int)
        
        if "Calorias_Ingeridas" in df.columns:
            df["Calorias_Ingeridas"] = pd.to_numeric(df["Calorias_Ingeridas"], errors='coerce').fillna(0).astype(int)

    return df

def save_data(df):
    conexoes.save_gsheet("Bio", df)

def massa_magra_set():
    df = load_data()
    df["Massa_Magra"] = df["Peso_kg"] * (1 - (df["Gordura_Perc"] / 100))
    df["Massa_Magra"] = df["Massa_Magra"].fillna(0.0).round(2)
    save_data(df)
    return True

import pandas as pds
import numpy as np
from statsmodels.tsa.arima.model import ARIMA
import warnings
warnings.filterwarnings("ignore") # Evita alertas de convergência do statsmodels

def previsao_arimax(df_input, meta_peso=65.0):
    df = df_input.copy()

    df['Data'] = pd.to_datetime(df['Data'])
    df.set_index('Data', inplace=True)
    df = df.resample('D').ffill()

    # Feature Engineering: Lag de 5 dias
    df['Calorias_Gastas_Lag5'] = df['Calorias_Gastas'].shift(5)
    df.dropna(subset=['Calorias_Gastas_Lag5'], inplace=True)

    endog = df['Peso_kg']
    exog = df[['Calorias_Gastas_Lag5']]

    # Modelo ARIMAX (p=1, d=1, q=1)
    # d=1 aplica a 1ª diferença (I) para lidar com a tendência não-estacionária de perda de peso
    modelo = ARIMA(endog, exog=exog, order=(1, 1, 1))
    resultado = modelo.fit()

    # Previsão de Curto Prazo (7 e 14 dias)
    calorias_medias = df['Calorias_Gastas'].mean()
    
    # Criando matriz exógena para o futuro (assumindo a manutenção da média calórica)
    exog_futuro_curto = pd.DataFrame(
        {'Calorias_Gastas_Lag5': [calorias_medias] * 14}, 
        index=pd.date_range(start=df.index[-1] + pd.Timedelta(days=1), periods=14)
    )
    
    previsoes_curto = resultado.forecast(steps=14, exog=exog_futuro_curto)
    previsoes_7_14 = [previsoes_curto.iloc[6], previsoes_curto.iloc[13]]

    # Previsão de Longo Prazo para encontrar a Meta (Projeção de até 365 dias)
    passos_maximos = 10000
    exog_futuro_longo = pd.DataFrame(
        {'Calorias_Gastas_Lag5': [calorias_medias] * passos_maximos}, 
        index=pd.date_range(start=df.index[-1] + pd.Timedelta(days=1), periods=passos_maximos)
    )
    
    previsoes_longo = resultado.forecast(steps=passos_maximos, exog=exog_futuro_longo)
    
    # Busca indexada da meta
    dias_abaixo_meta = previsoes_longo[previsoes_longo <= meta_peso]
    
    if not dias_abaixo_meta.empty:
        # Pega a data (index) do primeiro dia em que o peso atingiu/passou a meta
        data_prevista = dias_abaixo_meta.index[0].strftime('%Y-%m-%d')
    else:
        data_prevista = "Meta não será atingida nos próximos 365 dias com o ritmo atual."

    impacto_calorico = resultado.params.get('Calorias_Gastas_Lag5', 0)

    return impacto_calorico, previsoes_7_14, data_prevista

def regressao_linear(df_input, meta_peso=88.0):
    df = df_input.copy()

    df['Data'] = pd.to_datetime(df['Data'])
    df.set_index('Data', inplace=True)
    df = df.resample('D').ffill().reset_index()

    df['Calorias_Gastas_Lag5'] = df['Calorias_Gastas'].shift(5)
    
    df.dropna(subset=['Calorias_Gastas_Lag5'], inplace=True)

    data_zero = df['Data'].min()
    df['Dias_Passados'] = (df['Data'] - data_zero).dt.days

    X = df[['Dias_Passados', 'Calorias_Gastas_Lag5']]
    y = df['Peso_kg']

    modelo = LinearRegression()
    modelo.fit(X, y)

    beta_dias = modelo.coef_[0]     # Tendência temporal
    beta_calorias = modelo.coef_[1]
    beta_0 = modelo.intercept_

    calorias_medias_futuro = df['Calorias_Gastas'].mean()

    ultimo_dia = df['Dias_Passados'].max()
    
    dias_futuros = pd.DataFrame({
        'Dias_Passados': [ultimo_dia + 7, ultimo_dia + 14],
        'Calorias_Gastas_Lag5': [calorias_medias_futuro, calorias_medias_futuro]
    })
    previsoes = modelo.predict(dias_futuros)

    if beta_dias >= 0:
        data_prevista = "Tendência de alta/estagnação."
    else:
        dias_para_meta = (meta_peso - beta_0 - (beta_calorias * calorias_medias_futuro)) / beta_dias
        data_prevista = data_zero + pd.to_timedelta(dias_para_meta, unit='D')

    return beta_dias, previsoes, data_prevista

def calcular_bf_marinha(altura_m, cintura_cm, pescoco_cm):
    """Estima % de Gordura Corporal pelo método da Marinha Americana."""
    if cintura_cm == 0 or pescoco_cm == 0 or altura_m == 0: return 0.0
    try:
        log_cin_pes = math.log10(cintura_cm - pescoco_cm)
        log_alt = math.log10(altura_m * 100)
        bf = 495 / (1.0324 - 0.19077 * log_cin_pes + 0.15456 * log_alt) - 450
        return round(max(2.0, bf), 1)
    except: return 0.0

def calcular_visceral_proxies(cintura, quadril, altura_m):
    """
    Calcula RCQ (Relação Cintura-Quadril) e RCE (Cintura-Estatura).
    RCQ > 0.90 em homens indica alto risco visceral.
    """
    rcq = cintura / quadril if quadril > 0 else 0
    rce = cintura / (altura_m * 100) if altura_m > 0 else 0
    return round(rcq, 2), round(rce, 2)

def render_page():
    st.title("🧬 Dados Corporais")
    st.markdown("---")

    massa_magra_set()

    df = load_data()
    tendencia_arimax, previsoes_arimax, data_prevista_arimax = previsao_arimax(df, meta_peso=88.)
    tendencia, previsoes, data_prevista = regressao_linear(df)

    with st.expander("Medidas e Pesagem", expanded=False):
        st.header("⚙️ Painel de Controle")
        
        # Recuperar últimos valores para UX fluida
        last_global = df.sort_values("Data").iloc[-1] if not df.empty else None
        
        def get_val(col, default, is_static=True, row=None):
            if row is not None:
                return row[col]
            
            if is_static and last_global is not None and col in last_global:
                val = last_global[col]

                if isinstance(default, str):
                    return str(val) if val != "" else default

                try:
                    return float(val) if val != "" else default
                except (ValueError, TypeError):
                    return default
                
            return default
        
        # Seleção de Data
        dt_selecionada = st.date_input("Data do Registro", value=date.today())
        data_str = str(dt_selecionada)
        row_hoje = df[df['Data'] == data_str].iloc[0] if not df[df['Data'] == data_str].empty else None
        existe_hoje = row_hoje is not None

        # Bloco 1: Estrutura Física
        with st.expander("1. Medidas & Estrutura", expanded=not existe_hoje):
            c_s1, c_s2 = st.columns(2)
            peso = c_s1.number_input("Peso (kg)", 40.0, 150.0, float(get_val("Peso_kg", 92.0, True, row_hoje)), 0.1)
            altura = c_s2.number_input("Altura (m)", 1.00, 2.50, float(get_val("Altura_m", 1.72, True, row_hoje)), 0.01)
            
            c_s3, c_s4 = st.columns(2)
            cintura = c_s3.number_input("Cintura (cm)", 50.0, 150.0, float(get_val("Cintura_cm", 102.0, True, row_hoje)), 0.5)
            quadril = c_s4.number_input("Quadril (cm)", 50.0, 150.0, float(get_val("Quadril_cm", 107.0, True, row_hoje)), 0.5)
            pescoco = st.number_input("Pescoço (cm)", 20.0, 60.0, float(get_val("Pescoco_cm", 40.0, True, row_hoje)), 0.5)

            if st.checkbox("Medidas Secundárias"):
                peito = st.number_input("Peito", 0.0, 200.0, float(get_val("Peito_cm", 105.0, True, row_hoje)))
                biceps = st.number_input("Bíceps", 0.0, 100.0, float(get_val("Biceps_cm", 0.0, True, row_hoje)))
                coxa = st.number_input("Coxa", 0.0, 100.0, float(get_val("Coxa_cm", 0.0, True, row_hoje)))
            else:
                peito, biceps, coxa = get_val("Peito_cm", 0.0, True, row_hoje), get_val("Biceps_cm", 0.0, True, row_hoje), get_val("Coxa_cm", 0.0, True, row_hoje)

        # Bloco 2: Gestão do Dia
        with st.expander("2. Input Diário (Variáveis)", expanded=True):
            obj_options = ["Emagrecer (Cut)", "Manter", "Crescer (Bulk)"]
            obj_atual_val = get_val("Objetivo_Tipo", "Manter", True, row_hoje)
            idx_obj = obj_options.index(obj_atual_val) if obj_atual_val in obj_options else 0
            objetivo = st.selectbox("Objetivo Vigente", obj_options, index=idx_obj)
            
            treino_opts = ["Descanso", "Musculação", "Cardio", "Esporte"]
            t_val = get_val("Treino_Tipo", "Descanso", False, row_hoje)
            treino = st.selectbox("Treino Realizado", treino_opts, index=treino_opts.index(t_val) if t_val in treino_opts else 0)
            
            # Input de Macros
            st.caption("🔢 Auditoria Nutricional (Acumulado do Dia)")
            col_m1, col_m2, col_m3 = st.columns(3)
            prot_in = col_m1.number_input("Prot (g)", 0, 500, int(get_val("Prot_g", 0, False, row_hoje)))
            carb_in = col_m2.number_input("Carb (g)", 0, 1000, int(get_val("Carb_g", 0, False, row_hoje)))
            gord_in = col_m3.number_input("Gord (g)", 0, 500, int(get_val("Gord_g", 0, False, row_hoje)))
            
            # Cálculo automático de calorias dos macros (Engenharia Reversa)
            calorias_calc = (prot_in * 4) + (carb_in * 4) + (gord_in * 9)
            st.info(f"⚡ Energia Gerada: **{calorias_calc} kcal**")
            
            agua = st.slider("Água (L)", 0.0, 8.0, float(get_val("Agua_L", 0.0, False, row_hoje)), 0.5)
            sono = st.slider("Sono (h)", 0.0, 12.0, float(get_val("Sono_hrs", 7.0, True, row_hoje)), 0.5)
            humor = st.slider("Humor/Energia", 1, 10, int(get_val("Humor_0_10", 7, True, row_hoje)))

        # Bloco 3: Metas Editáveis (O "Contrato")
        with st.expander("3. Calibração de Metas", expanded=False):
            st.warning("⚠️ Ajuste apenas se o plano mudar")
            meta_peso = st.number_input("Meta Peso (kg)", 60.0, 120.0, float(get_val("Meta_Peso_kg", 79.0, True, row_hoje)))
            meta_bf = st.number_input("Meta BF (%)", 5.0, 30.0, float(get_val("Meta_BF_perc", 13.0, True, row_hoje)))

        # --- BOTÃO DE SALVAR ---
        if st.button("💾 Gravar Dados no Banco"):
            bf_calc = calcular_bf_marinha(altura, cintura, pescoco)

            massa_gorda = peso * (bf_calc / 100)
            massa_magra = peso - massa_gorda
            
            novo_registro = {
                "Data": data_str, "Idade": 26, "Altura_m": altura, "Objetivo_Tipo": objetivo,
                "Peso_kg": peso, "Gordura_Perc": bf_calc,
                "Pescoco_cm": pescoco, "Cintura_cm": cintura, "Quadril_cm": quadril,
                "Biceps_cm": biceps, "Peito_cm": peito, "Coxa_cm": coxa,
                "Agua_L": agua, "Calorias_Ingeridas": calorias_calc,
                "Prot_g": prot_in, "Carb_g": carb_in, "Gord_g": gord_in,
                "Treino_Tipo": treino, "Sono_hrs": sono, "Humor_0_10": humor,
                "Meta_Peso_kg": meta_peso, "Meta_BF_perc": meta_bf,
                "Massa_Magra": massa_magra
            }
            
            # Remove registro anterior do mesmo dia se houver
            df_limpo = df[df['Data'] != data_str]
            df_final = pd.concat([df_limpo, pd.DataFrame([novo_registro])], ignore_index=True)
            save_data(df_final)
            st.toast("✅ Protocolo Salvo com Sucesso!")
            st.rerun()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tendencia do peso: ", f"{tendencia:.2f} Kg")
    c2.metric("Previsão 7 dias: ", f"{previsoes[0]:.2f} Kg")
    c3.metric("Previsão 14 dias: ",f"{previsoes[1]:.2f} Kg")
    c4.metric("Data Prevista para a meta: ", f"{data_prevista.strftime('%d/%m/%Y')}")

    c5, c6, c7, c8 = st.columns(4)
    # O coeficiente do ARIMAX costuma ser bem pequeno (impacto por caloria), então 4 casas decimais é ideal
    c5.metric("Impacto Calórico (Lag 5): ", f"{tendencia_arimax:.4f} Kg") 
    c6.metric("Previsão 7 dias: ", f"{previsoes_arimax[0]:.2f} Kg")
    c7.metric("Previsão 14 dias: ", f"{previsoes_arimax[1]:.2f} Kg")
    try:
        c8.metric("Data Prevista p/ Meta: ", f"{data_prevista_arimax.strftime('%d/%m/%Y')}")
    except: pass


    if df.empty:
        st.warning("Aguardando input inicial...")
        return

    current = df.sort_values("Data").iloc[-1]
    bf_atual = current['Gordura_Perc']
    massa_gorda = current['Peso_kg'] * (bf_atual / 100)
    massa_magra = current['Peso_kg'] - massa_gorda

    ontem = df.sort_values("Data").iloc[-2]
    bf_ontem = ontem['Gordura_Perc']
    massa_gorda_ontem = ontem['Peso_kg'] * (bf_ontem / 100)
    massa_magra_ontem = ontem['Peso_kg'] - massa_gorda_ontem
    
    rcq, rce = calcular_visceral_proxies(current['Cintura_cm'], current['Quadril_cm'], current['Altura_m'])
    
    # 2. Header de KPIs
    st.subheader("🎯 Status Atual vs. Objetivos")
    k1, k2, k3, k4 = st.columns(4)
    
    # KPI 1: Peso
    delta_peso = current['Peso_kg'] - current['Meta_Peso_kg']
    k1.metric("Peso Balança", f"{current['Peso_kg']} kg", f"{delta_peso:.1f} kg p/ Meta", delta_color="inverse")
    
    # KPI 2: BF%
    delta_bf = bf_atual - current['Meta_BF_perc']
    k2.metric("BF (Marinha)", f"{bf_atual}%", f"{delta_bf:.1f}% p/ Meta", delta_color="inverse")
    
    # KPI 3: Risco Visceral (RCQ)
    lbl_rcq = "Alto Risco 🚨" if rcq > 0.95 else "Moderado ⚠️" if rcq > 0.90 else "Controlado ✅"
    k3.metric("Risco Visceral (RCQ)", f"{rcq}", lbl_rcq)
    
    # KPI 4: Qualidade Massa
    k4.metric("Massa Magra (Motor)", f"{massa_magra:.1f} kg", f"{massa_magra - massa_magra_ontem:.4f}")

    st.divider()

    # 3. Painel de Controle Operacional (Macros & Milestones)
    col_op1, col_op2 = st.columns([1, 2])
    
    with col_op1:
        st.markdown("### ⛽ Combustível (Hoje)")
        
        # Encapsulamento em formulário isolado
        with st.form("form_combustivel"):
            treino_opts = ["Descanso", "Musculação", "Cardio", "Esporte"]
            t_val = get_val("Treino_Tipo", "Descanso", False, row_hoje)
            treino = st.selectbox("Tipo de Exercício", treino_opts, index=treino_opts.index(t_val) if t_val in treino_opts else 0)
            
            calorias_gastas = st.number_input("Calorias Gastas (kcal)", 0, 5000, int(get_val("Calorias_Gastas", 0, False, row_hoje)), step=50)
            
            # Botão de submissão local
            submit_combustivel = st.form_submit_button("💾 Registar Combustível")
            
            if submit_combustivel:
                # Lógica de Upsert no DataFrame
                if not df[df['Data'] == data_str].empty:
                    # Update (Mutação parcial)
                    idx = df.index[df['Data'] == data_str].tolist()[0]
                    df.at[idx, 'Treino_Tipo'] = treino
                    df.at[idx, 'Calorias_Gastas'] = calorias_gastas
                else:
                    # Insert (Criação de linha mínima se o dia não existir)
                    novo_reg = {col: 0.0 for col in df.columns} # Preenche nulos
                    novo_reg['Data'] = data_str
                    novo_reg['Treino_Tipo'] = treino
                    novo_reg['Calorias_Gastas'] = calorias_gastas
                    for col in ["Obs", "Objetivo_Tipo"]: novo_reg[col] = "" # Corrige strings
                    
                    df = pd.concat([df, pd.DataFrame([novo_reg])], ignore_index=True)
                
                # Sincronização com o banco
                save_data(df)
                st.toast("✅ Log de combustível actualizado!")
                st.rerun()

    with col_op2:
        st.markdown("### 🛣️ Roadmap (Milestones)")
        
        # Gráfico de Evolução (Peso e BF)
        df_chart = df.copy()
        df_chart['Data_dt'] = pd.to_datetime(df_chart['Data'])
        df_chart = df_chart.sort_values("Data_dt")
        
        fig = go.Figure()
        # Linha de Peso
        fig.add_trace(go.Scatter(x=df_chart['Data_dt'], y=df_chart['Peso_kg'], name='Peso Real', 
                                 line=dict(color='#3498db', width=3)))
        # Linha de Meta (Milestone Dinâmico)
        fig.add_trace(go.Scatter(x=df_chart['Data_dt'], y=df_chart['Meta_Peso_kg'], name='Meta', 
                                 line=dict(color='#2ecc71', width=2, dash='dot')))
        
        fig.update_layout(height=300, margin=dict(l=20, r=20, t=20, b=20), legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, width='stretch')

    st.divider()

    window = 7
    df['Delta_Massa_7D'] = df['Massa_Magra'].diff(window)
    df['Soma_Calorias_7D'] = df['Calorias_Gastas'].rolling(window=window).sum()
    df['Eficiencia_Metabolica'] = (df['Delta_Massa_7D'] / df['Soma_Calorias_7D']) * 1000
    df['Eficiencia_SMA14'] = df['Eficiencia_Metabolica'].rolling(window=14).mean()

    valor_atual = df['Eficiencia_Metabolica'].iloc[-1]

    # --- PALETA CYBERPUNK ---
    CYBER_BLACK = "#000000"     # Fundo azul muito escuro
    NEON_CYAN = "#55ead4"       # Azul elétrico principal
    NEON_PINK = "#c5003c"       # Zona de perigo/negativa
    NEON_YELLOW = "#772289"     # Barra de valor atual (destaque)
    NEON_GREEN = "#4bff21"      # Zona ideal
    DARK_BLUE_UI = "#051A30"    # Cor para elementos neutros do gauge

    fig = go.Figure(go.Indicator(
        mode = "gauge+number+delta",
        value = valor_atual,
        domain = {'x': [0, 1], 'y': [0, 1]},
        
        # Título com estilo HTML para forçar a fonte e cor
        title = {
            'text': "<span style='font-family: \"Courier New\", monospace; color: #00FFF7; font-weight:bold;'>STATUS // EFICIÊNCIA METABÓLICA (η)</span>",
            'font': {'size': 20}
        },
        
        # Estilo do número principal
        number = {
            'font': {'family': '"Courier New\", monospace', 'size': 40, 'color': NEON_CYAN},
            'suffix': " g/kcal"
        },
        
        # Estilo do Delta (a variação)
        delta = {
            'reference': 0, 
            'position': "top", 
            'font': {'family': '"Courier New\", monospace', 'size': 18},
            'increasing': {'color': NEON_GREEN, 'symbol': "▲ UP LINK "},
            'decreasing': {'color': NEON_PINK, 'symbol': "▼ SYS FAIL "}
        },
        
        gauge = {
            'shape': "angular", # Formato mais agressivo/técnico
            'axis': {
                'range': [-5, 2.5], 
                'tickwidth': 2, 
                'tickcolor': NEON_CYAN, # Ticks brilhantes
                'tickfont': {'family': '"Courier New\", monospace', 'color': NEON_CYAN},
            },
            # A "agulha" ou barra de preenchimento
            'bar': {
                'color': NEON_YELLOW, # Amarelo Cyberpunk para destacar
                'thickness': 0.40
            },
            # Fundo do gauge
            'bgcolor': DARK_BLUE_UI,
            'borderwidth': 3,
            'bordercolor': NEON_CYAN, # Borda brilhante
            
            # As zonas de performance com cores neon
            'steps': [
                # Zona de "Glitch" / Catabolismo (Negativa)
                {'range': [-5, 0], 'color': NEON_PINK},  
                
                # Zona Neutra (Transição) - Um azul mais apagado
                {'range': [0, 0.5], 'color': '#003366'},
                
                # Zona de Performance Ideal (Onde você está)
                {'range': [0.5, 1.8], 'color': NEON_GREEN}, 
                
                # Zona de Overclock (Pico)
                {'range': [1.8, 2.5], 'color': NEON_CYAN} 
            ],
            
            # Linha de referência do seu objetivo ou média
            'threshold': {
                'line': {'color': NEON_YELLOW, 'width': 5},
                'thickness': 1.0,
                'value': df['Eficiencia_Metabolica'].iloc[-1] # Sua marca atual
            }
        }
    ))

    # Configuração do Layout Geral para o fundo escuro
    fig.update_layout(
        paper_bgcolor = CYBER_BLACK, # Fundo do gráfico inteiro
        font = {'family': '"Courier New\", monospace', 'color': NEON_CYAN}, # Fonte padrão
        margin=dict(l=30, r=30, t=80, b=30), # Margens ajustadas
        height=400
    )

    st.plotly_chart(fig, use_container_width=True)

    # 4. Tabela de Auditoria
    with st.expander("📋 Log de Engenharia (Raw Data)"):
        st.dataframe(df.sort_values("Data", ascending=False), width='stretch')