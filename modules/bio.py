import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import date
import math
from modules import conexoes # <--- Mantendo sua conexão original

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Bio-Engineer Hub", layout="wide", page_icon="🧬")

# --- 1. CARREGAMENTO E SANEAMENTO DE DADOS ---
def load_data():
    # 1. Definição do Schema Completo
    expected_cols = [
        "Data", "Peso_kg", "Altura_m", "Idade", "Gordura_Perc", 
        "Pescoco_cm", "Cintura_cm", "Quadril_cm",
        "Biceps_cm", "Peito_cm", "Coxa_cm",
        "Sono_hrs", "Humor_0_10", "Treino_Tipo", "Obs",
        "Agua_L", "Calorias_Ingeridas", "Objetivo_Tipo",
        "Meta_Peso_kg", "Meta_BF_perc", 
        "Prot_g", "Carb_g", "Gord_g"
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
                      "Meta_Peso_kg", "Meta_BF_perc", "Prot_g", "Carb_g", "Gord_g"]
        
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

# --- 2. MOTORES CIENTÍFICOS (CÁLCULOS) ---

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

def calcular_metas_macros(peso, objetivo):
    """
    Define targets dinâmicos baseados no peso atual e objetivo.
    Estratégia: Alta Proteína para segurar massa magra.
    """
    if objetivo == "Emagrecer (Cut)":
        prot_target = peso * 2.2  # 2.2g/kg (Proteção Muscular)
        gord_target = peso * 0.8  # 0.8g/kg (Hormonal)
        # O resto vem de carbo, mas vamos fixar um teto para déficit
        # Assumindo déficit moderado, carbo flutua
        carb_target = peso * 1.5 
    elif objetivo == "Crescer (Bulk)":
        prot_target = peso * 2.0
        gord_target = peso * 1.0
        carb_target = peso * 4.0
    else: # Manter
        prot_target = peso * 1.8
        gord_target = peso * 0.9
        carb_target = peso * 2.5
        
    return int(prot_target), int(carb_target), int(gord_target)

def calcular_gasto_calorico(peso, altura_m, idade, treino_tipo, objetivo):
    # Fórmula de Mifflin-St Jeor
    tmb = (10 * peso) + (6.25 * (altura_m * 100)) - (5 * idade) + 5
    
    fatores = {
        "Descanso": 1.2,
        "Musculação": 1.35, # Ajustado para realismo
        "Cardio": 1.5,
        "Esporte": 1.6
    }
    fator = fatores.get(treino_tipo, 1.2)
    
    gasto_total = tmb * fator
    meta_calorica = gasto_total
    
    if objetivo == "Emagrecer (Cut)": meta_calorica -= 500 
    elif objetivo == "Crescer (Bulk)": meta_calorica += 300 
    
    return int(tmb), int(gasto_total), int(meta_calorica)

# --- 3. INTERFACE (FRONT-END) ---

def render_page():
    st.title("🧬 Bio-Data: Engenharia Corporal")
    st.markdown("---")
    
    df = load_data()
    
    # --- SIDEBAR: INPUT DE DADOS ---
    with st.sidebar:
        st.header("⚙️ Painel de Controle")
        
        # Recuperar últimos valores para UX fluida
        last_global = df.sort_values("Data").iloc[-1] if not df.empty else None
        
        def get_val(col, default, is_static=True, row=None):
            if row is not None: return row[col] # Se existe registro hoje
            if is_static and last_global is not None and col in last_global:
                val = last_global[col]
                return float(val) if val != "" else default
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
            # Garantir que obj_atual_val esteja na lista
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
            novo_registro = {
                "Data": data_str, "Idade": 26, "Altura_m": altura, "Objetivo_Tipo": objetivo,
                "Peso_kg": peso, "Gordura_Perc": bf_calc,
                "Pescoco_cm": pescoco, "Cintura_cm": cintura, "Quadril_cm": quadril,
                "Biceps_cm": biceps, "Peito_cm": peito, "Coxa_cm": coxa,
                "Agua_L": agua, "Calorias_Ingeridas": calorias_calc,
                "Prot_g": prot_in, "Carb_g": carb_in, "Gord_g": gord_in,
                "Treino_Tipo": treino, "Sono_hrs": sono, "Humor_0_10": humor,
                "Meta_Peso_kg": meta_peso, "Meta_BF_perc": meta_bf
            }
            
            # Remove registro anterior do mesmo dia se houver
            df_limpo = df[df['Data'] != data_str]
            df_final = pd.concat([df_limpo, pd.DataFrame([novo_registro])], ignore_index=True)
            save_data(df_final)
            st.toast("✅ Protocolo Salvo com Sucesso!")
            st.rerun()

    # --- MAIN DASHBOARD (HubSpot Style) ---
    
    # 1. Processamento dos Dados Recentes
    if df.empty:
        st.warning("Aguardando input inicial...")
        return

    current = df.sort_values("Data").iloc[-1]
    bf_atual = current['Gordura_Perc']
    massa_gorda = current['Peso_kg'] * (bf_atual / 100)
    massa_magra = current['Peso_kg'] - massa_gorda
    
    rcq, rce = calcular_visceral_proxies(current['Cintura_cm'], current['Quadril_cm'], current['Altura_m'])
    target_p, target_c, target_f = calcular_metas_macros(current['Peso_kg'], current['Objetivo_Tipo'])
    
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
    k4.metric("Massa Magra (Motor)", f"{massa_magra:.1f} kg", "Proteger a todo custo")

    st.divider()

    # 3. Painel de Controle Operacional (Macros & Milestones)
    col_op1, col_op2 = st.columns([1, 2])
    
    with col_op1:
        st.markdown("### ⛽ Combustível (Hoje)")
        
        # Proteína
        pct_prot = min(current['Prot_g'] / target_p, 1.0)
        st.write(f"**Proteína:** {int(current['Prot_g'])}/{target_p}g")
        st.progress(pct_prot)
        if pct_prot < 0.8: st.caption(f"⚠️ Faltam {target_p - current['Prot_g']}g! Tome um Whey.")
        
        # Carbo
        pct_carb = min(current['Carb_g'] / target_c, 1.0) if target_c > 0 else 0
        st.write(f"**Carboidrato:** {int(current['Carb_g'])}/{target_c}g")
        st.progress(pct_carb)
        
        # Gordura
        pct_gord = min(current['Gord_g'] / target_f, 1.0)
        st.write(f"**Gordura:** {int(current['Gord_g'])}/{target_f}g")
        st.progress(pct_gord)

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

    # 4. Tabela de Auditoria
    with st.expander("📋 Log de Engenharia (Raw Data)"):
        st.dataframe(df.sort_values("Data", ascending=False), width='stretch')

if __name__ == "__main__":
    render_page()