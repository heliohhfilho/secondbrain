import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os

from modules import conexoes

@st.cache_data(ttl=600)
def load_all_data():
    # 1. Financeiro & Trade
    df_trans = conexoes.load_gsheet("Transacoes", ["Data", "Tipo", "Valor_Total", "Categoria"])
    df_invest = conexoes.load_gsheet("Investimentos", ["Total_Pago", "Qtd", "Preco_Unitario"])
    df_trade = conexoes.load_gsheet("DayTrade", ["Data", "Lucro", "Banca_Final"])
    
    # 2. Produtividade & Cultura
    df_prod = conexoes.load_gsheet("Log_Produtividade", ["Data", "Tipo", "Valor", "Unidade"])
    df_read = conexoes.load_gsheet("Leituras", ["Status", "Paginas_Lidas"])
    df_musica = conexoes.load_gsheet("Musica", ["ID"])
    df_filmes = conexoes.load_gsheet("Filmes", ["Status"])
    
    # 3. Saúde & Alma
    df_bio = conexoes.load_gsheet("Bio", ["Data", "Peso_kg", "Gordura_Perc", "Sono_hrs", "Calorias_Ingeridas"])
    df_alma = conexoes.load_gsheet("Alma", ["Data", "Nivel_Paz_0_10", "Emocao_Dominante"])
    
    # 4. Projetos & Acadêmico & METAS SMART (ATUALIZADO)
    df_fac_conf = conexoes.load_gsheet("Fac_Config", ["Inicio", "Fim"])
    df_deals = conexoes.load_gsheet("CRM_Deals", ["Cliente", "Projeto", "Valor_Est", "Estagio"])
    
    # --- UPDATE AQUI: Novas colunas SMART ---
    df_metas = conexoes.load_gsheet("Metas", ["ID", "Titulo", "Motivo_R", "Meta_Valor", "Unidade", "Progresso_Atual", "Deadline_T", "Ano"])
    # ----------------------------------------
    
    df_hobbies = conexoes.load_gsheet("Hobbies", ["Nome", "Status", "Progresso_Perc"])
    
    # 5. Cognitivo
    df_eisen = conexoes.load_gsheet("Tarefas", ["Tarefa", "Prioridade", "Concluido"]) 
    df_fear = conexoes.load_gsheet("FearSetting", ["Medo_Acao", "Status"])

    # 6. Módulos Adicionais
    df_trip = conexoes.load_gsheet("Viagens_Fin", ["Viagem", "Valor_Final_BRL", "Pago"])
    df_proj = conexoes.load_gsheet("Projetos", ["ID", "Nome", "Status"])
    df_task = conexoes.load_gsheet("Tarefas_Projetos", ["Projeto_ID", "Status"])
    df_series = conexoes.load_gsheet("Series", ["Titulo", "Temporada", "Total_Episodios", "Eps_Assistidos", "Status", "Onde_Assistir"])
    
    return (df_trans, df_invest, df_trade, df_prod, df_read, df_bio, df_alma, 
            df_fac_conf, df_deals, df_metas, df_hobbies, df_eisen, df_fear, 
            df_musica, df_filmes, df_trip, df_proj, df_task, df_series)

def render_page():
    st.header("🚀 Mainframe: Life OS")
    st.caption(f"Resumo Executivo - {date.today().strftime('%d/%m/%Y')}")
    
    try:
        (df_trans, df_invest, df_trade, df_prod, df_read, df_bio, df_alma, 
        df_fac_conf, df_deals, df_metas, df_hobbies, df_eisen, df_fear, 
        df_musica, df_filmes, df_trip, df_proj, df_task, df_series) = load_all_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- PROCESSAMENTO COGNITIVO ---
    q1_count = 0
    fears_crushed = 0
    if not df_eisen.empty:
        q1_count = len(df_eisen[(df_eisen['Importante']==True) & (df_eisen['Urgente']==True) & (df_eisen['Status']=='Pendente')])
    if not df_fear.empty:
        fears_crushed = len(df_fear[df_fear['Status']=='Superado'])

    if q1_count > 0:
        st.error(f"🔥 **ATENÇÃO:** {q1_count} tarefas Q1 (Críticas) pendentes.")

    # --- PREPARAÇÃO DE DADOS ---
    # Investimentos
    total_inv = (df_invest['Qtd'] * df_invest['Preco_Unitario']).sum() if not df_invest.empty else 0
    lidos = len(df_read[df_read['Status'] == 'Concluído']) if not df_read.empty else 0
    
    # Bio
    peso_atual = 0; bf_atual = 0; sono_atual = 0; str_bio_delta = ""; nutri_val = 0
    if not df_bio.empty:
        df_bio['Data'] = pd.to_datetime(df_bio['Data'])
        df_bio_sorted = df_bio.sort_values("Data")
        last_bio = df_bio_sorted.iloc[-1]
        peso_atual = last_bio.get('Peso_kg', 0)
        bf_atual = last_bio.get('Gordura_Perc', 0)
        sono_atual = last_bio.get('Sono_hrs', 0)
        nutri_val = int(last_bio.get('Calorias_Ingeridas', 0))
        if len(df_bio) > 1:
             d = peso_atual - df_bio_sorted.iloc[-2]['Peso_kg']
             str_bio_delta = f"{d:+.1f} kg"

    # Trade
    trade_lucro_total = df_trade['Lucro'].sum() if not df_trade.empty else 0
    banca_trade = df_trade.iloc[-1]['Banca_Final'] if not df_trade.empty else 0
    
    # CRM
    fat = 0; pipeline_val = 0; deals_ativos = 0
    if not df_deals.empty:
        fat = df_deals[df_deals['Estagio'] == "5. Fechado (Ganho)"]['Valor_Est'].sum()
        ativos = df_deals[~df_deals['Estagio'].isin(["5. Fechado (Ganho)", "6. Perdido"])]
        pipeline_val = ativos['Valor_Est'].sum()
        deals_ativos = len(ativos)

    # Hobbies
    hobbies_ativos = 0; hobby_top = "Nenhum"
    if not df_hobbies.empty:
        hobbies_ativos = len(df_hobbies[df_hobbies['Status'] != "Concluído"])
        em_andamento = df_hobbies[df_hobbies['Status'] != "Concluído"].sort_values("Progresso_Perc", ascending=False)
        if not em_andamento.empty:
            hobby_top = f"{em_andamento.iloc[0]['Nome']}"

    # KPIs Financeiros
    net_worth = total_inv + (banca_trade * 5.80)
    hoje = date.today()
    
    # Produtividade Hoje
    horas_foco_hoje = 0; dias_produtivos = 0
    if not df_prod.empty:
        df_prod['Data'] = pd.to_datetime(df_prod['Data']).dt.date
        foco_hoje = df_prod[(df_prod['Data'] == hoje) & (df_prod['Unidade'] == 'Minutos')]['Valor'].sum()
        horas_foco_hoje = foco_hoje / 60
        dias_produtivos = df_prod['Data'].nunique()

    # Alma
    emocao_atual = "-"; paz_atual = 5
    if not df_alma.empty:
        last_alma = df_alma.sort_values("Data").iloc[-1]
        paz_atual = last_alma.get('Nivel_Paz_0_10', 5)
        emocao_atual = last_alma.get('Emocao_Dominante', "-")

    # Transações Mês
    mes_atual = hoje.month
    receita_mes = 0; gastos_mes = 0
    if not df_trans.empty:
        df_trans['Data'] = pd.to_datetime(df_trans['Data'], errors='coerce')
        df_m = df_trans[df_trans['Data'].dt.month == mes_atual]
        gastos_mes = df_m[df_m['Tipo'].isin(['Cartao', 'Despesa Fixa', 'Emprestimo'])]['Valor_Total'].sum()
        receita_mes = df_m[df_m['Tipo'] == 'Receita']['Valor_Total'].sum()
    
    trade_mes = 0
    if not df_trade.empty:
        df_trade['Data'] = pd.to_datetime(df_trade['Data'])
        trade_mes = df_trade[df_trade['Data'].dt.month == mes_atual]['Lucro'].sum() * 5.80

    savings_rate = ((receita_mes - abs(gastos_mes)) / receita_mes * 100) if receita_mes > 0 else 0

    # --- RENDERIZAR DASHBOARD ---
    
    # 1. BIG NUMBERS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💎 Net Worth", f"R$ {net_worth:,.2f}")
    c2.metric("💸 Lucro Trade (Mês)", f"R$ {trade_mes:,.2f}")
    c3.metric("🧠 Deep Work (Hoje)", f"{horas_foco_hoje:.1f}h")
    c4.metric("💰 Poupança (Mês)", f"{savings_rate:.1f}%")
    
    st.divider()
    
    # 2. SEÇÃO COGNITIVA & BUSINESS
    st.subheader("🧠 Processador Cognitivo")
    b1, b2, b3, b4 = st.columns(4)
    b1.metric("🌪️ Pipeline CRM", f"R$ {pipeline_val:,.2f}", f"{deals_ativos} deals")
    b2.metric("🛡️ Fear Setting", f"{fears_crushed} Superados" if fears_crushed > 0 else "Sem dados")
    b3.metric("🛠️ Maker Space", f"{hobbies_ativos} Projetos")
    b4.metric("🧶 Foco Atual", hobby_top)

    st.divider()

    # 3. ENGENHARIA DO CORPO
    st.subheader("🧬 Engenharia do Corpo")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Peso", f"{peso_atual:.2f} kg", str_bio_delta, delta_color="inverse")
    k2.metric("BF %", f"{bf_atual:.1f}%", f"{15.0 - bf_atual:+.1f}% (Meta 15%)")
    k3.metric("Sono", f"{sono_atual}h")
    
    tmb_est = 2000 
    saldo = nutri_val - (tmb_est * 1.3)
    cor_cal = "normal" if saldo < -200 else "inverse" if saldo > 100 else "off"
    k4.metric("Nutrição", f"{nutri_val} kcal", f"Saldo: {int(saldo)}", delta_color=cor_cal)

    st.divider()

    # 4. METAS SMART (NOVO BLOCO)
    st.subheader(f"🎯 Metas {hoje.year} (SMART)")
    
    if not df_metas.empty:
        # Tratamento de dados para o Dashboard
        df_metas["Ano"] = pd.to_numeric(df_metas["Ano"], errors='coerce').fillna(hoje.year).astype(int)
        
        # Filtra apenas metas do ano atual para o dashboard principal
        metas_ano = df_metas[df_metas['Ano'] == hoje.year]
        
        if metas_ano.empty:
             st.info(f"Nenhuma meta definida para {hoje.year}.")
        else:
            cols_metas = st.columns(3)
            for idx, row in metas_ano.iterrows():
                with cols_metas[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"**{row['Titulo']}**")
                        
                        # Dados Numéricos
                        atual = float(row['Progresso_Atual']) if pd.notnull(row['Progresso_Atual']) else 0.0
                        alvo = float(row['Meta_Valor']) if pd.notnull(row['Meta_Valor']) else 1.0
                        perc = min(100.0, (atual / alvo) * 100) if alvo > 0 else 0
                        
                        st.progress(perc / 100)
                        c_val, c_time = st.columns(2)
                        c_val.caption(f"{atual:,.0f}/{alvo:,.0f} {row['Unidade']}")
                        
                        # Cálculo de Dias Restantes
                        if pd.notnull(row['Deadline_T']):
                            try:
                                deadline = pd.to_datetime(row['Deadline_T']).date()
                                dias_rest = (deadline - hoje).days
                                cor_dias = "red" if dias_rest < 15 else "green"
                                c_time.markdown(f":{cor_dias}[**{dias_rest} dias**]")
                            except:
                                c_time.caption("Sem Data")
                        
                        # Exibe o "R" do SMART (Motivação)
                        if pd.notnull(row['Motivo_R']) and str(row['Motivo_R']).strip() != "":
                            st.info(f"💡 {row['Motivo_R']}")
    else:
        st.warning("⚠️ Base de Metas vazia.")

    st.divider()

    # 5. GRÁFICOS (RADAR & CAIXA)
    col_radar, col_evolucao = st.columns([1, 2])
    with col_radar:
        st.subheader("🕸️ Radar")
        score_fin = min(100, max(0, savings_rate * 2)) 
        score_int = min(100, dias_produtivos * 5)
        score_lazer = min(100, (hobbies_ativos * 20)) if hobbies_ativos > 0 else 20
        s_bf = 100 if bf_atual <= 15 else max(0, 100 - (bf_atual-15)*3)
        
        categories = ['Finanças', 'Intelecto', 'Maker/Lazer', 'Saúde', 'Carreira']
        values = [score_fin, score_int, score_lazer, s_bf, 50] # Carreira estático 50 por enquanto
        
        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(t=20, b=20, l=20, r=20), height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_evolucao:
        st.subheader("📈 Fluxo de Caixa")
        if not df_trans.empty:
            df_trans['Mes'] = df_trans['Data'].dt.strftime('%Y-%m')
            receitas = df_trans[df_trans['Tipo'] == 'Receita'].groupby('Mes')['Valor_Total'].sum()
            despesas = df_trans[df_trans['Tipo'].isin(['Cartao', 'Despesa Fixa', 'Emprestimo'])].groupby('Mes')['Valor_Total'].sum().abs()
            df_chart = pd.DataFrame({'Receitas': receitas, 'Despesas': despesas}).fillna(0)
            st.bar_chart(df_chart)

    # 6. RODAPÉ (Cultura)
    st.subheader("🔍 Foco Específico & Cultura")
    kp1, kp2, kp3, kp4, kp5, kp6, kp7 = st.columns(7)
    
    kp1.metric("📚 Leitura", f"{lidos}", "Livros")
    kp2.metric("🎧 Música", f"{len(df_musica) if not df_musica.empty else 0}", "Álbuns")
    
    divida_viagem = 0
    if not df_trip.empty:
        df_trip['Valor_Final_BRL'] = pd.to_numeric(df_trip['Valor_Final_BRL'], errors='coerce').fillna(0)
        df_trip['Pago'] = df_trip['Pago'].astype(str).str.upper() == "TRUE"
        divida_viagem = df_trip[df_trip['Pago'] == False]['Valor_Final_BRL'].sum()
    kp3.metric("✈️ Viagens", f"R$ {divida_viagem:,.0f}", "A Pagar", delta_color="inverse" if divida_viagem > 0 else "off")

    kp4.metric("🕊️ Alma", emocao_atual, f"Paz: {paz_atual}/10")
    
    # Facul
    status_fac = "-"
    if not df_fac_conf.empty:
        ini = pd.to_datetime(df_fac_conf.iloc[0]['Inicio']).date()
        fim = pd.to_datetime(df_fac_conf.iloc[0]['Fim']).date()
        if ini <= hoje <= fim:
            p = (hoje - ini).days / (fim - ini).days
            status_fac = f"{p*100:.0f}%"
        else: status_fac = "Férias"
    kp5.metric("🎓 Semestre", status_fac)

    kp6.metric("🎬 Filmes", f"{len(df_filmes[df_filmes['Status']=='Assistido']) if not df_filmes.empty else 0}")
    kp7.metric("📺 Séries", f"{len(df_series[df_series['Status']=='Assistindo']) if not df_series.empty else 0}", "Ativas")