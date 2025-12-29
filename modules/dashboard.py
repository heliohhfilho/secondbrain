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
    
    # 4. Projetos & Acadêmico
    df_fac_conf = conexoes.load_gsheet("Fac_Config", ["Inicio", "Fim"])
    df_deals = conexoes.load_gsheet("CRM_Deals", ["Cliente", "Projeto", "Valor_Est", "Estagio"])
    df_metas = conexoes.load_gsheet("Metas", ["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Deadline", "Progresso_Manual"])
    df_hobbies = conexoes.load_gsheet("Hobbies", ["Nome", "Status", "Progresso_Perc"])
    
    # 5. Cognitivo
    df_eisen = conexoes.load_gsheet("Tarefas", ["Tarefa", "Prioridade", "Concluido"]) # Vinculado ao To-Do
    df_fear = conexoes.load_gsheet("FearSetting", ["Medo_Acao", "Status"])

    # 6. Módulos que faltavam carregar para bater com o Return (Total 18)
    df_trip = conexoes.load_gsheet("Viagens_Fin", ["Viagem", "Valor_Final_BRL", "Pago"])
    df_proj = conexoes.load_gsheet("Projetos", ["ID", "Nome", "Status"])
    df_task = conexoes.load_gsheet("Tarefas_Projetos", ["Projeto_ID", "Status"])
    
    return (df_trans, df_invest, df_trade, df_prod, df_read, df_bio, df_alma, 
            df_fac_conf, df_deals, df_metas, df_hobbies, df_eisen, df_fear, 
            df_musica, df_filmes, df_trip, df_proj, df_task)

# --- CÁLCULO DE METAS ---
def calcular_progresso_meta(row, dados_externos):
    tipo = row['Tipo_Vinculo']
    meta = row['Meta_Valor']
    manual = row['Progresso_Manual']
    
    atual = 0.0
    if tipo == "Manual": atual = manual
    elif tipo == "💰 Investimento Total": atual = dados_externos.get('Investimento Total', 0)
    elif tipo == "📚 Livros Lidos": atual = dados_externos.get('Livros Lidos', 0)
    elif tipo == "⚖️ Peso (Emagrecer)": atual = dados_externos.get('Peso Atual', 0)
    elif tipo == "🧬 Gordura % (Baixar)": atual = dados_externos.get('BF Atual', 0)
    elif tipo == "📈 Lucro DayTrade ($)": atual = dados_externos.get('Lucro Trade', 0)
    elif tipo == "💼 Faturamento CRM": atual = dados_externos.get('Faturamento', 0)
    
    perc = 0.0
    if tipo in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]:
        if atual <= meta and atual > 0: perc = 100.0
        else: perc = 0.0 
    else:
        perc = (atual / meta * 100) if meta > 0 else 0
    
    return atual, min(100.0, max(0.0, perc))

def render_page():
    st.header("🚀 Mainframe: Life OS")
    st.caption(f"Resumo Executivo - {date.today().strftime('%d/%m/%Y')}")
    
    try:
        (df_trans, df_invest, df_trade, df_prod, df_read, df_bio, df_alma, 
        df_fac_conf, df_deals, df_metas, df_hobbies, df_eisen, df_fear, 
        df_musica, df_filmes, df_trip, df_proj, df_task) = load_all_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return

    # --- PROCESSAMENTO COGNITIVO (NOVO) ---
    q1_count = 0
    fears_crushed = 0
    decisions_made = 0
    
    if not df_eisen.empty:
        # Q1: Importante + Urgente + Pendente
        q1_count = len(df_eisen[(df_eisen['Importante']==True) & (df_eisen['Urgente']==True) & (df_eisen['Status']=='Pendente')])
    
    if not df_fear.empty:
        fears_crushed = len(df_fear[df_fear['Status']=='Superado'])
        
    if not df_decis.empty:
        decisions_made = df_decis['Titulo'].nunique()

    # --- ALERTAS DE AÇÃO (PRIORIDADE 0) ---
    if q1_count > 0:
        st.error(f"🔥 **ATENÇÃO:** Você tem **{q1_count}** tarefas urgentes e importantes (Q1) pendentes! Resolva isso antes de qualquer coisa.")

    # --- PREPARAÇÃO DE DADOS ---
    dados_externos = {}
    
    total_inv = (df_invest['Qtd'] * df_invest['Preco_Unitario']).sum() if not df_invest.empty else 0
    dados_externos['Investimento Total'] = total_inv
    lidos = len(df_read[df_read['Status'] == 'Concluído']) if not df_read.empty else 0
    dados_externos['Livros Lidos'] = lidos
    
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

    dados_externos['Peso Atual'] = peso_atual
    dados_externos['BF Atual'] = bf_atual
    dados_externos['Lucro Trade'] = df_trade['Lucro'].sum() if not df_trade.empty else 0
    
    fat = 0
    if not df_deals.empty:
        fat = df_deals[df_deals['Estagio'] == "5. Fechado (Ganho)"]['Valor_Est'].sum()
    dados_externos['Faturamento'] = fat

    # Hobbies
    hobbies_ativos = 0; hobby_top = "Nenhum"
    if not df_hobbies.empty:
        hobbies_ativos = len(df_hobbies[df_hobbies['Status'] != "Concluído"])
        em_andamento = df_hobbies[df_hobbies['Status'] != "Concluído"].sort_values("Progresso_Perc", ascending=False)
        if not em_andamento.empty:
            hobby_top = f"{em_andamento.iloc[0]['Nome']} ({em_andamento.iloc[0]['Progresso_Perc']}%)"

    # KPIs MACRO
    banca_trade = df_trade.iloc[-1]['Banca_Final'] if not df_trade.empty else 0
    net_worth = total_inv + (banca_trade * 5.80)
    
    hoje = date.today()
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
        
    # CRM
    pipeline_val = 0; deals_ativos = 0
    if not df_deals.empty:
        ativos = df_deals[~df_deals['Estagio'].isin(["5. Fechado (Ganho)", "6. Perdido"])]
        pipeline_val = ativos['Valor_Est'].sum()
        deals_ativos = len(ativos)

    # Financeiro
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

    # --- RENDERIZAR DASHBOARD ---
    
    # 1. BIG NUMBERS
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("💎 Net Worth", f"R$ {net_worth:,.2f}", help="Invest + Trade")
    delta_trade = "Risco Alto" if trade_mes < 0 else "No alvo"
    c2.metric("💸 Lucro Trade (Mês)", f"R$ {trade_mes:,.2f}", delta=delta_trade)
    c3.metric("🧠 Deep Work (Hoje)", f"{horas_foco_hoje:.1f}h", "Meta: 4h")
    savings_rate = ((receita_mes - abs(gastos_mes)) / receita_mes * 100) if receita_mes > 0 else 0
    c4.metric("💰 Poupança (Mês)", f"{savings_rate:.1f}%", "Meta: 30%")
    
    st.divider()
    
    # 2. SEÇÃO COGNITIVA & BUSINESS (ATUALIZADA)
    st.subheader("🧠 Processador Cognitivo & Business")
    b1, b2, b3, b4 = st.columns(4)
    
    # KPIs Híbridos (Mente + Negócios)
    b1.metric("🌪️ Pipeline", f"R$ {pipeline_val:,.2f}", f"{deals_ativos} deals")
    
    # KPI Cognitivo
    if fears_crushed > 0:
        b2.metric("🛡️ Fear Setting", f"{fears_crushed} Superados", "Destravar")
    else:
        b2.metric("🛡️ Fear Setting", "Sem dados", "Mapeie Medos")
        
    b3.metric("🛠️ Maker Space", f"{hobbies_ativos} Projetos", "Na bancada")
    b4.metric("🧶 Foco Atual", hobby_top)

    st.divider()

    # 3. ENGENHARIA DO CORPO
    st.subheader("🧬 Engenharia do Corpo")
    k1, k2, k3, k4 = st.columns(4)
    cor_peso = "inverse" if str_bio_delta.startswith("+") else "normal"
    k1.metric("Peso", f"{peso_atual} kg", str_bio_delta, delta_color=cor_peso)
    delta_bf = 15.0 - bf_atual 
    k2.metric("BF %", f"{bf_atual:.1f}%", f"{delta_bf:+.1f}% (Meta 15%)", delta_color="normal")
    cor_sono = "normal" if sono_atual >= 7 else "inverse"
    k3.metric("Sono", f"{sono_atual}h", delta_color=cor_sono)
    
    cal_msg = "Sem dados"; cor_cal = "off"
    tmb_est = 2000 
    saldo = nutri_val - (tmb_est * 1.3)
    if nutri_val > 0:
        if saldo < -200: cal_msg, cor_cal = f"Déficit ({int(saldo)})", "normal"
        elif saldo > 100: cal_msg, cor_cal = f"Superávit ({int(saldo)})", "inverse"
        else: cal_msg, cor_cal = "Manutenção", "off"
    k4.metric("Nutrição", f"{nutri_val} kcal", cal_msg, delta_color=cor_cal)

    st.divider()

    # 4. METAS
    if not df_metas.empty:
        st.subheader("🎯 Metas 2026 (OKRs)")
        cols_metas = st.columns(3)
        for idx, row in df_metas.iterrows():
            with cols_metas[idx % 3]:
                with st.container(border=True):
                    atual, perc = calcular_progresso_meta(row, dados_externos)
                    st.markdown(f"**{row['Titulo']}**")
                    if row['Tipo_Vinculo'] in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]:
                        delta = atual - row['Meta_Valor']
                        if delta <= 0:
                            st.write(f"✅ CONCLUÍDO! ({atual} {row['Unidade']})")
                            st.progress(1.0)
                        else:
                            st.write(f"Falta: {delta:.1f} {row['Unidade']}")
                            st.progress(0.0) 
                    else:
                        st.progress(perc / 100)
                        st.caption(f"{atual:,.0f} / {row['Meta_Valor']:,.0f} {row['Unidade']} ({perc:.0f}%)")
    else:
        st.info("💡 Cadastre suas Metas na aba 'Metas 2026'.")

    st.divider()

    # 5. GRÁFICOS
    col_radar, col_evolucao = st.columns([1, 2])
    with col_radar:
        st.subheader("🕸️ Radar")
        score_fin = min(100, max(0, savings_rate * 2)) 
        score_int = min(100, dias_produtivos * 5)
        score_carreira = 50 
        score_lazer = min(100, (hobbies_ativos * 20)) if hobbies_ativos > 0 else 20
        s_bf = 100 if bf_atual <= 15 else max(0, 100 - (bf_atual-15)*3)
        score_saude = s_bf 
        
        categories = ['Finanças', 'Intelecto', 'Carreira', 'Maker/Lazer', 'Saúde']
        values = [score_fin, score_int, score_carreira, score_lazer, score_saude]
        
        fig = go.Figure(data=go.Scatterpolar(r=values, theta=categories, fill='toself'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 100])), showlegend=False, margin=dict(l=20, r=20, t=20, b=20), height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_evolucao:
        st.subheader("📈 Caixa Anual")
        if not df_trans.empty:
            df_trans['Mes'] = df_trans['Data'].dt.strftime('%Y-%m')
            receitas = df_trans[df_trans['Tipo'] == 'Receita'].groupby('Mes')['Valor_Total'].sum()
            despesas = df_trans[df_trans['Tipo'].isin(['Cartao', 'Despesa Fixa', 'Emprestimo'])].groupby('Mes')['Valor_Total'].sum().abs()
            df_chart = pd.DataFrame({'Receitas': receitas, 'Despesas': despesas}).fillna(0)
            st.bar_chart(df_chart)

    # 6. RODAPÉ (Foco Específico)
    st.subheader("🔍 Foco Específico & Cultura")
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    
    with kp1:
        st.markdown(f"**📚 Leitura**: {lidos} Livros")
        st.progress(min(lidos/12, 1.0))
        
    with kp2:
        # Música (Já carregado de df_musica)
        albuns_ouvidos = len(df_musica) if not df_musica.empty else 0
        st.markdown(f"**🎧 Música**: {albuns_ouvidos} Álbuns")
        st.progress(min(albuns_ouvidos/50, 1.0)) # Meta 50

    with kp3:
        # Viagens (Calcula dívida de viagem se houver)
        if not df_trip.empty:
            # Saneamento rápido para garantir cálculo
            df_trip['Valor_Final_BRL'] = pd.to_numeric(df_trip['Valor_Final_BRL'], errors='coerce').fillna(0)
            df_trip['Pago'] = df_trip['Pago'].astype(str).str.upper() == "TRUE"
            
            falta = df_trip[df_trip['Pago'] == False]['Valor_Final_BRL'].sum()
            st.markdown(f"**✈️ Viagens**: -R$ {falta:,.0f}")
        else:
            st.markdown("**✈️ Viagens**: OK")
            
    with kp4:
        st.markdown(f"**🕊️ Alma**: {emocao_atual}")
        st.progress(paz_atual / 10)
        
    with kp5:
        # Faculdade (Status do Semestre)
        if not df_fac_conf.empty:
            ini_sem = pd.to_datetime(df_fac_conf.iloc[0]['Inicio']).date()
            fim_sem = pd.to_datetime(df_fac_conf.iloc[0]['Fim']).date()
            hoje = date.today()
            if ini_sem <= hoje <= fim_sem:
                total = (fim_sem - ini_sem).days
                passados = (hoje - ini_sem).days
                perc_sem = passados/total if total > 0 else 0
                st.markdown(f"**🎓 Semestre**: {perc_sem*100:.0f}%")
                st.progress(perc_sem)
            else:
                st.markdown("**🎓 Faculdade**: Férias")
        else:
            st.markdown("**🎓 Faculdade**: -")

    with kp6:
        # Filmes (Já carregado de df_filmes)
        filmes_vistos = 0
        if not df_filmes.empty:
            filmes_vistos = len(df_filmes[df_filmes['Status'] == 'Assistido'])
        
        st.markdown(f"**🎬 Filmes**: {filmes_vistos}")
        st.progress(min(filmes_vistos/52, 1.0)) # Meta 1 por semana