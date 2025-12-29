import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import os

# --- CAMINHOS DOS DADOS ---
PATH_FIN_TRANS = os.path.join('data', 'fin_transacoes.csv')
PATH_FIN_INVEST = os.path.join('data', 'fin_investimentos.csv')
PATH_DAYTRADE = os.path.join('data', 'daytrade.csv')
PATH_PROD = os.path.join('data', 'log_produtividade.csv')
PATH_LEITURAS = os.path.join('data', 'leituras.csv')
PATH_VIAGENS = os.path.join('data', 'viagens.csv')
PATH_BIO = os.path.join('data', 'bio_data.csv')
PATH_ALMA = os.path.join('data', 'alma_log.csv')
PATH_FAC_CONFIG = os.path.join('data', 'fac_config.csv')
PATH_FAC_AVAL = os.path.join('data', 'fac_avaliacoes.csv')
PATH_CRM_DEALS = os.path.join('data', 'crm_deals.csv')
PATH_METAS = os.path.join('data', 'metas_okr.csv')
PATH_HOBBIES = os.path.join('data', 'hobbies_projetos.csv')
# Novos Caminhos Cognitivos
PATH_EISEN = os.path.join('data', 'eisenhower_tasks.csv')
PATH_DECISOES = os.path.join('data', 'decisoes_matrix.csv')
PATH_FEAR = os.path.join('data', 'fear_setting.csv')
PATH_MUSICA = os.path.join('data', 'musica_log.csv')
PATH_FILMES = os.path.join('data', 'filmes_watchlist')

# --- FUNÇÃO HELPER ---
def safe_load(path, cols):
    if os.path.exists(path):
        return pd.read_csv(path)
    return pd.DataFrame(columns=cols)

def load_all_data():
    # 1. Financeiro
    df_trans = safe_load(PATH_FIN_TRANS, ["Data", "Tipo", "Valor_Total", "Categoria"])
    df_invest = safe_load(PATH_FIN_INVEST, ["Total_Pago", "Qtd", "Preco_Unitario"])
    if "Preco_Unitario" not in df_invest.columns and "Preco_Medio" in df_invest.columns:
        df_invest.rename(columns={"Preco_Medio": "Preco_Unitario"}, inplace=True)
    if "Preco_Unitario" not in df_invest.columns: df_invest["Preco_Unitario"] = 0.0
        
    df_trade = safe_load(PATH_DAYTRADE, ["Data", "Lucro", "Banca_Final"])
    
    # 2. Produtividade & Leituras
    df_prod = safe_load(PATH_PROD, ["Data", "Tipo", "Valor", "Unidade"])
    df_read = safe_load(PATH_LEITURAS, ["Status", "Paginas_Lidas"])
    df_trip = safe_load(PATH_VIAGENS, ["Valor_Final_BRL", "Pago"])
    
    # 3. Bio-Data
    cols_bio = ["Data", "Peso_kg", "Gordura_Perc", "Sono_hrs", "Treino_Tipo", "Calorias_Ingeridas", "Objetivo_Tipo"]
    df_bio = safe_load(PATH_BIO, cols_bio)
    for col in cols_bio:
        if col not in df_bio.columns:
            if col == "Objetivo_Tipo": df_bio[col] = "Manter"
            elif col == "Treino_Tipo": df_bio[col] = "Descanso"
            else: df_bio[col] = 0.0

    # 4. Outros
    df_alma = safe_load(PATH_ALMA, ["Data", "Nivel_Paz_0_10", "Emocao_Dominante"])
    df_fac_conf = safe_load(PATH_FAC_CONFIG, ["Inicio", "Fim"])
    df_fac_aval = safe_load(PATH_FAC_AVAL, ["Materia", "Nome", "Data", "Concluido"])
    df_deals = safe_load(PATH_CRM_DEALS, ["Cliente", "Projeto", "Valor_Est", "Estagio", "Previsao_Fechamento"])
    df_metas = safe_load(PATH_METAS, ["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Deadline", "Progresso_Manual"])
    df_hobbies = safe_load(PATH_HOBBIES, ["Nome", "Categoria", "Status", "Progresso_Perc"])
    
    # 5. Cognitivo (Novo)
    df_eisen = safe_load(PATH_EISEN, ["Tarefa", "Importante", "Urgente", "Status"])
    df_decis = safe_load(PATH_DECISOES, ["Titulo", "Opcao"])
    df_fear = safe_load(PATH_FEAR, ["Medo_Acao", "Status"])
    
    return df_trans, df_invest, df_trade, df_prod, df_read, df_trip, df_bio, df_alma, df_fac_conf, df_fac_aval, df_deals, df_metas, df_hobbies, df_eisen, df_decis, df_fear

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
        df_trans, df_invest, df_trade, df_prod, df_read, df_trip, df_bio, df_alma, df_fac_conf, df_fac_aval, df_deals, df_metas, df_hobbies, df_eisen, df_decis, df_fear = load_all_data()
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

    # 6. RODAPÉ (Foco Específico) - Agora com 5 colunas
    st.subheader("🔍 Foco Específico & Cultura")
    kp1, kp2, kp3, kp4, kp5, kp6 = st.columns(6)
    
    with kp1:
        st.markdown(f"**📚 Leitura**: {lidos} Livros")
        st.progress(min(lidos/12, 1.0))
        
    with kp2:
        # Música (Novo)
        albuns_ouvidos = 0
        if os.path.exists(PATH_MUSICA):
            df_mus = pd.read_csv(PATH_MUSICA)
            albuns_ouvidos = len(df_mus)
        st.markdown(f"**🎧 Música**: {albuns_ouvidos} Álbuns")
        # Meta simbólica de 50 álbuns no ano
        st.progress(min(albuns_ouvidos/50, 1.0))

    with kp3:
        if not df_trip.empty and 'Pago' in df_trip.columns:
            falta = df_trip[df_trip['Pago'] == False]['Valor_Final_BRL'].sum()
            st.markdown(f"**✈️ Viagens**: -R$ {falta:,.0f}")
        else:
            st.markdown("**✈️ Viagens**: OK")
            
    with kp4:
        st.markdown(f"**🕊️ Alma**: {emocao_atual}")
        st.progress(paz_atual / 10)
        
    with kp5:
        if not df_fac_conf.empty:
            ini_sem = pd.to_datetime(df_fac_conf.iloc[0]['Inicio']).date()
            fim_sem = pd.to_datetime(df_fac_conf.iloc[0]['Fim']).date()
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

             # Pequeno hack se não tiver importado df_filmes na função principal ainda:

    with kp6:
        # Filmes (NOVO)
        filmes_vistos = 0
        if not df_hobbies.empty: # Ops, carregando de filmes
             # Pequeno hack se não tiver importado df_filmes na função principal ainda:
             if os.path.exists(PATH_FILMES):
                 df_f = pd.read_csv(PATH_FILMES)
                 filmes_vistos = len(df_f[df_f['Status'] == 'Assistido'])
        
        st.markdown(f"**🎬 Filmes**: {filmes_vistos}")
        # Meta de ver 1 filme por semana (52 no ano)
        st.progress(min(filmes_vistos/52, 1.0))