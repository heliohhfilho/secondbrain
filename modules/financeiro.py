import streamlit as st
import pandas as pd
from datetime import datetime
from modules import conexoes
import altair as alt
import time

st.set_page_config(layout="wide", page_title="Finance Dashboard")

# --- SCHEMAS DE DADOS ---
def get_portfolio_schema():
    return ["Ticker", "Cotas", "Preco_Medio", "DY_Anual_Estimado", "Segmento"]

def get_transacoes_schema():
    return ["Data", "Ticker", "Tipo", "Cotas", "Preco", "Total"]

def get_cdi_schema():
    return ["Nome_Caixa", "Saldo_Atual", "Ultima_Atualizacao"]

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
        "Peso_FII", "Peso_CDI", "Peso_Lazer", "Peso_Casa", "Peso_Vida",
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
        "Peso_Vida": st.session_state.get("p_vid", 0.0),
        
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

    df_portfolio, _, _ = load_investments_data()
    tab_visao_geral, tab_investimento, tab_cartao, tab_futuro, tab_financiamento = st.tabs(["Visão Geral", "Investimentos", "Cartões", "Futuro", "Financiamentos"])

    with tab_visao_geral:
        # CSS Customizado
        st.markdown("""
            <style>
            [data-testid="stMetricValue"] { font-size: 1.8rem; }
            .main-header { font-size: 1.2rem; font-weight: bold; margin-bottom: 15px; color: #1E88E5; border-bottom: 2px solid #f0f2f6; }
            </style>
        """, unsafe_allow_html=True)

        # Funções Auxiliares de UI
        def criar_linha_input(label, key, is_text=False):
            c1, c2 = st.columns([1, 1], vertical_alignment="center")
            with c1: st.markdown(f"**{label}**")
            with c2:
                if is_text: return st.text_input(label, label_visibility="collapsed", key=key)
                else: return st.number_input(label, label_visibility="collapsed", step=0.01, format="%.2f", key=key)

        def criar_linha_alocacao(label, key, default_val, salario):
            c1, c2, c3 = st.columns([2, 1.5, 1.5], vertical_alignment="center")
            with c1: st.markdown(f"**{label}**")
            with c3:
                peso = st.number_input(label=f"peso_{key}", label_visibility="collapsed", key=key, value=default_val, step=0.01, format="%.2f")
            with c2:
                valor_calculado = salario * peso
                st.markdown(f"<div style='background-color: #f0f2f6; padding: 5px; border-radius: 5px; text-align: center;'>R$ {valor_calculado:,.2f}</div>", unsafe_allow_html=True)
            return peso

        # --- LAYOUT PRINCIPAL ---
        col1, col2, col3 = st.columns([1.2, 2.2, 1.6], gap="large")

        with col1:
            with st.container(border=True):
                st.markdown('<p class="main-header">Entradas e Cartões</p>', unsafe_allow_html=True)
                salario = criar_linha_input("Salário", "sal_prin")

                st.caption("Gastos Por Cartão")
                banco_pan = criar_linha_input("Banco Pan", "input_pan")
                itau = criar_linha_input("Itaú", "input_itau")
                mercado_pago = criar_linha_input("Mercado Pago", "input_mp")
                nubank = criar_linha_input("Nubank", "input_nu")

                st.caption("Outros Gastos")
                desc_outros = criar_linha_input("Descrição", "d_out", is_text=True)
                valor_outros = criar_linha_input("Valor", "v_out")

            with st.container(border=True):
                st.markdown('<p class="main-header">Resumo Mensal</p>', unsafe_allow_html=True)
                cartoes_total = banco_pan + itau + mercado_pago + nubank
                total_geral = cartoes_total + valor_outros
                balanco = salario - total_geral
                st.metric("Total Gastos", f"R$ {total_geral:.2f}")
                st.metric("Balanço Final", f"R$ {balanco:.2f}", delta=f"{balanco:.2f}")

        with col2:
            with st.container(border=True):
                st.markdown('<p class="main-header">Gestão de Parcelas</p>', unsafe_allow_html=True)
                # Placeholder: Futuramente você pode carregar isso de uma aba "Parcelas"
                df_parcelas = pd.DataFrame([{"O Quê": "Lux Tour", "Vezes": "8", "Valor": 66.34, "Pagas": 2, "Cartão": "Banco Pan"}])
                st.data_editor(df_parcelas, num_rows="dynamic", use_container_width=True, key="editor_parcelas")

            with st.container(border=True):
                st.markdown('<p class="main-header">Alocação Ideal (Engineered)</p>', unsafe_allow_html=True)
                h1, h2, h3 = st.columns([2, 1.5, 1.5])
                h1.caption("Categoria")
                h2.caption("Valor Sugerido")
                h3.caption("Peso (%)")

                p_fii = criar_linha_alocacao("FII (Dividendos)", "p_fii", 0.25, salario)
                p_cdi = criar_linha_alocacao("CDI (Reserva)", "p_cdi", 0.25, salario)
                p_lazer = criar_linha_alocacao("Lazer", "p_laz", 0.20, salario)
                p_casa = criar_linha_alocacao("Casa", "p_cas", 0.15, salario)
                p_vida = criar_linha_alocacao("Custo de Vida", "p_vid", 0.15, salario)

        with col3:
            with st.container(border=True):
                st.markdown('<p class="main-header">Receitas Adicionais</p>', unsafe_allow_html=True)
                div = criar_linha_input("Dividendos", "div")
                free = criar_linha_input("Freelancer", "free")
                dt = criar_linha_input("Day Trade", "dt")
                pres = criar_linha_input("Presente", "pres")
                total_extra = div + free + dt + pres
                st.divider()
                st.metric("Total Extra", f"R$ {total_extra:.2f}")

            with st.container(border=True):
                st.markdown('<p class="main-header">Planejamento de Compra (Pacote FIIs)</p>', unsafe_allow_html=True)
                
                # 1. Definição do Custo do Pacote (Soma de 1 cota de cada ativo da carteira)
                custo_pacote = df_portfolio["Preco_Medio"].sum() if not df_portfolio.empty else 0.0
                
                # 2. Cenários
                orcamento_ideal = (salario * p_fii) + div
                orcamento_real = balanco # Balanço Final calculado anteriormente (Salario - Gastos)

                # Cálculo de Quantidade de Pacotes (Floor division)
                qtd_ideal = int(orcamento_ideal // custo_pacote) if custo_pacote > 0 else 0
                qtd_real = int(orcamento_real // custo_pacote) if custo_pacote > 0 else 0

                # --- VISUALIZAÇÃO ---
                st.caption(f"Custo para comprar 1 de cada ativo da carteira: **R$ {custo_pacote:,.2f}**")
                
                col_cen1, col_cen2 = st.columns(2)
                
                # Cenário A: Ideal (Baseado no Peso configurado)
                with col_cen1:
                    st.info(f"**Cenário Ideal (Peso {p_fii*100:.0f}%)**")
                    st.markdown(f"Disponível: R$ {orcamento_ideal:,.2f}")
                    st.metric("Pacotes Ideais", f"{qtd_ideal}", help=f"Quantas vezes você compra a carteira inteira com R$ {orcamento_ideal:.2f}")
                    st.caption(f"Sobra: R$ {orcamento_ideal - (qtd_ideal * custo_pacote):.2f}")

                # Cenário B: Real (Baseado no Balanço/Sobra)
                with col_cen2:
                    st.success("**Cenário Real (Sobra Caixa)**")
                    st.markdown(f"Disponível: R$ {orcamento_real:,.2f}")
                    st.metric("Pacotes Possíveis", f"{qtd_real}", help=f"Quantas vezes você compra a carteira inteira com o que sobrou (R$ {orcamento_real:.2f})")
                    if qtd_real >= 0:
                        st.caption(f"Sobra: R$ {orcamento_real - (qtd_real * custo_pacote):.2f}")
                    else:
                        st.error("Balanço Negativo")

                if custo_pacote == 0:
                    st.warning("Cadastre ativos na aba 'Investimentos' para calcular o pacote.")
            
            # --- BOTÃO DE AÇÃO ---
            st.markdown("---")
            # Usando callback ou verificação direta
            if st.button("💾 Salvar Registro no Database", type="primary", use_container_width=True):
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
                        st.altair_chart(chart_line, use_container_width=True)
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
                        st.altair_chart(chart_pie, use_container_width=True)

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
                    use_container_width=True,
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
                    use_container_width=True,
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
                    use_container_width=True,
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
        pass

if __name__ == "__main__":
    render_page()