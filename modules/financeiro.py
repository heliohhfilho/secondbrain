import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import numpy as np

from modules import conexoes

DIA_FECHAMENTO_PADRAO = 5 

def load_data():
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    if not df_t.empty:
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Recorrente"] = df_t["Recorrente"].astype(str).str.upper() == "TRUE"
        # Garante coluna de cartão
        if "Cartao_Ref" not in df_t.columns: df_t["Cartao_Ref"] = ""
    
    # 2. Investimentos (Para Dividendos)
    cols_i = ["Ativo", "Tipo", "Qtd", "Preco_Unitario", "Total_Pago", "Data_Compra", "DY_Mensal", "Total_Atual"]
    df_i = conexoes.load_gsheet("Investimentos", cols_i)
    if not df_i.empty:
        cols_num = ["Qtd", "Preco_Unitario", "Total_Pago", "DY_Mensal", "Total_Atual"]
        for c in cols_num: df_i[c] = pd.to_numeric(df_i[c], errors='coerce').fillna(0.0)

    # 3. Empréstimos
    cols_l = ["ID", "Nome", "Valor_Original", "Valor_Parcela", "Parcelas_Totais", "Parcelas_Pagas", "Dia_Vencimento", "Status", "Data_Inicio"]
    df_l = conexoes.load_gsheet("Emprestimos", cols_l)
    if not df_l.empty:
        df_l["ID"] = pd.to_numeric(df_l["ID"], errors='coerce').fillna(0).astype(int)
        for c in ["Valor_Original", "Valor_Parcela", "Parcelas_Totais", "Parcelas_Pagas", "Dia_Vencimento"]:
            df_l[c] = pd.to_numeric(df_l[c], errors='coerce').fillna(0)

    # 4. Cartões
    df_c = conexoes.load_gsheet("Cartoes", ["ID", "Nome", "Dia_Fechamento"])

    return df_t, df_i, df_l, df_c

def save_data(df, aba):
    df_save = df.copy()
    for col in ["Data", "Data_Compra", "Data_Inicio"]:
        if col in df_save.columns: df_save[col] = df_save[col].astype(str)
    conexoes.save_gsheet(aba, df_save)

def get_proximo_vencimento(dia_vencimento):
    hoje = date.today()
    try: venc_este_mes = date(hoje.year, hoje.month, int(dia_vencimento))
    except ValueError: venc_este_mes = date(hoje.year, hoje.month, 28)
    if hoje > venc_este_mes: return venc_este_mes + relativedelta(months=1)
    return venc_este_mes

# --- CÁLCULO DE DIVIDENDOS (NOVA FUNÇÃO) ---
def get_dividendos_estimados(df_invest):
    if df_invest.empty: return 0.0
    # Fórmula: Qtd * Preço Médio * (DY / 100)
    # Assume-se que DY_Mensal está em porcentagem (ex: 0.8 para 0.8%)
    df_invest['Div_Mensal'] = df_invest['Qtd'] * df_invest['Preco_Unitario'] * (df_invest['DY_Mensal'] / 100)
    return df_invest['Div_Mensal'].sum()

# --- MOTOR DE PROJEÇÃO ---
def get_future_projection(df_trans, df_loans, df_cards, meses=12):
    hoje = date.today()
    projecao = []
    
    mapa_fechamento = {}
    if not df_cards.empty:
        for _, c in df_cards.iterrows():
            mapa_fechamento[c['Nome']] = int(c['Dia_Fechamento'])

    # 1. Cartões Parcelados
    for _, row in df_trans.iterrows():
        if row['Tipo'] == 'Cartao' and row['Qtd_Parcelas'] > 1:
            try:
                data_compra = pd.to_datetime(row['Data']).date()
                parcelas = int(row['Qtd_Parcelas'])
                val_parc = float(row['Valor_Total']) / parcelas
                card_name = row.get('Cartao_Ref')
                dia_fech = mapa_fechamento.get(card_name, DIA_FECHAMENTO_PADRAO)
                
                for i in range(parcelas):
                    dt_parcela = data_compra + relativedelta(months=i)
                    mes_cobranca = dt_parcela.replace(day=1)
                    if dt_parcela.day > dia_fech:
                        mes_cobranca = (dt_parcela + relativedelta(months=1)).replace(day=1)
                    
                    if mes_cobranca >= hoje.replace(day=1):
                        projecao.append({
                            "Mes": mes_cobranca, "Valor": val_parc, "Origem": f"Cartão ({card_name})" if card_name else "Cartão"
                        })
            except: continue

    # 2. Empréstimos
    ativos = df_loans[df_loans['Status'] == 'Ativo']
    for _, row in ativos.iterrows():
        faltam = int(row['Parcelas_Totais'] - row['Parcelas_Pagas'])
        val_parc = float(row['Valor_Parcela'])
        dia_venc = int(row.get('Dia_Vencimento', 10))
        try: venc_atual = date(hoje.year, hoje.month, dia_venc)
        except: venc_atual = date(hoje.year, hoje.month, 28)
        if hoje > venc_atual: venc_atual += relativedelta(months=1)
        
        for i in range(faltam):
            dt_pag = venc_atual + relativedelta(months=i)
            projecao.append({
                "Mes": dt_pag.replace(day=1), "Valor": val_parc, "Origem": "Empréstimo"
            })

    # 3. Custos Fixos Recorrentes
    recorrentes = df_trans[df_trans['Recorrente'] == True]
    for _, row in recorrentes.iterrows():
        val = float(row['Valor_Total'])
        # IMPORTANTE: Só projeta se for DESPESA (Ignora Receita Recorrente no gráfico de dívida)
        if row['Tipo'] != 'Receita':
            for i in range(meses):
                mes_futuro = (hoje + relativedelta(months=i)).replace(day=1)
                projecao.append({
                    "Mes": mes_futuro, "Valor": val, "Origem": "Custo Fixo"
                })

    df_proj = pd.DataFrame(projecao)
    if not df_proj.empty:
        return df_proj.groupby(['Mes', 'Origem'])['Valor'].sum().reset_index()
    return pd.DataFrame()

def get_renda_media(df_trans, df_invest):
    # 1. Renda do Trabalho (Transações)
    media_trabalho = 5000.0
    try:
        df_rec = df_trans[df_trans['Tipo'] == 'Receita'].copy()
        if not df_rec.empty:
            df_rec['Data'] = pd.to_datetime(df_rec['Data'])
            mask = df_rec['Data'] >= (pd.Timestamp.now() - pd.Timedelta(days=180)) # Últimos 6 meses
            total = df_rec[mask]['Valor_Total'].sum()
            meses = df_rec[mask]['Data'].dt.to_period('M').nunique()
            media_trabalho = total / max(1, meses)
    except: pass

    # 2. Renda Passiva (Dividendos Estimados)
    renda_passiva = get_dividendos_estimados(df_invest)
    
    return media_trabalho + renda_passiva

def get_month_view(df_trans, mes_ref_date, df_cards):
    mapa_fechamento = {}
    if not df_cards.empty:
        for _, c in df_cards.iterrows():
            mapa_fechamento[c['Nome']] = int(c['Dia_Fechamento'])
            
    dt_fim_padrao = date(mes_ref_date.year, mes_ref_date.month, DIA_FECHAMENTO_PADRAO)
    dt_ini_padrao = (dt_fim_padrao - relativedelta(months=1)) + timedelta(days=1)
    
    transacoes_mes = []
    
    for _, row in df_trans.iterrows():
        try:
            data_t = pd.to_datetime(row['Data']).date()
            valor = float(row['Valor_Total'])
            try: parcelas = int(row['Qtd_Parcelas'])
            except: parcelas = 1
            if parcelas < 1: parcelas = 1
            valor_parc = valor / parcelas
            
            if row['Pagamento'] == "Crédito" or row['Tipo'] == 'Cartao':
                card_name = row.get('Cartao_Ref')
                dia_fech = mapa_fechamento.get(card_name, DIA_FECHAMENTO_PADRAO)
                
                for i in range(parcelas):
                    dt_parcela_base = data_t + relativedelta(months=i)
                    mes_fiscal_venc = dt_parcela_base
                    if dt_parcela_base.day > dia_fech:
                        mes_fiscal_venc = dt_parcela_base + relativedelta(months=1)
                    
                    venc_fatura = date(mes_fiscal_venc.year, mes_fiscal_venc.month, 1)
                    ref_visual = mes_ref_date.replace(day=1)
                    
                    if venc_fatura == ref_visual:
                        item_desc = f"{row['Descricao']} ({i+1}/{parcelas})"
                        transacoes_mes.append({"Data": dt_parcela_base, "Descricao": item_desc, "Categoria": row['Categoria'], "Tipo": row['Tipo'], "Valor": valor_parc})
            else:
                if dt_ini_padrao <= data_t <= dt_fim_padrao:
                    transacoes_mes.append({"Data": data_t, "Descricao": row['Descricao'], "Categoria": row['Categoria'], "Tipo": row['Tipo'], "Valor": valor})
        except: continue
    return pd.DataFrame(transacoes_mes)

def render_page():
    st.header("💎 Wealth Management & Dívidas")
    
    df_trans, df_invest, df_loans, df_cards = load_data()
    # Passa Investimentos para calcular Dividendos na Renda Média
    renda_media_historica = get_renda_media(df_trans, df_invest) 
    
    with st.container(border=True):
        col_date, col_info = st.columns([1, 3])
        with col_date:
            data_ref = st.date_input("Mês Ref.", date.today())
        
        dt_fim_ciclo = date(data_ref.year, data_ref.month, DIA_FECHAMENTO_PADRAO)
        if data_ref.day > DIA_FECHAMENTO_PADRAO: dt_fim_ciclo += relativedelta(months=1)
        
        df_view = get_month_view(df_trans, dt_fim_ciclo, df_cards)
        
        # --- CÁLCULO DE SALDO REAL DO MÊS ---
        receitas_mes = df_view[df_view['Tipo'] == 'Receita']['Valor'].sum() if not df_view.empty else 0
        div_mes = get_dividendos_estimados(df_invest) # Adiciona Dividendos ao fluxo
        total_entradas = receitas_mes + div_mes
        
        despesas_mes = df_view[df_view['Tipo'].isin(['Despesa Fixa', 'Cartao', 'Emprestimo'])]['Valor'].sum() if not df_view.empty else 0
        
        saldo = total_entradas - despesas_mes
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Entradas (Trab + Div)", f"R$ {total_entradas:,.2f}", f"+{div_mes:.2f} Div")
        k2.metric("Despesas", f"R$ {despesas_mes:,.2f}")
        k3.metric("Saldo Líquido", f"R$ {saldo:,.2f}", delta_color="normal" if saldo >= 0 else "inverse")

    st.divider()
    tab_dividas, tab_lan, tab_inv = st.tabs(["🏦 Dívidas", "📝 Lançamentos & Projeção", "📈 Investimentos"])

    with tab_dividas:
        c_add, c_view = st.columns([1, 2])
        with c_add:
            st.subheader("Novo Contrato")
            with st.form("form_divida"):
                l_nome = st.text_input("Nome (Ex: Empréstimo)")
                l_orig = st.number_input("Valor Original", 0.0)
                l_val_parc = st.number_input("Valor Parcela", 0.0)
                l_dia = st.number_input("Dia Venc.", 1, 31, 10)
                l_tot_parc = st.number_input("Total Parcelas", 1, 480, 12)
                l_pagas = st.number_input("Já Pagas", 0, 480, 0)
                if st.form_submit_button("Cadastrar"):
                    new_id = 1 if df_loans.empty else df_loans['ID'].max() + 1
                    novo = {"ID": new_id, "Nome": l_nome, "Valor_Original": l_orig, "Valor_Parcela": l_val_parc, "Parcelas_Totais": l_tot_parc, "Parcelas_Pagas": l_pagas, "Dia_Vencimento": l_dia, "Status": "Ativo", "Data_Inicio": date.today()}
                    df_loans = pd.concat([df_loans, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_loans, "Emprestimos"); st.rerun()
        
        with c_view:
            st.subheader("Carteira Ativa")
            ativos = df_loans[df_loans['Status'] == "Ativo"]
            if not ativos.empty:
                for idx, row in ativos.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['Nome']}** - R$ {row['Valor_Parcela']:.2f}/mês")
                        st.progress(row['Parcelas_Pagas'] / row['Parcelas_Totais'], text=f"{row['Parcelas_Pagas']}/{row['Parcelas_Totais']}")
                        if st.button("Pagar Parcela", key=f"pay_{row['ID']}"):
                            nova_trans = {"Data": date.today(), "Tipo": "Emprestimo", "Categoria": "Dívidas", "Descricao": f"Parcela {row['Nome']}", "Valor_Total": row['Valor_Parcela'], "Pagamento": "Débito", "Qtd_Parcelas": 1, "Recorrente": False, "Cartao_Ref": ""}
                            df_trans = pd.concat([df_trans, pd.DataFrame([nova_trans])], ignore_index=True)
                            df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'] += 1
                            if df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'].values[0] >= row['Parcelas_Totais']: 
                                df_loans.loc[df_loans['ID'] == row['ID'], 'Status'] = "Quitado"
                            save_data(df_trans, "Transacoes"); save_data(df_loans, "Emprestimos"); st.rerun()

    with tab_lan:
        st.subheader("🔮 Bola de Cristal")
        
        df_proj = get_future_projection(df_trans, df_loans, df_cards)
        
        if not df_proj.empty:
            df_proj['Mes'] = pd.to_datetime(df_proj['Mes'])
            df_proj = df_proj.sort_values('Mes')
            df_proj['Mes_Str'] = df_proj['Mes'].dt.strftime('%m/%Y')
            
            # --- CORREÇÃO DO SUFOCAMENTO ---
            # Usa a maior entre: Renda Média Histórica OU Renda Real deste Mês
            # Isso impede que o sistema fale que você tá quebrado se sua renda já caiu na conta
            base_calculo = max(renda_media_historica, total_entradas)
            
            prox_mes_date = (date.today().replace(day=1) + relativedelta(months=1))
            filtro_prox = df_proj[df_proj['Mes'] == pd.Timestamp(prox_mes_date)]
            comprometido_prox = filtro_prox['Valor'].sum() if not filtro_prox.empty else 0
            
            perc_prox = (comprometido_prox / base_calculo * 100) if base_calculo > 0 else 0
            
            m1, m2 = st.columns(2)
            m1.metric("Capacidade de Pagamento (Base)", f"R$ {base_calculo:,.2f}", "+Dividendos Incluídos")
            m2.metric(f"Comprometido {prox_mes_date.strftime('%b')}", f"{perc_prox:.1f}%", f"R$ {comprometido_prox:,.2f}", delta_color="inverse")
            
            st.bar_chart(df_proj, x="Mes_Str", y="Valor", color="Origem", stack=True)
        
        st.divider()
        
        # --- FORMULÁRIO CORRIGIDO ---
        with st.form("form_transacao"):
            st.markdown("#### 📝 Novo Lançamento")
            c1, c2, c3 = st.columns(3)
            dt_tr = c1.date_input("Data", date.today())
            tipo = c2.selectbox("Tipo", ["Despesa Fixa", "Cartao", "Receita", "Emprestimo"])
            categ = c3.text_input("Categoria", "Geral")
            
            c4, c5, c6 = st.columns(3)
            desc = c4.text_input("Descrição")
            val = c5.number_input("Valor", 0.0)
            
            # SELETOR DE CARTÃO INTELIGENTE
            card_ref = ""
            pagamento = "Crédito"
            
            if tipo == "Cartao":
                # Verifica se existem cartões
                lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
                if lista_cartoes:
                    card_ref = c6.selectbox("Qual Cartão?", lista_cartoes)
                else:
                    c6.error("Nenhum cartão cadastrado!")
            else:
                pagamento = c6.selectbox("Pagamento", ["Débito", "Pix", "Dinheiro"])
                
            c7, c8 = st.columns(2)
            parc = c7.number_input("Parcelas", 1, 60, 1)
            rec = False
            if tipo != "Cartao": rec = c8.checkbox("Recorrente?", False)
            
            if st.form_submit_button("Salvar"):
                nova = {
                    "Data": dt_tr, "Tipo": tipo, "Categoria": categ, "Descricao": desc, 
                    "Valor_Total": val, "Pagamento": pagamento, "Qtd_Parcelas": parc, 
                    "Recorrente": rec, "Cartao_Ref": card_ref
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([nova])], ignore_index=True)
                save_data(df_trans, "Transacoes"); st.rerun()

    with tab_inv:
        st.info("Acesse o módulo de 'Investimentos' para detalhes. Aqui apenas consideramos os Dividendos na renda.")