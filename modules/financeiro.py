import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
import os
import numpy as np

from modules import conexoes # <--- Conexão Nuvem

DIA_FECHAMENTO_PADRAO = 5 

def load_data():
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    if not df_t.empty:
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Recorrente"] = df_t["Recorrente"].astype(str).str.upper() == "TRUE"
    
    # 2. Investimentos
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

    # 4. Cartões (Lê da aba que já criamos no módulo de Cartões)
    df_c = conexoes.load_gsheet("Cartoes", ["ID", "Nome", "Dia_Fechamento"])

    return df_t, df_i, df_l, df_c

def save_data(df, aba):
    df_save = df.copy()
    # Converte colunas sensíveis para string antes do upload
    for col in ["Data", "Data_Compra", "Data_Inicio"]:
        if col in df_save.columns: df_save[col] = df_save[col].astype(str)
    conexoes.save_gsheet(aba, df_save)

def get_proximo_vencimento(dia_vencimento):
    hoje = date.today()
    try: venc_este_mes = date(hoje.year, hoje.month, int(dia_vencimento))
    except ValueError: venc_este_mes = date(hoje.year, hoje.month, 28)
    if hoje > venc_este_mes: return venc_este_mes + relativedelta(months=1)
    return venc_este_mes

# --- MOTOR DE PROJEÇÃO ---
def get_future_projection(df_trans, df_loans, df_cards, meses=12):
    hoje = date.today()
    projecao = []
    
    # Mapa de Fechamento dos Cartões (Para precisão da fatura)
    mapa_fechamento = {}
    if not df_cards.empty:
        for _, c in df_cards.iterrows():
            mapa_fechamento[c['Nome']] = int(c['Dia_Fechamento'])

    # 1. Projeção de Cartão de Crédito (Parcelados)
    for _, row in df_trans.iterrows():
        if row['Tipo'] == 'Cartao' and row['Qtd_Parcelas'] > 1:
            try:
                data_compra = pd.to_datetime(row['Data']).date()
                parcelas = int(row['Qtd_Parcelas'])
                val_parc = float(row['Valor_Total']) / parcelas
                card_name = row.get('Cartao_Ref')
                
                # Pega dia de fechamento específico ou usa padrão 5
                dia_fech = mapa_fechamento.get(card_name, 5) 
                
                for i in range(parcelas):
                    dt_parcela = data_compra + relativedelta(months=i)
                    
                    # Lógica de Corte de Fatura
                    mes_cobranca = dt_parcela.replace(day=1)
                    if dt_parcela.day > dia_fech:
                        mes_cobranca = (dt_parcela + relativedelta(months=1)).replace(day=1)
                    
                    # Só mostra meses futuros ou atual
                    if mes_cobranca >= hoje.replace(day=1):
                        origin_tag = f"Cartão ({card_name})" if card_name else "Cartão (Geral)"
                        projecao.append({
                            "Mes": mes_cobranca,
                            "Valor": val_parc,
                            "Origem": origin_tag
                        })
            except: continue

    # 2. Projeção de Empréstimos Ativos
    ativos = df_loans[df_loans['Status'] == 'Ativo']
    for _, row in ativos.iterrows():
        faltam = int(row['Parcelas_Totais'] - row['Parcelas_Pagas'])
        val_parc = float(row['Valor_Parcela'])
        
        # Pega próximo vencimento real
        dia_venc = int(row.get('Dia_Vencimento', 10))
        try: venc_atual = date(hoje.year, hoje.month, dia_venc)
        except: venc_atual = date(hoje.year, hoje.month, 28)
        if hoje > venc_atual: venc_atual += relativedelta(months=1)
        
        for i in range(faltam):
            dt_pag = venc_atual + relativedelta(months=i)
            projecao.append({
                "Mes": dt_pag.replace(day=1), 
                "Valor": val_parc, 
                "Origem": "Empréstimo/Dívida"
            })

    # 3. Projeção de Despesas Fixas (Recorrentes)
    recorrentes = df_trans[df_trans['Recorrente'] == True]
    for _, row in recorrentes.iterrows():
        val = float(row['Valor_Total'])
        for i in range(meses):
            mes_futuro = (hoje + relativedelta(months=i)).replace(day=1)
            projecao.append({
                "Mes": mes_futuro, 
                "Valor": val, 
                "Origem": "Custo Fixo"
            })

    df_proj = pd.DataFrame(projecao)
    if not df_proj.empty:
        # Agrupa para o gráfico
        return df_proj.groupby(['Mes', 'Origem'])['Valor'].sum().reset_index()
    return pd.DataFrame()

def get_renda_media(df_trans):
    try:
        df_rec = df_trans[df_trans['Tipo'] == 'Receita'].copy()
        if df_rec.empty: return 5000.0
        df_rec['Data'] = pd.to_datetime(df_rec['Data'])
        df_rec = df_rec.sort_values('Data')
        mask = df_rec['Data'] >= (pd.Timestamp.now() - pd.Timedelta(days=180))
        total = df_rec[mask]['Valor_Total'].sum()
        meses = df_rec[mask]['Data'].dt.to_period('M').nunique()
        return total / max(1, meses)
    except: return 5000.0

def get_month_view(df_trans, mes_ref_date, df_cards):
    # Cria mapa de fechamentos
    mapa_fechamento = {}
    if not df_cards.empty:
        for _, c in df_cards.iterrows():
            mapa_fechamento[c['Nome']] = int(c['Dia_Fechamento'])
            
    # Usa o padrão para definir o ciclo visual, mas calcula fatura baseada no cartão
    dt_fim_padrao = date(mes_ref_date.year, mes_ref_date.month, DIA_FECHAMENTO_PADRAO)
    dt_ini_padrao = (dt_fim_padrao - relativedelta(months=1)) + timedelta(days=1)
    
    transacoes_mes = []
    
    for _, row in df_trans.iterrows():
        try:
            data_t = pd.to_datetime(row['Data']).date()
            valor = float(row['Valor_Total'])
            pagamento = row['Pagamento']
            try: parcelas = int(row['Qtd_Parcelas'])
            except: parcelas = 1
            if parcelas < 1: parcelas = 1
            valor_parc = valor / parcelas
            
            if pagamento == "Crédito" or row['Tipo'] == 'Cartao':
                card_name = row.get('Cartao_Ref')
                dia_fech = mapa_fechamento.get(card_name, DIA_FECHAMENTO_PADRAO)
                
                # Define a data de corte deste mês ESPECÍFICO para este cartão
                # Se estamos vendo Fev, o corte é dia X de Fev
                dt_corte_card = date(mes_ref_date.year, mes_ref_date.month, dia_fech)
                
                for i in range(parcelas):
                    dt_parcela_base = data_t + relativedelta(months=i)
                    
                    # Lógica de Fatura Específica
                    mes_fiscal_venc = dt_parcela_base
                    if dt_parcela_base.day > dia_fech:
                        mes_fiscal_venc = dt_parcela_base + relativedelta(months=1)
                    
                    # Normaliza vencimento para comparar com o mês de referência visual
                    # Se a fatura vence em Jan, ela aparece na visão de Jan
                    venc_fatura = date(mes_fiscal_venc.year, mes_fiscal_venc.month, 1) # Normaliza pro dia 1
                    ref_visual = mes_ref_date.replace(day=1)
                    
                    if venc_fatura == ref_visual:
                        item_desc = f"{row['Descricao']} ({i+1}/{parcelas})"
                        if card_name: item_desc += f" [{card_name}]"
                        transacoes_mes.append({"Data": dt_parcela_base, "Descricao": item_desc, "Categoria": row['Categoria'], "Tipo": row['Tipo'], "Valor": valor_parc})
            else:
                if dt_ini_padrao <= data_t <= dt_fim_padrao:
                    transacoes_mes.append({"Data": data_t, "Descricao": row['Descricao'], "Categoria": row['Categoria'], "Tipo": row['Tipo'], "Valor": valor})
        except: continue
    return pd.DataFrame(transacoes_mes)

def render_page():
    st.header("💎 Wealth Management & Dívidas")
    
    df_trans, df_invest, df_loans, df_cards = load_data()
    renda_media = get_renda_media(df_trans)
    
    # --- HEADER ---
    with st.container(border=True):
        col_date, col_info = st.columns([1, 3])
        with col_date:
            data_ref = st.date_input("Mês Ref.", date.today())
        
        # Ajuste visual padrão
        dt_fim_ciclo = date(data_ref.year, data_ref.month, DIA_FECHAMENTO_PADRAO)
        if data_ref.day > DIA_FECHAMENTO_PADRAO: dt_fim_ciclo += relativedelta(months=1)
        
        df_view = get_month_view(df_trans, dt_fim_ciclo, df_cards)
        receitas = df_view[df_view['Tipo'] == 'Receita']['Valor'].sum() if not df_view.empty else 0
        despesas = df_view[df_view['Tipo'].isin(['Despesa Fixa', 'Cartao', 'Emprestimo'])]['Valor'].sum() if not df_view.empty else 0
        saldo = receitas - despesas
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Receitas", f"R$ {receitas:,.2f}")
        k2.metric("Despesas", f"R$ {despesas:,.2f}")
        k3.metric("Saldo", f"R$ {saldo:,.2f}", delta_color="normal" if saldo >= 0 else "inverse")

    st.divider()
    tab_dividas, tab_lan, tab_inv = st.tabs(["🏦 Dívidas", "📝 Lançamentos & Projeção", "📈 Investimentos"])

    # --- ABA 1: DÍVIDAS ---
    with tab_dividas:
        c_add, c_view = st.columns([1, 2])
        with c_add:
            st.subheader("Novo Contrato")
            with st.form("form_divida"):
                l_nome = st.text_input("Nome (Ex: Empréstimo Pessoal)")
                l_orig = st.number_input("Valor Original (R$)", 0.0)
                l_val_parc = st.number_input("Valor da Parcela (R$)", 0.0)
                l_dia = st.number_input("Dia Vencimento", 1, 31, 10)
                l_tot_parc = st.number_input("Total Parcelas", 1, 480, 48)
                l_pagas = st.number_input("Já Pagas", 0, 480, 0)
                if st.form_submit_button("Cadastrar Passivo"):
                    new_id = 1 if df_loans.empty else df_loans['ID'].max() + 1
                    novo = {"ID": new_id, "Nome": l_nome, "Valor_Original": l_orig, "Valor_Parcela": l_val_parc, "Parcelas_Totais": l_tot_parc, "Parcelas_Pagas": l_pagas, "Dia_Vencimento": l_dia, "Status": "Ativo", "Data_Inicio": date.today()}
                    df_loans = pd.concat([df_loans, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_loans, "Emprestimos"); st.success("Registrado."); st.rerun()
        
        with c_view:
            st.subheader("Carteira de Dívidas")
            ativos = df_loans[df_loans['Status'] == "Ativo"]
            if ativos.empty: st.success("Sem dívidas ativas!")
            else:
                for idx, row in ativos.iterrows():
                    with st.container(border=True):
                        total_financiado = row['Valor_Parcela'] * row['Parcelas_Totais']
                        juros_totais = total_financiado - row['Valor_Original']
                        faltam = row['Parcelas_Totais'] - row['Parcelas_Pagas']
                        prox_venc = get_proximo_vencimento(row['Dia_Vencimento'])
                        
                        c_tit, c_prox = st.columns([3, 1])
                        c_tit.markdown(f"### 📉 {row['Nome']}")
                        c_prox.metric("Vencimento", prox_venc.strftime('%d/%m'))

                        st.markdown("#### 🚩 Análise de Custo")
                        r1, r2, r3 = st.columns(3)
                        r1.metric("Valor Original", f"R$ {row['Valor_Original']:,.2f}")
                        r2.metric("Custo Final", f"R$ {total_financiado:,.2f}", delta=f"-{juros_totais:,.2f} Juros", delta_color="inverse")
                        st.progress(row['Parcelas_Pagas'] / row['Parcelas_Totais'], text=f"Progresso: {row['Parcelas_Pagas']}/{row['Parcelas_Totais']}")
                        
                        col_pay, col_amort, col_quit = st.columns([1, 1, 0.2])
                        if col_pay.button("✅ Pagar Parcela", key=f"pay_{row['ID']}"):
                            nova_trans = {"Data": date.today(), "Tipo": "Emprestimo", "Categoria": "Dívidas", "Descricao": f"Parcela {row['Nome']}", "Valor_Total": row['Valor_Parcela'], "Pagamento": "Débito", "Qtd_Parcelas": 1, "Recorrente": False}
                            df_trans = pd.concat([df_trans, pd.DataFrame([nova_trans])], ignore_index=True)
                            df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'] += 1
                            if df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'].values[0] >= row['Parcelas_Totais']: df_loans.loc[df_loans['ID'] == row['ID'], 'Status'] = "Quitado"
                            save_data(df_trans, "Transacoes"); save_data(df_loans, "Emprestimos"); st.rerun()

                        with col_amort.popover("🚀 Amortizar"):
                            val_amort = st.number_input("Valor (R$)", 0.0, step=100.0, key=f"va_{row['ID']}")
                            parc_elim = st.number_input("Parcelas Eliminadas", 0, int(faltam), 1, key=f"pa_{row['ID']}")
                            if st.button("Confirmar", key=f"ba_{row['ID']}"):
                                nova_trans = {"Data": date.today(), "Tipo": "Emprestimo", "Categoria": "Amortização", "Descricao": f"Amortização {row['Nome']}", "Valor_Total": val_amort, "Pagamento": "Pix", "Qtd_Parcelas": 1, "Recorrente": False}
                                df_trans = pd.concat([df_trans, pd.DataFrame([nova_trans])], ignore_index=True)
                                df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'] += parc_elim
                                if df_loans.loc[df_loans['ID'] == row['ID'], 'Parcelas_Pagas'].values[0] >= row['Parcelas_Totais']: df_loans.loc[df_loans['ID'] == row['ID'], 'Status'] = "Quitado"
                                save_data(df_trans, "Transacoes"); save_data(df_loans, "Emprestimos"); st.rerun()

                        if col_quit.button("🗑️", key=f"dl_{row['ID']}"):
                            df_loans = df_loans[df_loans['ID'] != row['ID']]
                            save_data(df_loans, "Emprestimos"); st.rerun()

    # --- ABA 2: LANÇAMENTOS (ATUALIZADO COM CARTÃO) ---
    with tab_lan:
        st.subheader("🔮 Bola de Cristal (Projeção Financeira)")
        st.caption("Visão futura de gastos JÁ contratados (Parcelas + Empréstimos + Fixos).")
        
        # Gera Projeção com Cartões
        df_proj = get_future_projection(df_trans, df_loans, df_cards)
        
        if not df_proj.empty:
            df_proj['Mes'] = pd.to_datetime(df_proj['Mes'])
            df_proj = df_proj.sort_values('Mes')
            df_proj['Mes_Str'] = df_proj['Mes'].dt.strftime('%m/%Y')
            
            # --- CÁLCULO DE MÉTRICAS DE SUFOCAMENTO ---
            # 1. Total por mês
            df_total_mes = df_proj.groupby('Mes')['Valor'].sum().reset_index()
            
            # 2. Próximo Mês (O Perigo Imediato)
            prox_mes_date = (date.today().replace(day=1) + relativedelta(months=1))
            prox_mes_date_ts = pd.Timestamp(prox_mes_date)
            
            filtro_prox = df_total_mes[df_total_mes['Mes'] == prox_mes_date_ts]
            comprometido_prox = filtro_prox['Valor'].sum() if not filtro_prox.empty else 0
            
            perc_prox = (comprometido_prox / renda_media * 100) if renda_media > 0 else 0
            
            # 3. Pior Cenário
            pior_val = df_total_mes['Valor'].max()
            pior_perc = (pior_val / renda_media * 100) if renda_media > 0 else 0
            
            # --- VISUALIZAÇÃO DOS KPIS ---
            m1, m2, m3 = st.columns(3)
            
            m1.metric("Sua Renda Média", f"R$ {renda_media:,.2f}", "Baseado no Histórico")
            
            # Cor condicional
            cor_delta = "normal" if perc_prox < 30 else "off" if perc_prox < 50 else "inverse"
            m2.metric(f"Comprometido em {prox_mes_date.strftime('%b')}", f"{perc_prox:.1f}%", f"R$ {comprometido_prox:,.2f}", delta_color=cor_delta)
            
            m3.metric("Pior Mês Futuro", f"{pior_perc:.1f}% da renda", f"R$ {pior_val:,.2f}")
            
            # Barras de Progresso
            st.caption("Nível de Sufocamento (Próximo Mês)")
            st.progress(min(perc_prox/100, 1.0))
            
            if perc_prox > 50:
                st.error(f"🚨 PARE! Mais da metade do seu dinheiro de {prox_mes_date.strftime('%B')} já era. Não parcele mais nada.")
            
            # --- GRÁFICO ---
            st.markdown("#### 📊 Composição da Dívida Futura")
            st.bar_chart(df_proj, x="Mes_Str", y="Valor", color="Origem", stack=True)
            
        else:
            st.success("✨ Zero dívidas futuras! Seu fluxo de caixa está livre.")
        
        st.divider()
        
        # --- FORMULÁRIO DE LANÇAMENTO (COM LÓGICA DE CARTÃO) ---
        with st.form("form_transacao"):
            st.markdown("#### 📝 Novo Lançamento")
            
            c1, c2, c3 = st.columns(3)
            dt_tr = c1.date_input("Data", date.today())
            tipo = c2.selectbox("Tipo", ["Despesa Fixa", "Cartao", "Receita", "Emprestimo"])
            categ = c3.text_input("Categoria (Ex: Mercado, Lazer)")
            
            c4, c5, c6 = st.columns(3)
            desc = c4.text_input("Descrição")
            val = c5.number_input("Valor Total (R$)", 0.0)
            
            # Lógica Condicional de Pagamento/Cartão
            forma = "Crédito"
            card_select = None
            rec = False
            
            if tipo == "Cartao":
                # Se for cartão, esconde 'Pagamento' e mostra 'Qual Cartão?'
                if not df_cards.empty:
                    card_select = c6.selectbox("Qual Cartão?", df_cards['Nome'].unique())
                else:
                    c6.warning("Cadastre cartões primeiro!")
            else:
                forma = c6.selectbox("Pagamento", ["Débito", "Pix", "Dinheiro"])
            
            c7, c8 = st.columns(2)
            parc = c7.number_input("Parcelas", 1, 60, 1)
            
            if tipo != "Cartao":
                rec = c8.checkbox("É Recorrente (Todo mês)?", False)
            
            if st.form_submit_button("Salvar Lançamento"):
                nova = {
                    "Data": dt_tr, "Tipo": tipo, "Categoria": categ, "Descricao": desc, 
                    "Valor_Total": val, "Pagamento": forma, "Qtd_Parcelas": parc, 
                    "Recorrente": rec, "Cartao_Ref": card_select
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([nova])], ignore_index=True)
                save_data(df_trans, "Transacoes")
                st.success("Registrado com sucesso!")
                st.rerun()
        
        # --- TABELA DE ÚLTIMOS LANÇAMENTOS ---
        if not df_trans.empty:
            st.markdown("#### 🕰️ Últimas Transações")
            # Mostra as colunas mais relevantes
            view_cols = ["Data", "Descricao", "Valor_Total", "Tipo", "Cartao_Ref", "Qtd_Parcelas"]
            # Garante que as colunas existem antes de mostrar
            cols_existentes = [c for c in view_cols if c in df_trans.columns]
            
            st.dataframe(
                df_trans.sort_values("Data", ascending=False).head(10)[cols_existentes], 
                use_container_width=True,
                hide_index=True
            )