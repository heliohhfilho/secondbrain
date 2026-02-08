import streamlit as st
import pandas as pd
from datetime import datetime
from datetime import date, timedelta
from modules import conexoes
import altair as alt
import time
from dateutil.relativedelta import relativedelta
import requests
import math

st.set_page_config(layout="wide", page_title="Finance Dashboard")

# --- NOVOS SCHEMAS (FINANCIAMENTO) ---
def get_financiamentos_schema():
    return ["Nome", "Valor_Emprestado", "Valor_Parcela", "Qtd_Total", "Qtd_Pagas", "Data_Inicio", "Tipo"] # Tipo: Carro, Casa, Empréstimo

# --- ETL FINANCIAMENTOS ---
def load_financiamentos_data():
    try:
        df = conexoes.load_gsheet("Financiamentos", get_financiamentos_schema())
        cols_num = ["Valor_Emprestado", "Valor_Parcela"]
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        cols_int = ["Qtd_Total", "Qtd_Pagas"]
        for c in cols_int:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    except:
        df = pd.DataFrame(columns=get_financiamentos_schema())
    return df

def save_financiamentos_data(df):
    try:
        with st.spinner('Salvando Financiamento...'):
            conexoes.save_gsheet("Financiamentos", df)
        st.toast("Contrato atualizado!", icon="bank")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

def projetar_futuro(df_parcelas, df_financiamentos, salario, div_mensal_inicial, saldo_cdi_inicial, config_pesos, dy_medio_carteira, teto_cdi, simulacao=None, dias_fechamento=None):
    """
    Atualizado para incluir Financiamentos Recorrentes.
    """
    hoje = datetime.now().date()
    dados_meses = []

    if not dias_fechamento:
        dias_fechamento = {"Nubank": 2, "Itaú": 1, "Mercado Pago": 5, "Banco Pan": 26}

    # Prepara listas
    lista_despesas = df_parcelas.to_dict('records')
    lista_financiamentos = df_financiamentos.to_dict('records') if not df_financiamentos.empty else []

    if simulacao:
        lista_despesas.append({
            "O Quê": simulacao['desc'],
            "Valor": simulacao['valor'] / simulacao['vezes'],
            "Vezes": simulacao['vezes'],
            "Data_Compra": simulacao['data'].strftime("%Y-%m-%d"),
            "Cartão": simulacao['cartao'],
            "Simulado": True
        })

    # Variáveis Acumuladoras
    div_projetado = div_mensal_inicial
    saldo_cdi_proj = saldo_cdi_inicial
    peso_fii = config_pesos.get('p_fii', 0.25)
    peso_cdi = config_pesos.get('p_cdi', 0.25)
    soma_pesos = peso_fii + peso_cdi
    if soma_pesos == 0: soma_pesos = 1

    for i in range(12):
        data_ref = hoje + relativedelta(months=i)
        mes_ref = data_ref.month
        ano_ref = data_ref.year
        
        gastos_cartao = 0.0
        gastos_finan = 0.0

        # 1. Soma Cartão (Lógica existente)
        for despesa in lista_despesas:
            data_compra = datetime.strptime(str(despesa["Data_Compra"]), "%Y-%m-%d").date()
            dia_fec = dias_fechamento.get(despesa["Cartão"], 1)
            
            if data_compra.day >= dia_fec: inicio_pagto = data_compra + relativedelta(months=1)
            else: inicio_pagto = data_compra
            
            data_primeira_parc = date(inicio_pagto.year, inicio_pagto.month, 1)
            data_ultima_parc = data_primeira_parc + relativedelta(months=despesa["Vezes"] - 1)
            data_mes_loop = date(ano_ref, mes_ref, 1)

            if data_primeira_parc <= data_mes_loop <= data_ultima_parc:
                gastos_cartao += float(despesa["Valor"])
        
        # 2. Soma Financiamentos (NOVA LÓGICA)
        for fin in lista_financiamentos:
            # Assume que começa a pagar no mês seguinte ao inicio
            dt_inicio = datetime.strptime(str(fin["Data_Inicio"]), "%Y-%m-%d").date()
            dt_fim = dt_inicio + relativedelta(months=fin["Qtd_Total"])
            
            # Se a data atual do loop está dentro do contrato
            if dt_inicio <= date(ano_ref, mes_ref, 28) <= dt_fim:
                # Verifica se já não foi quitado (Pagas < Total)
                # Na projeção, assumimos pagamento linear, mas descontamos o que já foi pago
                meses_corridos = (ano_ref - dt_inicio.year) * 12 + (mes_ref - dt_inicio.month)
                if meses_corridos < fin["Qtd_Total"]:
                    gastos_finan += float(fin["Valor_Parcela"])

        # --- A MÁGICA DA PROJEÇÃO ---
        total_entradas = salario + div_projetado
        saldo_operacional = total_entradas - gastos_cartao - gastos_finan # Subtrai financiamento
        
        aporte_fii = 0.0
        aporte_cdi = 0.0
        
        if saldo_operacional > 0:
            investimento_total_mes = saldo_operacional 
            aporte_fii = investimento_total_mes * (peso_fii / soma_pesos)
            aporte_cdi = investimento_total_mes * (peso_cdi / soma_pesos)
            
            div_projetado += (aporte_fii * dy_medio_carteira)
            saldo_cdi_proj = saldo_cdi_proj + (saldo_cdi_proj * 0.01) + aporte_cdi
        else:
            saldo_cdi_proj += (saldo_cdi_proj * 0.01)
            
        atingiu_teto = "✅" if saldo_cdi_proj >= teto_cdi else "⏳"

        dados_meses.append({
            "Mês": data_ref.strftime("%b/%y"),
            "Entradas (Cresc.)": total_entradas,
            "Dividendos Proj.": div_projetado,
            "Gastos Cartão": gastos_cartao,
            "Financiamentos": gastos_finan, # Nova Coluna
            "Aporte FII": aporte_fii,
            "Aporte CDI": aporte_cdi,
            "Saldo CDI (Juros)": saldo_cdi_proj,
            "Status Reserva": atingiu_teto,
            "Balanço": saldo_operacional
        })

    return pd.DataFrame(dados_meses)

# --- FUNÇÕES DE CONTROLE DE CICLO (MÊS VIGENTE) ---
def get_datas_ciclo(dia_corte=5):
    hoje = date.today()
    
    # Se hoje é dia 1, 2, 3 ou 4, ainda estamos no ciclo do mês anterior
    if hoje.day < dia_corte:
        # Começou no mês passado
        if hoje.month == 1:
            data_inicio = date(hoje.year - 1, 12, dia_corte)
        else:
            data_inicio = date(hoje.year, hoje.month - 1, dia_corte)
        
        data_fim = date(hoje.year, hoje.month, dia_corte - 1)
    else:
        # Estamos no ciclo do mês atual que vai até o mês que vem
        data_inicio = date(hoje.year, hoje.month, dia_corte)
        if hoje.month == 12:
            data_fim = date(hoje.year + 1, 1, dia_corte - 1)
        else:
            data_fim = date(hoje.year, hoje.month + 1, dia_corte - 1)
            
    return data_inicio, data_fim

def carregar_estado_do_ciclo_atual(df):
    """
    Busca o ÚLTIMO registro salvo dentro do ciclo vigente para preencher os inputs.
    Isso evita que o usuário tenha que digitar tudo de novo todo dia.
    """
    # 1. Calcula as datas PRIMEIRO (correção do erro NoneType)
    data_ini, data_fim = get_datas_ciclo()

    # 2. Se não tem dados, retorna as datas calculadas e não faz nada
    if df.empty:
        return data_ini, data_fim
    
    # Converte coluna de data para datetime se for string
    if df["Data_Registro"].dtype == 'object':
        df["Data_Registro"] = pd.to_datetime(df["Data_Registro"])
    
    # Filtra dados dentro da janela do ciclo (Ex: 05/Fev a 04/Mar)
    mascara = (df["Data_Registro"].dt.date >= data_ini) & (df["Data_Registro"].dt.date <= data_fim)
    df_ciclo = df.loc[mascara]
    
    if not df_ciclo.empty:
        # Pega o último registro salvo (o estado mais recente)
        ultimo_estado = df_ciclo.iloc[-1]
        
        # Mapeamento: Coluna do DF -> Chave do st.session_state
        mapa_estado = {
            "Salario": "sal_prin",
            "Gasto_Pan": "input_pan",
            "Gasto_Itau": "input_itau", 
            "Gasto_MP": "input_mp", 
            "Gasto_Nu": "input_nu",
            "Outros_Desc": "d_out",
            "Outros_Val": "v_out",
            "Peso_FII": "p_fii",
            "Peso_CDI": "p_cdi",
            "Peso_Lazer": "p_laz",
            "Peso_Casa": "p_cas",
            "Peso_Carro": "p_car",
            "Peso_Vida": "p_vid",
            "Div_Valor": "div",
            "Free_Valor": "free",
            "DT_Valor": "dt",
            "Pres_Valor": "pres",
            "Meta_Preco_Cota_FII": "preco_cota"
        }
        
        # Atualiza a sessão SE a chave ainda não estiver inicializada pelo usuário
        for col, key in mapa_estado.items():
            if key not in st.session_state:
                st.session_state[key] = ultimo_estado[col]
                
    return data_ini, data_fim

# --- SCHEMAS DE DADOS ---
def get_portfolio_schema():
    return ["Ticker", "Cotas", "Preco_Medio", "DY_Anual_Estimado", "Segmento"]

def get_transacoes_schema():
    return ["Data", "Ticker", "Tipo", "Cotas", "Preco", "Total"]

def get_cdi_schema():
    return ["Nome_Caixa", "Saldo_Atual", "Ultima_Atualizacao"]

# --- NOVOS SCHEMAS ---
def get_parcelas_schema():
    return ["O Quê", "Vezes", "Valor", "Pagas", "Restantes", "Faltam", "Cartão", "Data_Compra"]

# --- FUNÇÕES DE ETL PARA CARTÕES/PARCELAS ---
def load_parcelas_data():
    try:
        df = conexoes.load_gsheet("Parcelas", get_parcelas_schema())
        # Garante tipos numéricos
        cols_num = ["Valor", "Faltam"]
        for c in cols_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)
        # Garante inteiros
        cols_int = ["Vezes", "Pagas", "Restantes"]
        for c in cols_int:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)
    except:
        df = pd.DataFrame(columns=get_parcelas_schema())
    return df

def save_parcelas_data(df):
    try:
        with st.spinner('Atualizando Parcelamentos...'):
            conexoes.save_gsheet("Parcelas", df)
        st.toast("Parcela registrada!", icon="💳")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- FUNÇÕES DE ETL PARA INVESTIMENTOS ---
def load_investments_data():
    # Carrega Carteira
    try:
        df_port = conexoes.load_gsheet("Carteira", get_portfolio_schema())
        # Garante numérico
        for c in ["Cotas", "Preco_Medio", "DY_Mensal_Perc"]:
            if c in df_port.columns: df_port[c] = pd.to_numeric(df_port[c], errors='coerce').fillna(0.0)
    except:
        df_port = pd.DataFrame(columns=get_portfolio_schema())

    # Carrega Histórico Transações
    try:
        df_hist = conexoes.load_gsheet("Historico_Transacoes", get_transacoes_schema())
    except:
        df_hist = pd.DataFrame(columns=get_transacoes_schema())

    # Carrega CDI (Caixinhas)
    try:
        df_cdi = conexoes.load_gsheet("CDI_Caixinhas", get_cdi_schema())
        if not df_cdi.empty:
             df_cdi["Saldo_Atual"] = pd.to_numeric(df_cdi["Saldo_Atual"], errors='coerce').fillna(0.0)
    except:
        # Cria a caixinha padrão se não existir
        df_cdi = pd.DataFrame([{"Nome_Caixa": "Reserva de Emergência", "Saldo_Atual": 0.0, "Ultima_Atualizacao": datetime.now().strftime("%Y-%m-%d")}])
    
    return df_port, df_hist, df_cdi

def save_investments_data(df_port, df_hist, df_cdi):
    try:
        with st.spinner('Salvando dados de investimento...'):
            conexoes.save_gsheet("Carteira", df_port)
            conexoes.save_gsheet("Historico_Transacoes", df_hist)
            conexoes.save_gsheet("CDI_Caixinhas", df_cdi)
        st.toast("Investimentos atualizados!", icon="💰")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- 1. DEFINIÇÃO DO SCHEMA (Colunas do Banco de Dados) ---
def get_financial_schema():
    return [
        "Data_Registro", "Salario",
        # Gastos
        "Gasto_Pan", "Gasto_Itau", "Gasto_MP", "Gasto_Nu", 
        "Outros_Desc", "Outros_Val",
        # Pesos Configurados
        "Peso_FII", "Peso_CDI", "Peso_Lazer", "Peso_Casa", "Peso_Carro", "Peso_Vida",
        # Entradas Extras
        "Div_Valor", "Free_Valor", "DT_Valor", "Pres_Valor",
        # Planejamento
        "Meta_Preco_Cota_FII"
    ]

# --- 2. FUNÇÕES DE ETL (Extract, Transform, Load) ---
def load_data():
    schema = get_financial_schema()
    
    # 1. Carrega usando seu módulo conexoes
    # Nota: Certifique-se de criar uma aba chamada "Financeiro" na sua planilha Life_OS_Database
    df = conexoes.load_gsheet("Financeiro", schema) 
    
    # 2. Tratamento de Tipos (Casting)
    # Como o save_gsheet converte tudo para string, precisamos converter de volta para float
    if not df.empty:
        # Colunas que são números
        cols_float = [c for c in schema if c not in ["Data_Registro", "Outros_Desc"]]
        
        for col in cols_float:
            if col in df.columns:
                # 'coerce' transforma erros (textos vazios) em NaN, depois fillna(0.0)
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    
    return df

def save_current_state():
    # 1. Carrega histórico para não perder dados anteriores
    df_antigo = load_data()
    
    # 2. Captura dados da Sessão Atual
    new_data = {
        "Data_Registro": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Salario": st.session_state.get("sal_prin", 0.0),
        
        "Gasto_Pan": st.session_state.get("input_pan", 0.0),
        "Gasto_Itau": st.session_state.get("input_itau", 0.0),
        "Gasto_MP": st.session_state.get("input_mp", 0.0),
        "Gasto_Nu": st.session_state.get("input_nu", 0.0),
        
        "Outros_Desc": st.session_state.get("d_out", ""),
        "Outros_Val": st.session_state.get("v_out", 0.0),
        
        "Peso_FII": st.session_state.get("p_fii", 0.0),
        "Peso_CDI": st.session_state.get("p_cdi", 0.0),
        "Peso_Lazer": st.session_state.get("p_laz", 0.0),
        "Peso_Casa": st.session_state.get("p_cas", 0.0),
        "Peso_Carro": st.session_state.get("p_car", 0.10),
        "Peso_Vida": st.session_state.get("p_vid", 0.05),
        
        "Div_Valor": st.session_state.get("div", 0.0),
        "Free_Valor": st.session_state.get("free", 0.0),
        "DT_Valor": st.session_state.get("dt", 0.0),
        "Pres_Valor": st.session_state.get("pres", 0.0),
        
        "Meta_Preco_Cota_FII": st.session_state.get("preco_cota", 0.0)
    }
    
    # 3. Concatena e Salva
    df_new_row = pd.DataFrame([new_data])
    
    # Se o df antigo estiver vazio, o novo é o principal, senão concatena
    if df_antigo.empty:
        df_final = df_new_row
    else:
        df_final = pd.concat([df_antigo, df_new_row], ignore_index=True)
    
    try:
        with st.spinner('Salvando no Google Sheets...'):
            conexoes.save_gsheet("Financeiro", df_final)
        st.toast("Dados salvos com sucesso!", icon="✅")
    except Exception as e:
        st.error(f"Erro ao salvar: {e}")

# --- 3. RENDERIZAÇÃO DA PÁGINA (UI) ---
def render_page():
    st.title("💵 Financeiro")
    st.markdown("---")

    df_financeiro = load_data() 
    data_ini, data_fim = carregar_estado_do_ciclo_atual(df_financeiro)
    df_portfolio, df_historico, df_cdi = load_investments_data()
    df_parcelas = load_parcelas_data()
    df_finan = load_financiamentos_data()

    if st.session_state.get("sal_prin", 0) == 0:
        st.session_state["sal_prin"] = 2466.00

    salario = st.session_state["sal_prin"]
    div_atual = st.session_state.get("div", 0.0)
    saldo_cdi_atual = df_cdi["Saldo_Atual"].sum() if not df_cdi.empty else 0.0
    custo_finan_mensal = df_finan["Valor_Parcela"].sum() if not df_finan.empty else 0.0
    
    pesos = {
        "p_fii": st.session_state.get("p_fii", 0.25),
        "p_cdi": st.session_state.get("p_cdi", 0.25)
    }

    # DY Médio para projeção
    dy_medio_mensal = 0.008 
    if not df_portfolio.empty and "DY_Mensal_Real" in df_portfolio.columns:
        investido = df_portfolio["Cotas"] * df_portfolio["Preco_Medio"]
        total_inv = investido.sum()
        if total_inv > 0:
            dy_medio_mensal = (investido * df_portfolio["DY_Mensal_Real"]).sum() / total_inv

    # Gera o df_proj aqui (Escopo Global da função render_page)
    df_proj = projetar_futuro(
        df_parcelas, df_finan, salario, div_atual, saldo_cdi_atual, 
        pesos, dy_medio_mensal, teto_cdi=20000.0, # valor default ou da session
        simulacao=None, dias_fechamento=None
    )

    # --- 3. AGORA SIM, AS TABS ---
    tab_visao_geral, tab_investimento, tab_cartao, tab_futuro, tab_financiamento, tab_sonho = st.tabs(["Visão Geral", "Investimentos", "Cartão", "Futuro", "Financiamento", "Sonho"])

    with tab_visao_geral:
        # CSS Customizado
        st.markdown("""
            <style>
            [data-testid="stMetricValue"] { font-size: 1.8rem; }
            .main-header { font-size: 1.2rem; font-weight: bold; margin-bottom: 15px; color: #1E88E5; border-bottom: 2px solid #f0f2f6; }
            </style>
        """, unsafe_allow_html=True)

        if not df_proj.empty:
            # Pega o 'Balanço' da primeira linha (mês atual)
            balanco = df_proj.iloc[0]['Balanço'] 
        else:
            balanco = 0.0

        df_finan = load_financiamentos_data()
        custo_finan_mensal = df_finan["Valor_Parcela"].sum() if not df_finan.empty else 0.0

        # Função para EXIBIR valores (Read-Only) com estilo de cartão
        def criar_linha_display(label, valor, key_session=None):
            # Se tiver key_session, tenta pegar o valor atualizado da memória, senão usa o valor passado
            val_final = st.session_state.get(key_session, valor) if key_session else valor
            
            c1, c2 = st.columns([1, 1], vertical_alignment="center")
            with c1: 
                st.markdown(f"**{label}**")
            with c2:
                # Usamos um container visual cinza para indicar "apenas leitura"
                st.markdown(
                    f"<div style='background-color: #e0e0e0; padding: 8px; border-radius: 5px; text-align: right; color: #333; font-weight: bold;'>R$ {val_final:,.2f}</div>", 
                    unsafe_allow_html=True
                )
            return val_final

        # Funções Auxiliares de UI
        def criar_linha_input(label, key, is_text=False):
            c1, c2 = st.columns([1, 1], vertical_alignment="center")
            with c1: st.markdown(f"**{label}**")
            with c2:
                if is_text: return st.text_input(label, label_visibility="collapsed", key=key)
                else: return st.number_input(label, label_visibility="collapsed", step=0.01, format="%.2f", key=key)

        # Recupera Variáveis da Sidebar/Sessão
        salario = st.session_state.get("sal_prin", 2466.00)
        
        # Pesos
        p_fii = st.session_state.get("p_fii", 0.25)
        p_cdi = st.session_state.get("p_cdi", 0.25)
        p_laz = st.session_state.get("p_laz", 0.20)
        p_cas = st.session_state.get("p_cas", 0.15)
        p_car = st.session_state.get("p_car", 0.10)
        p_vid = st.session_state.get("p_vid", 0.05)

        # --- CÁLCULO DE INVESTIMENTOS REALIZADOS (Do Histórico) ---
        # Filtra compras de FIIs feitas NESTE CICLO (entre dia 05 e 04)
        if not df_historico.empty:
            df_historico["Data"] = pd.to_datetime(df_historico["Data"])
            # data_ini e data_fim vêm da função de ciclo que criamos antes
            mask_ciclo = (df_historico["Data"].dt.date >= data_ini) & (df_historico["Data"].dt.date <= data_fim) & (df_historico["Tipo"] == "Compra")
            investido_fii_real = df_historico[mask_ciclo]["Total"].sum()
        else:
            investido_fii_real = 0.0

        # --- LAYOUT PRINCIPAL ---
        col1, col2, col3 = st.columns([1.2, 2.2, 1.6], gap="large")

        with col1:
            with st.container(border=True):
                st.markdown('<p class="main-header">Entradas e Cartões</p>', unsafe_allow_html=True)
                
                criar_linha_display("Salário Líquido", salario)
                st.caption("Editável na barra lateral 👈")

                st.divider()
                st.caption("Gastos Por Cartão (Automático)")
                v_pan = criar_linha_display("Banco Pan", 0.0, key_session="input_pan")
                v_itau = criar_linha_display("Itaú", 0.0, key_session="input_itau")
                v_mp = criar_linha_display("Mercado Pago", 0.0, key_session="input_mp")
                v_nu = criar_linha_display("Nubank", 0.0, key_session="input_nu")

                st.divider()
                st.caption("Outros Gastos")
                criar_linha_display("Financiamentos", custo_finan_mensal)
                desc_outros = criar_linha_input("Descrição", "d_out", is_text=True)
                valor_outros = criar_linha_input("Valor", "v_out")

            with st.container(border=True):
                st.markdown('<p class="main-header">Fluxo de Caixa Real</p>', unsafe_allow_html=True)
                
                base_chart = alt.Chart(df_proj).encode(x=alt.X('Mês', sort=None))

                # Barra de Gastos Cartão
                bar_gastos = base_chart.mark_bar(color='#D32F2F', opacity=0.7).encode(
                    y='Gastos Cartão', tooltip=['Mês', 'Gastos Cartão']
                )
                
                # Barra de Financiamento (Sobreposta ou empilhada)
                bar_finan = base_chart.mark_bar(color='#FFA000', opacity=0.8).encode(
                    y='Financiamentos', tooltip=['Mês', 'Financiamentos']
                )
                
                # Linha de Entradas (Receita Total)
                line_entradas = base_chart.mark_line(color='#2E7D32', strokeWidth=3).encode(
                    y='Entradas (Cresc.)', tooltip=['Mês', 'Entradas (Cresc.)']
                )

                # Área de Investimento
                area_inv = base_chart.mark_area(color='#1976D2', opacity=0.3).encode(
                    y='Aporte FII', tooltip=['Mês', 'Aporte FII']
                )

                # Combina tudo (Note o bar_finan adicionado)
                chart_final = (bar_gastos + bar_finan + area_inv + line_entradas).properties(height=350)
                st.altair_chart(chart_final, width='stretch')
                
                st.divider()
                st.metric("Sobra em Caixa", f"R$ {balanco:,.2f}", delta="Livre", delta_color="normal" if balanco > 0 else "inverse")

        with col2:
            with st.container(border=True):
                st.markdown('<p class="main-header">Gestão de Parcelas</p>', unsafe_allow_html=True)
                df_parcelas = load_parcelas_data()
                # Apenas visualização, edição deve ser controlada
                st.dataframe(
                    df_parcelas[["Cartão", "O Quê", "Valor", "Pagas", "Restantes"]], 
                    width='stretch', 
                    hide_index=True,
                    height=250
                )

            with st.container(border=True):
                st.markdown('<p class="main-header">Alocação Ideal (Planejamento)</p>', unsafe_allow_html=True)
                
                # Visualização da distribuição ideal baseada no salário
                c_a1, c_a2 = st.columns([1, 1])
                with c_a1:
                    st.write("**Categoria**")
                    st.caption(f"FIIs ({p_fii*100:.0f}%)")
                    st.caption(f"CDI ({p_cdi*100:.0f}%)")
                    st.caption(f"Lazer ({p_laz*100:.0f}%)")
                    st.caption(f"Casa ({p_cas*100:.0f}%)")
                    st.caption(f"carro ({p_car*100:.0f}%)")
                    st.caption(f"Vida ({p_vid*100:.0f}%)")
                
                with c_a2:
                    st.write("**Meta R$**")
                    st.markdown(f"R$ {salario * p_fii:,.2f}")
                    st.markdown(f"R$ {salario * p_cdi:,.2f}")
                    st.markdown(f"R$ {salario * p_laz:,.2f}")
                    st.markdown(f"R$ {salario * p_cas:,.2f}")
                    st.markdown(f"R$ {salario * p_car:,.2f}")
                    st.markdown(f"R$ {salario * p_vid:,.2f}")

            with st.container(border=True):
                st.markdown('<p class="main-header">Veículo Ideal (Engenharia Reversa)</p>', unsafe_allow_html=True)
                
                # Parâmetros de entrada baseados no seu contexto
                taxa_juros = 0.044  # 1.5% a.m.
                fipe_max = (salario * p_car) / 0.015
                limite_parcela = salario * 0.45
                
                c_v1, c_v2 = st.columns([1, 1])
                with c_v1:
                    st.metric("Manutenção Mensal (Alocado)", f"R$ {salario * p_car:,.2f}")
                with c_v2:
                    st.metric("Tabela FIPE Máxima", f"R$ {fipe_max:,.2f}")

                st.divider()

                # Lógica de Simulação
                periodos = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 18, 20, 22, 24, 36, 48]
                dados_simulacao = []

                for n in periodos:
                    if n == 1:
                        pmt = fipe_max
                        label = "À Vista"
                    else:
                        # Sistema Price
                        pmt = fipe_max * (taxa_juros * (1 + taxa_juros)**n) / ((1 + taxa_juros)**n - 1)
                        label = f"{n}x"
                    
                    valor_total = pmt * n
                    crit_renda = pmt <= limite_parcela
                    crit_balanco = pmt <= balanco
                    eh_viavel = crit_renda and crit_balanco
                    
                    # Definição da Dica (Tooltip)
                    if eh_viavel:
                        dica = "Dentro dos parâmetros financeiros."
                    elif not crit_renda:
                        dica = f"Inviável: Parcela excede 45% da renda (R$ {limite_parcela:,.2f})"
                    else:
                        dica = f"Inviável: Balanço insuficiente (Saldo: R$ {balanco:,.2f})"
                    
                    dados_simulacao.append({
                        "Prazo": label,
                        "Parcela (R$)": f"R$ {pmt:,.2f}",
                        "Comprometimento": f"{(pmt/salario)*100:.1f}%",
                        "Status": "✅ Viável" if eh_viavel else "❌ Inviável",
                        "Valor Pago (R$)": f"R$ {valor_total:,.2f}"
                    })

                # Exibição em Tabela para melhor visualização (estilo engenharia)
                st.write(f"**Análise de Financiamento (Limite: R$ {limite_parcela:,.2f}/mês)**")
                st.table(dados_simulacao)


        with col3:
            with st.container(border=True):
                st.markdown('<p class="main-header">Receitas Adicionais</p>', unsafe_allow_html=True)
                
                # --- CÁLCULO AUTOMÁTICO DE DIVIDENDOS ---
                # Pega a carteira carregada no início da função e calcula a renda mensal esperada
                if not df_portfolio.empty and "DY_Anual_Estimado" in df_portfolio.columns:
                     # Fórmula: Cotas * PM * (DY Anual / 100 / 12)
                     renda_proj = (df_portfolio["Cotas"] * df_portfolio["Preco_Medio"] * (df_portfolio["DY_Anual_Estimado"] / 100 / 12)).sum()
                else:
                     renda_proj = 0.0
                
                # Atualiza a sessão para que o botão "Salvar" pegue esse valor correto
                st.session_state["div"] = renda_proj

                # Exibe como Leitura (Display)
                div = criar_linha_display("Dividendos (Est.)", renda_proj)
                
                # Os outros continuam editáveis (Inputs)
                free = criar_linha_input("Freelancer", "free")
                dt = criar_linha_input("Day Trade", "dt")
                pres = criar_linha_input("Presente", "pres")
                
                total_extra = div + free + dt + pres
                
                st.divider()
                st.metric("Total Extra", f"R$ {total_extra:.2f}")

            with st.container(border=True):
                st.markdown('<p class="main-header">Planejamento de Compra (Pacote FIIs)</p>', unsafe_allow_html=True)
                
                custo_pacote = df_portfolio["Preco_Medio"].sum() if not df_portfolio.empty else 0.0
                
                # Cenários
                orcamento_ideal = (salario * p_fii) + div
                orcamento_real = balanco # O que sobrou na conta
                
                qtd_ideal = int(orcamento_ideal // custo_pacote) if custo_pacote > 0 else 0
                qtd_real = int(orcamento_real // custo_pacote) if custo_pacote > 0 else 0

                st.caption(f"Custo Pacote: **R$ {custo_pacote:,.2f}**")
                
                # Cenário Real (Foco no que dá pra fazer agora)
                st.metric("Poder de Compra Real", f"{qtd_real} Pacotes", help="Baseado na sobra de caixa atual")
                if qtd_real > 0:
                    st.success(f"Dá pra comprar! Sobra: R$ {orcamento_real - (qtd_real*custo_pacote):.2f}")
                else:
                    st.warning("Sem caixa suficiente.")
            
            st.markdown("---")
            if st.button("💾 Salvar Fechamento", type="primary", width='stretch'):
                save_current_state()

    with tab_investimento:
        # Carrega dados
        df_portfolio, df_historico, df_cdi = load_investments_data()
        
        # Garante que a coluna nova exista se vier de um save antigo
        if "DY_Anual_Estimado" not in df_portfolio.columns:
            # Se tinha a coluna antiga, tenta migrar, senão zera
            if "DY_Mensal_Perc" in df_portfolio.columns:
                # Assume que o antigo mensal * 12 é o anual (estimativa grosseira para migração)
                df_portfolio["DY_Anual_Estimado"] = df_portfolio["DY_Mensal_Perc"] * 100 * 12
            else:
                df_portfolio["DY_Anual_Estimado"] = 0.0

        salario_atual = st.session_state.get("sal_prin", 1500.00) 
        if salario_atual == 0: salario_atual = 1500.00

        # ==========================================
        # SEÇÃO 1: INTELLIGENCE (CÁLCULOS CORRIGIDOS)
        # ==========================================
        st.markdown('<p class="main-header">Intelligence & Liberdade Financeira</p>', unsafe_allow_html=True)
        
        if not df_portfolio.empty:
            # LÓGICA CORRIGIDA:
            # Input do usuário: 12.00 (representa 12% ao ano)
            # Cálculo: (12 / 100) / 12 meses = Taxa Mensal Decimal
            
            df_portfolio["DY_Mensal_Real"] = (df_portfolio["DY_Anual_Estimado"] / 100) / 12
            df_portfolio["Renda_Mensal_Ativo"] = df_portfolio["Cotas"] * df_portfolio["Preco_Medio"] * df_portfolio["DY_Mensal_Real"]
            
            renda_mensal_total = df_portfolio["Renda_Mensal_Ativo"].sum()
            renda_anual_proj = renda_mensal_total * 12
            cobertura_custo = (renda_mensal_total / salario_atual) * 100

            # --- VISUALIZAÇÃO DOS KPI's ---
            col_bi_1, col_bi_2, col_bi_3, col_bi_4 = st.columns(4)
            col_bi_1.metric("Renda Mensal (Estimada)", f"R$ {renda_mensal_total:.2f}", help="Baseada no DY Anual / 12")
            col_bi_2.metric("Renda Anual (Proj.)", f"R$ {renda_anual_proj:.2f}")
            col_bi_3.metric("Patrimônio FIIs", f"R$ {(df_portfolio['Cotas'] * df_portfolio['Preco_Medio']).sum():,.2f}")
            col_bi_4.metric("Liberdade Financeira", f"{cobertura_custo:.2f}%", help="% do seu salário coberto por FIIs")

            # --- GRÁFICOS ---
            c_chart1, c_chart2 = st.columns([2, 1])
            
            with c_chart1:
                with st.container(border=True):
                    st.caption("📈 Evolução da Renda Passiva (Simulação)")
                    if not df_historico.empty:
                        df_evolucao = df_historico.copy()
                        # Mapeia o DY Anual atual para o histórico
                        mapa_dy = dict(zip(df_portfolio["Ticker"], df_portfolio["DY_Anual_Estimado"]))
                        df_evolucao["DY_Ref_Anual"] = df_evolucao["Ticker"].map(mapa_dy).fillna(0)
                        
                        # Transforma em mensal decimal para o gráfico
                        df_evolucao["Renda_Adicionada"] = df_evolucao["Cotas"] * df_evolucao["Preco"] * ((df_evolucao["DY_Ref_Anual"]/100)/12)
                        
                        df_evolucao["Data"] = pd.to_datetime(df_evolucao["Data"])
                        df_evolucao = df_evolucao.sort_values("Data")
                        df_evolucao["Evolucao_Renda"] = df_evolucao["Renda_Adicionada"].cumsum()
                        
                        chart_line = alt.Chart(df_evolucao).mark_area(
                            line={'color':'darkgreen'},
                            color=alt.Gradient(gradient='linear', stops=[alt.GradientStop(color='white', offset=0), alt.GradientStop(color='darkgreen', offset=1)], x1=1, x2=1, y1=1, y2=0)
                        ).encode(
                            x='Data:T', y=alt.Y('Evolucao_Renda:Q', axis=alt.Axis(format='R$,.2f')), tooltip=['Data', 'Evolucao_Renda']
                        )
                        st.altair_chart(chart_line, width='stretch')
                    else:
                        st.info("Registre compras para ver o gráfico.")

            with c_chart2:
                with st.container(border=True):
                    st.caption("🍰 Diversificação")
                    if "Segmento" in df_portfolio.columns:
                        chart_pie = alt.Chart(df_portfolio).mark_arc(innerRadius=50).encode(
                            theta=alt.Theta(field="Renda_Mensal_Ativo", type="quantitative"),
                            color=alt.Color(field="Segmento", type="nominal"),
                            tooltip=["Ticker", "Renda_Mensal_Ativo"]
                        )
                        st.altair_chart(chart_pie, width='stretch')

            # --- TABELA DE PLANEJAMENTO ---
            with st.expander("🎯 VER PLANEJAMENTO (Magic Number & Cotas)", expanded=False):
                st.info(f"Meta: **R$ {salario_atual:,.2f}** (Salário Atual)")
                
                df_metas = df_portfolio.copy()
                # Renda por cota = Preço * (DY Anual / 100 / 12)
                df_metas["Renda_Unit"] = df_metas["Preco_Medio"] * df_metas["DY_Mensal_Real"]
                
                # Magic Number: Preço / Renda da Cota
                df_metas["Magic_Number"] = df_metas.apply(lambda x: int(x["Preco_Medio"] / x["Renda_Unit"]) if x["Renda_Unit"] > 0 else 0, axis=1)
                
                # Cotas Liberdade
                df_metas["Cotas_Liberdade"] = df_metas.apply(lambda x: int(salario_atual / x["Renda_Unit"]) if x["Renda_Unit"] > 0 else 0, axis=1)
                
                df_metas["Falta_Cotas"] = df_metas["Cotas_Liberdade"] - df_metas["Cotas"]
                df_metas["Investimento_Nec"] = df_metas["Falta_Cotas"] * df_metas["Preco_Medio"]
                
                st.dataframe(
                    df_metas[["Ticker", "Preco_Medio", "DY_Anual_Estimado", "Renda_Unit", "Cotas", "Magic_Number", "Falta_Cotas", "Investimento_Nec"]],
                    width='stretch',
                    column_config={
                        "Preco_Medio": st.column_config.NumberColumn("Preço Base", format="R$ %.2f"),
                        "DY_Anual_Estimado": st.column_config.NumberColumn("DY Anual", format="%.2f %%"),
                        "Renda_Unit": st.column_config.NumberColumn("Pag/Cota (Mês)", format="R$ %.2f"),
                        "Falta_Cotas": st.column_config.ProgressColumn("Falta Comprar", min_value=0, max_value=1000, format="%d"),
                        "Investimento_Nec": st.column_config.NumberColumn("Capital Nec.", format="R$ %.2f"),
                    }
                )

        st.divider()

        # ==========================================
        # SEÇÃO 2: GESTÃO (EDITOR CORRIGIDO)
        # ==========================================
        col_rv_1, col_rv_2 = st.columns([2, 1], gap="large")

        with col_rv_1:
            with st.container(border=True):
                st.markdown("#### 📂 Carteira (Edite o DY Aqui)")
                
                # AQUI ESTAVA O ERRO DO SPRINTF.
                # Mudamos o format para "%.2f" (número normal) e o título para "DY Anual (%)"
                # O usuário digita "12.5" para 12.5%
                
                edited_portfolio = st.data_editor(
                    df_portfolio,
                    num_rows="dynamic",
                    width='stretch',
                    key="editor_portfolio",
                    column_config={
                        "Ticker": st.column_config.TextColumn("Ativo", validate="^[A-Z0-9]+$"),
                        "Cotas": st.column_config.NumberColumn("Qtd.", format="%d"),
                        "Preco_Medio": st.column_config.NumberColumn("PM (R$)", format="R$ %.2f"),
                        
                        # CORREÇÃO CRÍTICA AQUI:
                        "DY_Anual_Estimado": st.column_config.NumberColumn(
                            "DY Anual (%)", 
                            help="Digite o valor anual (ex: 12 para 12%). O sistema divide por 12 automaticamente.",
                            min_value=0.0,
                            max_value=100.0,
                            step=0.1,
                            format="%.2f" # Formato numérico simples para evitar erro
                        ),
                        
                        "Segmento": st.column_config.SelectboxColumn("Tipo", options=["Papel", "Tijolo", "Fiagro", "Infra", "Ação"]),
                        # Esconde as colunas calculadas do editor
                        "DY_Mensal_Real": None,
                        "Renda_Mensal_Ativo": None
                    }
                )

        with col_rv_2:
            with st.container(border=True):
                st.markdown("#### 🛒 Nova Compra")
                
                with st.form("form_compra_fii"):
                    lista_tickers = edited_portfolio["Ticker"].unique().tolist() if not edited_portfolio.empty else []
                    ticker_input = st.selectbox("Ativo", options=lista_tickers + ["NOVO..."])
                    
                    if ticker_input == "NOVO...":
                        novo_ticker = st.text_input("Digite Código:").upper()
                        ativo_final = novo_ticker
                    else:
                        ativo_final = ticker_input

                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        data_compra = st.date_input("Data", value=datetime.now())
                        qtd_compra = st.number_input("Qtd", min_value=1, step=1)
                    with c_f2:
                        preco_compra = st.number_input("Preço", min_value=0.01, step=0.01, format="%.2f")
                        taxas = st.number_input("Taxas", min_value=0.0, step=0.01, format="%.2f")
                    
                    # Adicionei input de DY na compra para já cadastrar certo se for novo
                    dy_compra_input = st.number_input("DY Anual Atual (%)", value=10.0, step=0.5, help="Ex: 12.0")

                    if st.form_submit_button("Confirmar", type="primary"):
                        if not ativo_final:
                            st.error("Defina o Ticker")
                        else:
                            # 1. Histórico
                            nova_transacao = {
                                "Data": data_compra.strftime("%Y-%m-%d"),
                                "Ticker": ativo_final,
                                "Tipo": "Compra",
                                "Cotas": qtd_compra,
                                "Preco": preco_compra,
                                "Total": (qtd_compra * preco_compra) + taxas
                            }
                            df_historico = pd.concat([df_historico, pd.DataFrame([nova_transacao])], ignore_index=True)

                            # 2. Atualizar PM e DY na Carteira
                            if ativo_final in edited_portfolio["Ticker"].values:
                                idx = edited_portfolio.index[edited_portfolio["Ticker"] == ativo_final][0]
                                cotas_antigas = edited_portfolio.at[idx, "Cotas"]
                                pm_antigo = edited_portfolio.at[idx, "Preco_Medio"]
                                nova_qtd = cotas_antigas + qtd_compra
                                novo_pm = ((cotas_antigas * pm_antigo) + (qtd_compra * preco_compra)) / nova_qtd
                                
                                edited_portfolio.at[idx, "Cotas"] = nova_qtd
                                edited_portfolio.at[idx, "Preco_Medio"] = novo_pm
                                # Atualiza o DY também com o valor informado na compra (opcional, mas bom pra manter atualizado)
                                edited_portfolio.at[idx, "DY_Anual_Estimado"] = dy_compra_input
                            else:
                                novo_ativo = {
                                    "Ticker": ativo_final, 
                                    "Cotas": qtd_compra, 
                                    "Preco_Medio": preco_compra, 
                                    "DY_Anual_Estimado": dy_compra_input, 
                                    "Segmento": "Papel"
                                }
                                edited_portfolio = pd.concat([edited_portfolio, pd.DataFrame([novo_ativo])], ignore_index=True)
                            
                            # Salva limpando colunas calculadas
                            cols_to_save = ["Ticker", "Cotas", "Preco_Medio", "DY_Anual_Estimado", "Segmento"]
                            save_investments_data(edited_portfolio[cols_to_save], df_historico, df_cdi)
                            st.rerun()

        st.divider()

        # ==========================================
        # SEÇÃO 3: RENDA FIXA (CDI) - MANTIDA IGUAL
        # ==========================================
        st.markdown('<p class="main-header">Renda Fixa (Caixinhas CDI 1%)</p>', unsafe_allow_html=True)
        col_cdi_1, col_cdi_2 = st.columns([2, 1], gap="large")

        with col_cdi_1:
            with st.container(border=True):
                st.markdown("#### 📦 Suas Caixinhas")
                df_cdi_editado = st.data_editor(
                    df_cdi,
                    key="editor_cdi",
                    num_rows="dynamic",
                    width='stretch',
                    column_config={
                        "Nome_Caixa": st.column_config.TextColumn("Objetivo"),
                        "Saldo_Atual": st.column_config.NumberColumn("Saldo Atual", format="R$ %.2f", disabled=True),
                        "Ultima_Atualizacao": st.column_config.TextColumn("Data Base", disabled=True)
                    }
                )
                st.metric("Total em Caixa", f"R$ {df_cdi_editado['Saldo_Atual'].sum():,.2f}")

        with col_cdi_2:
            with st.container(border=True):
                st.markdown("#### ⚙️ Operações")
                with st.expander("💰 Novo Aporte", expanded=True):
                    with st.form("form_aporte_cdi"):
                        caixa_sel = st.selectbox("Destino", options=df_cdi_editado["Nome_Caixa"].unique())
                        valor_aporte = st.number_input("Valor", min_value=1.00, format="%.2f")
                        if st.form_submit_button("Aportar"):
                            if not df_cdi_editado.empty and caixa_sel:
                                idx = df_cdi_editado.index[df_cdi_editado["Nome_Caixa"] == caixa_sel][0]
                                df_cdi_editado.at[idx, "Saldo_Atual"] += valor_aporte
                                save_investments_data(edited_portfolio, df_historico, df_cdi_editado)
                                st.rerun()
                
                with st.expander("📈 Virar o Mês (Juros)", expanded=False):
                    st.warning("Isso aplicará 1% em todas as caixas.")
                    if st.button("Aplicar 1% Agora"):
                        df_cdi_editado["Saldo_Atual"] = df_cdi_editado["Saldo_Atual"] * 1.01
                        df_cdi_editado["Ultima_Atualizacao"] = datetime.now().strftime("%Y-%m-%d")
                        save_investments_data(edited_portfolio, df_historico, df_cdi_editado)
                        st.success("Juros Aplicados!")
                        time.sleep(1)
                        st.rerun()

    with tab_cartao:
        df_parcelas = load_parcelas_data()

        # --- CONFIGURAÇÃO DE FECHAMENTO (Personalize aqui seus dias) ---
        # Se o dia da compra for MAIOR que o fechamento, joga para o mês seguinte.
        CONFIG_FECHAMENTOS = {
            "Nubank": 2,
            "Itaú": 1,
            "Mercado Pago": 5,
            "Banco Pan": 26
        }

        # --- FUNÇÃO AUXILIAR DE CÁLCULO DE PARCELAS ---
        def calcular_status_parcelas(data_compra, dia_fechamento, qtd_vezes):
            hoje = datetime.now().date()
            
            # Lógica: Se comprou DEPOIS do fechamento, a 1ª parcela é no mês seguinte
            # Se comprou ANTES, a 1ª parcela é no próprio mês
            if data_compra.day >= dia_fechamento:
                mes_inicio = data_compra.month + 1
                ano_inicio = data_compra.year
                if mes_inicio > 12:
                    mes_inicio = 1
                    ano_inicio += 1
            else:
                mes_inicio = data_compra.month
                ano_inicio = data_compra.year

            # Cria a data de referência da 1ª fatura (Dia do fechamento do mês de cobrança)
            # Usamos o dia do fechamento como "data de corte" para contar se pagou ou não
            try:
                data_primeira_fatura = datetime(ano_inicio, mes_inicio, dia_fechamento).date()
            except ValueError:
                # Tratamento para dias inválidos (ex: dia 30 em fevereiro), joga pro dia 1 do próximo
                if mes_inicio == 12:
                    data_primeira_fatura = datetime(ano_inicio + 1, 1, 1).date()
                else:
                    data_primeira_fatura = datetime(ano_inicio, mes_inicio + 1, 1).date()

            # Loop para contar quantas faturas já venceram até hoje
            pagas = 0
            
            # Percorre cada parcela prevista
            for i in range(qtd_vezes):
                # Calcula a data dessa parcela específica
                mes_atual = mes_inicio + i
                ano_atual = ano_inicio + (mes_atual - 1) // 12
                mes_atual = (mes_atual - 1) % 12 + 1
                
                try:
                    data_fatura_atual = datetime(ano_atual, mes_atual, dia_fechamento).date()
                except:
                    # Fallback simples para fim de mês
                    data_fatura_atual = datetime(ano_atual, mes_atual, 28).date()
                
                # Se a data dessa fatura for menor ou igual a hoje, considera paga
                if data_fatura_atual <= hoje:
                    pagas += 1
                else:
                    break # Se essa não venceu, as próximas também não
            
            restantes = qtd_vezes - pagas
            return pagas, restantes


        # --- CALLBACK ATUALIZADO ---
        def callback_registrar_compra():
            descricao = st.session_state.novo_gasto_desc
            qtd_parcelas = st.session_state.novo_gasto_qtd
            valor_total = st.session_state.novo_gasto_valor
            cartao_sel = st.session_state.novo_gasto_cartao
            data_compra = st.session_state.novo_gasto_data
            
            if not descricao:
                st.error("Descreva o gasto.")
                return

            valor_parcela = valor_total / qtd_parcelas if qtd_parcelas > 0 else 0
            
            # Recupera dia de fechamento
            dia_fechamento = CONFIG_FECHAMENTOS.get(cartao_sel, 1) # Default dia 1 se não achar
            
            # --- CÁLCULO INTELIGENTE DAS PAGAS ---
            pagas_calc, restantes_calc = calcular_status_parcelas(data_compra, dia_fechamento, qtd_parcelas)
            
            # Calcula valor faltante real
            faltam_reais = valor_total - (pagas_calc * valor_parcela)
            if faltam_reais < 0: faltam_reais = 0 # Segurança

            df_atual = load_parcelas_data()
            
            nova_parcela = {
                "O Quê": descricao,
                "Vezes": qtd_parcelas,
                "Valor": valor_parcela,
                "Pagas": pagas_calc,         # Agora calculado dinamicamente
                "Restantes": restantes_calc, # Agora calculado dinamicamente
                "Faltam": faltam_reais,
                "Cartão": cartao_sel,
                "Data_Compra": data_compra.strftime("%Y-%m-%d")
            }
            
            df_atual = pd.concat([df_atual, pd.DataFrame([nova_parcela])], ignore_index=True)
            try:
                conexoes.save_gsheet("Parcelas", df_atual)
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

            # ATUALIZAÇÃO DO SALDO MENSAL (Session State)
            # Nota: Só somamos ao input mensal SE tiver alguma parcela ativa pagável HOJE.
            # Mas para simplificar a visão geral, mantemos a lógica de somar a parcela do mês se houver.
            mapa_keys = {"Nubank": "input_nu", "Itaú": "input_itau", "Mercado Pago": "input_mp", "Banco Pan": "input_pan"}
            key_alvo = mapa_keys.get(cartao_sel)
            
            # Se ainda tem parcelas a pagar ou se pagou a última este mês, impacta o fluxo
            if restantes_calc > 0 or pagas_calc == qtd_parcelas:
                 valor_antigo = st.session_state.get(key_alvo, 0.0)
                 st.session_state[key_alvo] = valor_antigo + valor_parcela
                 save_current_state()
            
            st.toast(f"Compra registrada! {pagas_calc} parcelas já consideradas pagas.", icon="✅")

        # --- FORMULÁRIO ---
        with st.container(border=True):
            st.markdown('<p class="main-header">Registrar Compra no Cartão</p>', unsafe_allow_html=True)
            
            with st.form("form_gasto_cartao"):
                col_c1, col_c2 = st.columns(2)
                
                with col_c1:
                    # Adicionei help para explicar a lógica nova
                    st.date_input("Data da Compra", value=datetime.now(), key="novo_gasto_data", help="Se a data for antiga, o sistema calculará quantas parcelas já foram pagas.")
                    c_sel = st.selectbox("Cartão", list(CONFIG_FECHAMENTOS.keys()), key="novo_gasto_cartao")
                    st.text_input("Descrição", placeholder="Ex: IPhone 15", key="novo_gasto_desc")
                    
                    # Mostra o dia de fechamento configurado para feedback
                    dia_f = CONFIG_FECHAMENTOS.get(st.session_state.get("novo_gasto_cartao", "Nubank"), 1)
                    st.caption(f"📅 Fechamento do {c_sel}: Dia {dia_f}")
                
                with col_c2:
                    v_total = st.number_input("Valor TOTAL", min_value=0.01, step=10.00, format="%.2f", key="novo_gasto_valor")
                    q_parcelas = st.number_input("Qtd Parcelas", min_value=1, step=1, value=1, key="novo_gasto_qtd")
                
                v_parcela = v_total / q_parcelas if q_parcelas > 0 else 0
                st.caption(f"Parcela: **R$ {v_parcela:,.2f}**")

                st.form_submit_button("Registrar Despesa", type="primary", on_click=callback_registrar_compra)

        st.divider()

        # --- VISUALIZAÇÃO ---
        with st.container(border=True):
            st.markdown('<p class="main-header">Histórico de Lançamentos</p>', unsafe_allow_html=True)
            if not df_parcelas.empty:
                # Adicionei colunas de status para você ver a mágica acontecendo
                df_view = df_parcelas.tail(10).copy()
                df_view = df_view[["Data_Compra", "Cartão", "O Quê", "Valor", "Pagas", "Vezes", "Faltam"]]
                st.dataframe(
                    df_view,
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "Pagas": st.column_config.NumberColumn("Pagas", format="%d"),
                        "Faltam": st.column_config.NumberColumn("Saldo Devedor", format="R$ %.2f")
                    }
                )
            else:
                st.info("Nenhuma compra registrada.")

    with tab_futuro:
        # Carrega dados necessários
        salario = st.session_state.get("sal_prin", 2466.00)
        div_atual = st.session_state.get("div", 0.0)
        
        # Recupera Pesos
        pesos = {
            "p_fii": st.session_state.get("p_fii", 0.25),
            "p_cdi": st.session_state.get("p_cdi", 0.25)
        }

        # Dados Reais
        df_parcelas = load_parcelas_data()
        df_finan = load_financiamentos_data()
        df_portfolio, _, df_cdi = load_investments_data() # Carrega CDI e Portfólio
        
        # Cálculos de Base para Projeção
        saldo_cdi_atual = df_cdi["Saldo_Atual"].sum() if not df_cdi.empty else 0.0
        
        # Calcula DY Médio Ponderado da Carteira (Mensal)
        dy_medio_mensal = 0.008 # Valor padrão conservador (0.8% a.m.)
        if not df_portfolio.empty and "DY_Mensal_Real" in df_portfolio.columns:
            # Weighted Average
            investido = df_portfolio["Cotas"] * df_portfolio["Preco_Medio"]
            total_inv = investido.sum()
            if total_inv > 0:
                dy_medio_mensal = (investido * df_portfolio["DY_Mensal_Real"]).sum() / total_inv

        CONFIG_FECHAMENTOS = {"Nubank": 2, "Itaú": 1, "Mercado Pago": 5, "Banco Pan": 26}

        col_fut1, col_fut2 = st.columns([1, 3], gap="large")

        # --- ESQUERDA: PARÂMETROS ---
        with col_fut1:
            with st.container(border=True):
                st.markdown('<p class="main-header">Parâmetros Futuros</p>', unsafe_allow_html=True)
                teto_cdi = st.number_input("Meta Teto Reserva (R$)", value=20000.0, step=1000.0)
                
                st.divider()
                st.markdown("#### 🔮 Simulador")
                sim_desc = st.text_input("O que?", placeholder="Ex: Passagem")
                sim_val = st.number_input("Valor Total", min_value=0.0, step=50.0)
                sim_vezes = st.number_input("Parcelas", min_value=1, value=1)
                sim_data = st.date_input("Data Compra", value=datetime.now())
                sim_cartao = st.selectbox("Cartão", list(CONFIG_FECHAMENTOS.keys()), key="sim_card_fut")

                dados_simulacao = None
                if sim_val > 0:
                    dados_simulacao = {"desc": sim_desc, "valor": sim_val, "vezes": int(sim_vezes), "data": sim_data, "cartao": sim_cartao}

        # --- 3. GERAÇÃO DA PROJEÇÃO (Crucial: Definir antes de usar col_fut2) ---
        df_proj = projetar_futuro(
            df_parcelas, df_finan, salario, div_atual, saldo_cdi_atual, 
            pesos, dy_medio_mensal, teto_cdi, 
            dados_simulacao, CONFIG_FECHAMENTOS
        )

        # --- DIREITA: PROJEÇÃO EVOLUTIVA ---
        with col_fut2:
            # Pega o último mês (Mês 12) para ver o resultado do efeito bola de neve
            mes_12 = df_proj.iloc[-1]
            crescimento_renda = mes_12["Dividendos Proj."] - div_atual
            
            with st.container(border=True):
                st.markdown(f"#### 🚀 Resultado em 12 Meses ({mes_12['Mês']})")
                k1, k2, k3, k4 = st.columns(4)
                
                k1.metric("Novo Dividendo", f"R$ {mes_12['Dividendos Proj.']:,.2f}", delta=f"+R$ {crescimento_renda:.2f}")
                k2.metric("Saldo CDI Projetado", f"R$ {mes_12['Saldo CDI (Juros)']:,.2f}", delta=f"{((mes_12['Saldo CDI (Juros)']/saldo_cdi_atual)-1)*100:.1f}%")
                
                # Barra de progresso do Teto da Reserva
                perc_teto = min(mes_12['Saldo CDI (Juros)'] / teto_cdi, 1.0)
                k3.progress(perc_teto, text=f"Meta Reserva: {perc_teto*100:.1f}%")
                k3.caption(f"Meta: R$ {teto_cdi:,.2f}")
                
                k4.metric("Status", mes_12["Status Reserva"])

            # GRÁFICO COMBINADO: PATRIMÔNIO CDI vs RENDA PASSIVA
            with st.container(border=True):
                st.markdown("#### 🌊 Evolução Patrimonial & Renda")
                
                base = alt.Chart(df_proj).encode(x=alt.X('Mês', sort=None))

                # Área CDI (Fundo)
                area_cdi = base.mark_area(color='#E3F2FD', opacity=0.5).encode(
                    y=alt.Y('Saldo CDI (Juros)', axis=alt.Axis(title='Saldo CDI (R$)')),
                    tooltip=['Mês', 'Saldo CDI (Juros)']
                )
                
                # Linha Teto (Meta)
                rule_teto = alt.Chart(pd.DataFrame({'y': [teto_cdi]})).mark_rule(color='red', strokeDash=[5, 5]).encode(y='y')

                # Linha Dividendos (Eixo da Direita - Usando dual axis gambiarra ou normalizando visualmente)
                # O Altair no Streamlit simplificado às vezes complica dual axis, vamos focar no crescimento da renda
                line_div = base.mark_line(color='#2E7D32', strokeWidth=3).encode(
                    y=alt.Y('Dividendos Proj.', axis=alt.Axis(title='Renda Passiva Mensal (R$)')),
                    tooltip=['Mês', 'Dividendos Proj.']
                )

                chart_dual = alt.layer(area_cdi + rule_teto, line_div).resolve_scale(y='independent')
                
                st.altair_chart(chart_dual, width='stretch')

            # TABELA FINANCEIRA
            with st.expander("Ver Planilha Financeira Projetada", expanded=False):
                st.dataframe(
                    df_proj[["Mês", "Entradas (Cresc.)", "Dividendos Proj.", "Gastos Cartão", "Aporte FII", "Aporte CDI", "Saldo CDI (Juros)"]],
                    width='stretch',
                    hide_index=True,
                    column_config={
                        "Entradas (Cresc.)": st.column_config.NumberColumn("Entradas", format="R$ %.2f"),
                        "Dividendos Proj.": st.column_config.NumberColumn("Renda Passiva", format="R$ %.2f"),
                        "Gastos Cartão": st.column_config.NumberColumn("Fatura", format="R$ %.2f"),
                        "Aporte FII": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Aporte CDI": st.column_config.NumberColumn(format="R$ %.2f"),
                        "Saldo CDI (Juros)": st.column_config.NumberColumn("Caixa Acum.", format="R$ %.2f"),
                    }
                )

    with tab_financiamento:
        df_finan = load_financiamentos_data()

        st.markdown('<p class="main-header">Gestão de Dívidas & Financiamentos</p>', unsafe_allow_html=True)

        col_fin1, col_fin2 = st.columns([1, 2], gap="large")

        # --- CADASTRO ---
        with col_fin1:
            with st.container(border=True):
                st.markdown("#### 📝 Novo Contrato")
                with st.form("form_finan"):
                    tipo = st.selectbox("Tipo", ["Carro", "Moto", "Casa", "Empréstimo Pessoal", "Parcelamento Fatura (Futuro)"])
                    nome = st.text_input("Descrição", placeholder="Ex: Finan. HB20")
                    val_emp = st.number_input("Valor Emprestado (Principal)", min_value=0.0, step=100.0)
                    val_parc = st.number_input("Valor Parcela", min_value=0.0, step=10.0)
                    qtd = st.number_input("Qtd Parcelas", min_value=1, step=1)
                    inicio = st.date_input("Data Início", value=datetime.now())

                    if st.form_submit_button("Registrar Financiamento", type="primary"):
                        if val_parc > 0 and qtd > 0:
                            novo_finan = {
                                "Nome": nome, "Tipo": tipo,
                                "Valor_Emprestado": val_emp,
                                "Valor_Parcela": val_parc,
                                "Qtd_Total": qtd,
                                "Qtd_Pagas": 0,
                                "Data_Inicio": inicio.strftime("%Y-%m-%d")
                            }
                            df_finan = pd.concat([df_finan, pd.DataFrame([novo_finan])], ignore_index=True)
                            save_financiamentos_data(df_finan)
                            st.rerun()
                        else:
                            st.error("Valores inválidos.")

            # Placeholder para Parcelamento de Fatura
            if tipo == "Parcelamento Fatura (Futuro)":
                st.info("💡 Futuramente: Integração automática com a aba Cartões para converter dívida de cartão em financiamento fixo.")

        # --- GESTÃO E AMORTIZAÇÃO ---
        with col_fin2:
            if not df_finan.empty:
                # Seleção para detalhar
                opcoes = df_finan["Nome"].unique()
                selecionado = st.selectbox("Selecione o contrato para simular:", options=opcoes)
                
                # Pega dados do contrato selecionado
                idx = df_finan.index[df_finan["Nome"] == selecionado][0]
                row = df_finan.loc[idx]
                
                # Cálculos de Juros
                total_a_pagar = row["Valor_Parcela"] * row["Qtd_Total"]
                total_juros = total_a_pagar - row["Valor_Emprestado"]
                juros_por_parcela = total_juros / row["Qtd_Total"] if row["Qtd_Total"] > 0 else 0
                
                # Exibição do Card
                with st.container(border=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Parcela Atual", f"R$ {row['Valor_Parcela']:,.2f}")
                    c2.metric("Progresso", f"{row['Qtd_Pagas']}/{row['Qtd_Total']}", help="Parcelas Pagas")
                    c3.metric("Juros Embutido/Mês", f"R$ {juros_por_parcela:,.2f}", help="Estimativa Linear (Total Pago - Principal)/Meses")
                    
                    st.progress(row['Qtd_Pagas']/row['Qtd_Total'], text="Evolução do Pagamento")

                    st.divider()
                    st.markdown("#### 📉 Simulador de Amortização")
                    st.caption("Ao antecipar, você deixa de pagar os juros daquele período. (Simulação baseada em juros médios lineares).")

                    col_sim1, col_sim2 = st.columns(2)
                    
                    with col_sim1:
                        st.info("**Pagar a Próxima (Normal)**")
                        st.markdown(f"Valor: **R$ {row['Valor_Parcela']:,.2f}**")
                        st.caption("Reduz 1 mês do prazo, paga juros cheios.")
                        if st.button("Registrar Pagamento Mensal"):
                             df_finan.at[idx, "Qtd_Pagas"] += 1
                             save_financiamentos_data(df_finan)
                             st.rerun()

                    with col_sim2:
                        st.success("**Antecipar a Última (Amortizar)**")
                        valor_com_desconto = row["Valor_Parcela"] - juros_por_parcela
                        desconto_real = row["Valor_Parcela"] - valor_com_desconto
                        
                        st.markdown(f"Valor Estimado: **R$ {valor_com_desconto:,.2f}**")
                        st.markdown(f"📉 Desconto: **R$ {desconto_real:,.2f}**")
                        
                        if st.button("Amortizar 1 Parcela (Fim da Fila)"):
                            df_finan.at[idx, "Qtd_Pagas"] += 1
                            # Nota: Não alteramos o valor da parcela no banco, pois é contrato fixo,
                            # mas registramos que uma parcela foi eliminada pagando menos.
                            save_financiamentos_data(df_finan)
                            st.toast(f"Amortizado! Economia de R$ {desconto_real:.2f}", icon="🤑")
                            st.rerun()
            else:
                st.info("Nenhum financiamento ativo.")

    with tab_sonho:
        with st.container(border=True):
            st.markdown('<p class="main-header">Sonhos e Metas</p>', unsafe_allow_html=True)
            
            # Ajuste nas opções e rótulos
            choice = st.radio("Simular por:", ["Salário", "Valor do Carro"], horizontal=True)
            
            if choice == "Salário":
                salario = st.number_input("Digite o Salário Desejado (R$):", min_value=0.0, step=100.0, value=2500.0)
            else:
                carro_input = st.number_input("Digite o Valor do Carro (FIPE):", min_value=0.0, step=1000.0, value=20000.0)
                # Engenharia Reversa: Salário necessário para manter esse carro (1.5% FIPE = 10% Salário)
                salario = (carro_input * 0.015) / 0.10

            # Pesos das Metas
            pesos = {
                "FIIs": 0.32,
                "CDI": 0.18,
                "Lazer": 0.20,
                "Casa": 0.15,
                "Carro": 0.10,
                "Vida": 0.05
            }

            fiis_dy = {
                "AAZQ": 0.1551,
                "VGIR": 0.1517,
                "VRTM": 0.1479,
                "SNAG": 0.1270,
                "MXRF": 0.1230
            }

            media_dy = sum(i for i in fiis_dy.values())/len(fiis_dy)

            sonho_c1, sonho_c2 = st.columns(2)
            
            with sonho_c1:
                with st.container(border=True):
                    st.write("**Distribuição da Meta de Renda**")

                    with st.container(border=True):
                        st.write(f"Salário: R$**{salario:,.2f}**")

                    c_a1, c_a2 = st.columns([1, 1])
                    
                    for cat, peso in pesos.items():
                        with c_a1:
                            st.caption(f"{cat} ({peso*100:.0f}%)")
                        with c_a2:
                            st.markdown(f"R$ {salario * peso:,.2f}")

                st.divider()
                valor_carro = (salario * pesos["Carro"]) / 0.015
                
                c_sv1, c_sv2 = st.columns([1, 1])
                with c_sv1:
                    # Correção da vírgula e dois pontos na formatação
                    st.metric("Manutenção Mensal (Alocado)", f"R$ {salario * pesos['Carro']:,.2f}")
                with c_sv2:
                    st.metric("Tabela FIPE Máxima", f"R$ {valor_carro:,.2f}")
            
            with sonho_c2:
                with st.container(border=True):
                    st.subheader("📊 Investimentos", divider="gray")

                    @st.cache_data(ttl=86400) # Cache de 24h
                    def get_ipca_recente():
                        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/12?formato=json"
                        response = requests.get(url)
                        data = response.json()
                        df_ipca = pd.DataFrame(data)
                        # i_mensal = valor / 100
                        return pd.to_numeric(df_ipca['valor']).mean() / 100
                    
                    # Cálculos
                    aporte_financeiro = salario * pesos["FIIs"]
                    num_cotas = int(aporte_financeiro / custo_pacote)
                    dividendos_estimados = (media_dy / 12) * (num_cotas * custo_pacote)

                    i = get_ipca_recente()

                    dividendos_necessarios_inflacao = (i / (1 + i))*salario
                    compra_ideal_inflac = dividendos_necessarios_inflacao / (media_dy/12)
                    peso_ideal = compra_ideal_inflac / salario

                    # Layout de métricas
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Aporte", f"R$ {aporte_financeiro:,.2f}")
                    m2.metric("Cotas", f"{num_cotas} un")
                    m3.metric("Renda Mensal", f"R$ {dividendos_estimados:,.2f}", delta_color="normal")
                    m3.metric("Parcela da Renda", f"{(dividendos_estimados/salario):,.2%}", delta_color="normal")
                    m4.metric("Renda Necessária", f"R$ {dividendos_necessarios_inflacao:,.2f}", delta_color="normal")
                    m4.metric("Peso Ideal", f"{(peso_ideal):,.2%}", delta_color="normal")

                with st.container(border=True):
                    st.subheader("Reserva de Emergência", divider="gray")
                    reserva_emergencia = salario * 6
                    tempo_para_meta = math.log((reserva_emergencia * 0.012 / (salario * pesos["CDI"])) + 1) / math.log(1 + 0.012)

                    mr1, mr2 = st.columns(2)
                    mr1.metric("Reserva Ideal", f"R$ {reserva_emergencia:,.2f}", delta_color="normal")
                    mr2.metric("Tempo para Reserva", f"{tempo_para_meta:,.0f} meses", delta_color="normal")

        renda_passiva, desvalorizacao = st.columns(2)

        with renda_passiva:
            with st.container(border=True):
                st.markdown('<p class="main-header">Renda Passiva</p>', unsafe_allow_html=True)

                renda_desejada = st.number_input(label="Renda Desejada", step=0.01)

                taxa_mensal = media_dy / 12
                valor_total_necessario = renda_desejada / taxa_mensal
                st.metric("Patrimônio Necessário", f"R$ {valor_total_necessario:,.2f}")

                choice = st.radio("Simular por:", ["Tempo Investindo", "Aporte Mensal"], horizontal=True)

                if choice == "Tempo Investindo":
                    anos = st.number_input("Anos Investindo", min_value=1, step=1, value=10)
                    investimento_mensal = valor_total_necessario / (anos * 12)
                    st.write(f"Aportes mensais de: **R$ {investimento_mensal:,.2f}**")
                    
                else:
                    valor_aporte = st.number_input("Aporte Mensal", min_value=0.01, value=500.0, step=0.01)
                    meses_totais = valor_total_necessario / valor_aporte

                    if meses_totais >= 12:
                        anos_f = meses_totais // 12
                        meses_f = meses_totais % 12
                        st.write(f"Tempo: **{anos_f:.0f} anos e {meses_f:.0f} meses**")
                    else:
                        st.write(f"Tempo: **{meses_totais:.0f} meses**")

        with desvalorizacao:
                @st.cache_data(ttl=86400) # Cache de 24h
                def get_ipca_recente():
                    url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/12?formato=json"
                    response = requests.get(url)
                    data = response.json()
                    df_ipca = pd.DataFrame(data)
                    # i_mensal = valor / 100
                    return pd.to_numeric(df_ipca['valor']).mean() / 100

                # Cálculos de Engenharia Financeira
                i_mensal_real = get_ipca_recente()
                data_final = datetime(2027, 9, 1)
                meses_faltantes = (data_final.year - datetime.today().year) * 12 + (data_final.month - datetime.today().month)
                fator_acumulado = (1 + i_mensal_real)**meses_faltantes
                salario_real_futuro = salario / fator_acumulado
                dividendos_necessarios = (salario * fator_acumulado) - salario

                # --- UI DESIGN SYSTEM ---
                with desvalorizacao:
                    with st.container(border=True):
                        st.subheader("🛡️ Proteção de Capital", divider="orange")
                        
                        # 1. KPIs Principais (Visão Macro)
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Poder de Compra (Set/27)", f"R$ {salario_real_futuro:,.2f}", 
                                    help="Valor do seu salário atual corrigido pela inflação projetada.")
                        with col2:
                            st.metric("Gap de Inflação", f"R$ {dividendos_necessarios:,.2f}", delta="- Perda de Poder", delta_color="inverse")

                        st.divider()

                        # 2. Status de Progresso (Visualização de Dados)
                        progresso = min(renda_proj / dividendos_necessarios, 1.0) # Cap em 100%
                        st.write(f"**Cobertura da Inflação:** {progresso:.2%}")
                        st.progress(progresso)

                        # 3. Plano de Ação (Cards de Detalhes)
                        with st.expander("Ver Detalhes do Cálculo e Aportes"):
                            c1, c2 = st.columns(2)
                            
                            dividendos_restantes = max(dividendos_necessarios - renda_proj, 0)
                            valor_investimento_total = dividendos_restantes / (media_dy/12)
                            aporte_mensal = valor_investimento_total / meses_faltantes
                            eq_renda = (aporte_mensal / salario)

                            c1.markdown(f"""
                            **Métricas de Mercado**
                            * Inflação Mensal (μ): `{i_mensal_real:.4%}`
                            * Taxa Anualizada: `{(1 + i_mensal_real)**12 - 1:.2%}`
                            * Meses até o alvo: `{meses_faltantes}`
                            """)
                            
                            c2.markdown(f"""
                            **Necessidade de Aporte**
                            * Aporte Mensal: `R$ {aporte_mensal:,.2f}`
                            * % do Salário: `{eq_renda:.2%}`
                            """)

                        # 4. Alerta de Engenharia
                        if eq_renda > 0.3:
                            st.error(f"⚠️ Atenção: O aporte necessário excede 30% da sua renda.")
                        else:
                            st.success("✅ Plano de proteção sustentável dentro da renda atual.")

        with st.expander("📅 Projeção Detalhada (Otimizada) - 60 Meses", expanded=False):
            # Parâmetros de Entrada
            taxa_aumento_salarial = 0.05  # 5% a.a.
            yield_fiis_mensal = media_dy / 12
            yield_cdi_mensal = 0.0085 # ~0.85% a.m. (100% CDI Liq)
            
            # Inicialização de Estado
            proj_dados = []
            salario_corrente = salario
            saldo_fiis = 0.0
            saldo_reserva = 0.0
            dividendos_anterior = 0.0
            
            # Loop de Simulação Discreta
            for mes in range(1, 61):
                # 1. Reajuste Salarial Anual (Step Function)
                if mes > 1 and (mes - 1) % 12 == 0:
                    salario_corrente *= (1 + taxa_aumento_salarial)
                    
                # 2. Logic Gate: Saturação da Reserva
                target_reserva = salario_corrente * 6
                
                if saldo_reserva >= target_reserva:
                    # Redirecionamento de Fluxo (CDI -> FIIs)
                    alocacao_fiis = pesos["FIIs"] + pesos["CDI"]
                    alocacao_cdi = 0.0
                    status_reserva = "Otimizada (Full)"
                else:
                    # Acumulação Padrão
                    alocacao_fiis = pesos["FIIs"]
                    alocacao_cdi = pesos["CDI"]
                    status_reserva = "Em Construção"

                # 3. Execução dos Aportes
                aporte_fiis = (salario_corrente * alocacao_fiis) + dividendos_anterior
                aporte_reserva = salario_corrente * alocacao_cdi
                
                # 4. Evolução Patrimonial (Juros Compostos)
                saldo_fiis += aporte_fiis
                # Reserva rende mesmo se aporte for zero
                saldo_reserva = (saldo_reserva + aporte_reserva) * (1 + yield_cdi_mensal)
                
                # 5. Output de Renda Passiva (Para o próximo ciclo)
                dividendos_anterior = saldo_fiis * yield_fiis_mensal
                
                # 6. Gastos Operacionais (Indexados ao salário)
                gastos = {k: salario_corrente * v for k, v in pesos.items() if k not in ["FIIs", "CDI"]}

                proj_dados.append({
                    "Mês": mes,
                    "Salário Base": salario_corrente,
                    "Status Reserva": status_reserva,
                    "Aporte FIIs (+Div)": aporte_fiis,
                    "Patrimônio FIIs": saldo_fiis,
                    "Renda Passiva": dividendos_anterior,
                    "Saldo Reserva": saldo_reserva,
                    "Renda Total (Sal+Div)": salario_corrente + dividendos_anterior
                })

            # Renderização
            df_proj = pd.DataFrame(proj_dados)
            
            tabs = st.tabs([f"Ano {i+1}" for i in range(5)])
            cols_visualizacao = ["Mês", "Salário Base", "Status Reserva", "Aporte FIIs (+Div)", "Patrimônio FIIs", "Renda Passiva", "Saldo Reserva"]

            for i, t in enumerate(tabs):
                with t:
                    inicio = i * 12
                    fim = (i + 1) * 12
                    
                    st.dataframe(
                        df_proj.iloc[inicio:fim][cols_visualizacao].style.format({
                            "Salário Base": "R$ {:,.2f}",
                            "Aporte FIIs (+Div)": "R$ {:,.2f}",
                            "Patrimônio FIIs": "R$ {:,.2f}",
                            "Renda Passiva": "R$ {:,.2f}",
                            "Saldo Reserva": "R$ {:,.2f}"
                        }),
                        use_container_width=True,
                        hide_index=True
                    )

if __name__ == "__main__":
    render_page()