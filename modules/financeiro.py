import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from modules import conexoes
import uuid

# --- 1. CARREGAMENTO E MAPA DE CARTÕES ---
def load_data_dashboard():
    # Carrega Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Cartao_Ref", "ID_Compra"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    # Carrega Cartões
    cols_c = ["ID", "Nome", "Dia_Fechamento", "Dia_Vencimento"]
    df_c = conexoes.load_gsheet("Cartoes", cols_c)
    
    if not df_t.empty:
        df_t["Data"] = pd.to_datetime(df_t["Data"], errors='coerce')
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        
        # SANEAMENTO DE STRINGS (Resolve o bug dos cartões sumindo)
        # Remove espaços extras: "Banco Pan " vira "Banco Pan"
        df_t["Cartao_Ref"] = df_t["Cartao_Ref"].astype(str).str.strip()
        df_t["Tipo"] = df_t["Tipo"].astype(str).str.strip()
        
        if "ID_Compra" not in df_t.columns:
            df_t["ID_Compra"] = [str(uuid.uuid4())[:8] for _ in range(len(df_t))]

    if not df_c.empty:
        # Saneamento também nos Cartões
        df_c["Nome"] = df_c["Nome"].astype(str).str.strip()
        df_c["Dia_Fechamento"] = pd.to_numeric(df_c["Dia_Fechamento"], errors='coerce').fillna(1).astype(int)
        df_c["Dia_Vencimento"] = pd.to_numeric(df_c["Dia_Vencimento"], errors='coerce').fillna(10).astype(int)

    return df_t, df_c

def save_full_dataframe(df):
    df_save = df.copy()
    if "Data_Caixa" in df_save.columns:
        df_save = df_save.drop(columns=["Data_Caixa"])
    
    if "Data" in df_save.columns:
        df_save["Data"] = pd.to_datetime(df_save["Data"]).apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    
    conexoes.save_gsheet("Transacoes", df_save)

# --- 2. ENGINE DE CAIXA (Lógica Financeira) ---
def calcular_data_caixa(row, cartoes_dict):
    """
    Calcula quando o dinheiro efetivamente sai da conta.
    """
    # REGRA DE OURO DO SALÁRIO: Receita cai no dia exato.
    if row['Tipo'] == 'Receita':
        return row['Data']
        
    # Se não é cartão de crédito (Pix, Débito, Dinheiro), é no dia.
    if row['Pagamento'] != 'Crédito':
        return row['Data']
    
    # Lógica de Cartão de Crédito
    nome_cartao = row['Cartao_Ref']
    regras = cartoes_dict.get(nome_cartao)
    
    if not regras:
        return row['Data'] # Fallback
    
    dia_compra = row['Data'].day
    dia_fech = regras['fechamento']
    dia_venc = regras['vencimento']
    data_base = row['Data']
    
    # 1. Definição da Fatura (Competência)
    if dia_compra <= dia_fech:
        # Cai na fatura atual
        data_ref_fatura = data_base
    else:
        # Cai na próxima fatura
        data_ref_fatura = data_base + relativedelta(months=1)
        
    # 2. Definição do Pagamento (Caixa)
    # Se fecha dia 31 e vence dia 06, o pagamento é no mês seguinte ao fechamento
    if dia_venc < dia_fech:
        data_caixa = data_ref_fatura + relativedelta(months=1)
    else:
        # Se fecha dia 02 e vence dia 10, é no mesmo mês
        data_caixa = data_ref_fatura
        
    # Ajusta o dia
    try:
        data_caixa = data_caixa.replace(day=dia_venc)
    except ValueError:
        data_caixa = data_caixa + relativedelta(day=31)
        
    return data_caixa

# --- 3. DASHBOARD ---
def render_page():
    st.header("📊 Painel Financeiro")
    df_trans, df_cards = load_data_dashboard()

    # Mapa de regras
    regras_cartoes = {}
    if not df_cards.empty:
        for _, row in df_cards.iterrows():
            regras_cartoes[row['Nome']] = {
                'fechamento': int(row['Dia_Fechamento']),
                'vencimento': int(row['Dia_Vencimento'])
            }

    # Aplica Engine
    if not df_trans.empty:
        df_trans['Data_Caixa'] = df_trans.apply(lambda row: calcular_data_caixa(row, regras_cartoes), axis=1)
    else:
        df_trans['Data_Caixa'] = pd.to_datetime([])

    # --- CORREÇÃO DO PERÍODO VIGENTE (O ERRO ESTAVA AQUI) ---
    hoje = date.today()
    
    # Se hoje é dia 30, e seu ciclo vira dia 05, você já está vivendo o mês seguinte financeiramente.
    # Ex: Hoje 30/12 -> Mostra Janeiro (onde está o salário do dia 05/01 e a fatura do dia 06/01)
    if hoje.day > 5:
        data_default = hoje + relativedelta(months=1)
    else:
        data_default = hoje

    # --- FILTRO MESTRE ---
    with st.container():
        c_mes, c_resumo = st.columns([1, 3])
        
        # O value agora usa data_default corrigida!
        mes_selecionado = c_mes.date_input("Mês de Caixa (Vigência)", value=data_default)
        
        if not df_trans.empty:
            # Filtro pela Data de CAIXA (Quando o dinheiro move)
            mask_mes = (df_trans['Data_Caixa'].dt.month == mes_selecionado.month) & \
                       (df_trans['Data_Caixa'].dt.year == mes_selecionado.year)
            
            df_view = df_trans[mask_mes].copy()
            df_view = df_view.sort_values("Data_Caixa")

            # KPIs
            receita = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            invest = df_view[df_view['Tipo'] == 'Investimento']['Valor_Total'].sum()
            despesa = df_view[~df_view['Tipo'].isin(['Receita', 'Investimento'])]['Valor_Total'].sum()
            saldo = receita - despesa - invest
            
            k1, k2, k3, k4 = c_resumo.columns(4)
            k1.metric("Salário/Entradas", f"R$ {receita:,.2f}", help=f"Entradas previstas para {mes_selecionado.strftime('%B')}")
            k2.metric("Contas/Faturas", f"R$ {despesa:,.2f}", help="Total de saídas de caixa")
            k3.metric("Investimentos", f"R$ {invest:,.2f}")
            k4.metric("Saldo Líquido", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")
        else:
            df_view = pd.DataFrame()

    tab_dash, tab_add, tab_edit, tab_risk = st.tabs(["📈 Visão 360", "➕ Lançamento", "📝 Editor", "⚠️ Parcelar Fatura"])

    # --- ABA 1: VISÃO GERAL ---
    with tab_dash:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💳 Faturas do Mês")
            df_faturas = df_view[(df_view['Tipo'] == 'Cartão') | (df_view['Pagamento'] == 'Crédito')]
            
            if not df_faturas.empty:
                resumo = df_faturas.groupby("Cartao_Ref")['Valor_Total'].sum().reset_index()
                resumo['Vencimento'] = resumo['Cartao_Ref'].map(lambda x: regras_cartoes.get(x, {}).get('vencimento', '-'))
                st.dataframe(resumo, hide_index=True, width=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})
            else:
                st.info("Nenhuma fatura vence neste mês de caixa.")

        with c2:
            st.subheader("📊 Categorias")
            if not df_view.empty:
                df_cat = df_view[df_view['Tipo'] != 'Receita']
                res = df_cat.groupby("Categoria")['Valor_Total'].sum().reset_index().sort_values("Valor_Total", ascending=False)
                st.dataframe(res, hide_index=True, width=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})

    # --- ABA 2: LANÇAMENTO (SEM FORMULÁRIO PARA PERMITIR INTERATIVIDADE) ---
    with tab_add:
        st.caption("O sistema calcula automaticamente o vencimento correto para evitar juros.")
        
        # Removemos o st.form para permitir que a seleção de Pagamento destrave o Cartão em tempo real
        
        l1_a, l1_b, l1_c = st.columns(3)
        dt_compra = l1_a.date_input("Data da Ocorrência", date.today())
        tipo = l1_b.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartão", "Receita", "Investimento"])
        valor = l1_c.number_input("Valor TOTAL", min_value=0.01)
        
        l2_a, l2_b = st.columns(2)
        desc = l2_a.text_input("Descrição")
        
        # Lógica de Opções
        opts = ["Pix", "Débito", "Dinheiro", "Crédito"]
        if tipo == "Cartão": opts = ["Crédito"]
        if tipo == "Receita": opts = ["Pix", "Dinheiro"]
        
        # Agora, ao mudar isso, o Streamlit roda o script e atualiza a variável abaixo
        pagamento = l2_b.selectbox("Pagamento", opts)
        
        l3_a, l3_b, l3_c = st.columns(3)
        
        # Lógica de Cartão (Agora funciona!)
        nomes_cartoes = list(regras_cartoes.keys())
        cartao_disabled = True if pagamento != "Crédito" else False
        
        cartao = l3_a.selectbox("Cartão", nomes_cartoes, disabled=cartao_disabled)
        parcelas = l3_b.number_input("Vezes", 1, 60, 1, disabled=cartao_disabled)
        categ = l3_c.text_input("Categoria", "Geral")

        st.divider()

        # Botão solto (fora de form)
        if st.button("🚀 Lançar Registro", type="primary"):
            rows = []
            
            # Sanitização
            if pagamento != "Crédito":
                parcelas = 1
                cartao = ""

            valor_p = valor / parcelas
            uuid_grp = str(uuid.uuid4())[:8]
            
            for i in range(parcelas):
                data_real_parcela = dt_compra + relativedelta(months=i)
                desc_f = desc
                if parcelas > 1: desc_f = f"{desc} ({i+1}/{parcelas})"
                
                rows.append({
                    "Data": data_real_parcela,
                    "Tipo": tipo,
                    "Categoria": categ,
                    "Descricao": desc_f,
                    "Valor_Total": valor_p,
                    "Pagamento": pagamento,
                    "Qtd_Parcelas": parcelas,
                    "Cartao_Ref": cartao,
                    "ID_Compra": uuid_grp
                })
            
            df_trans = pd.concat([df_trans, pd.DataFrame(rows)], ignore_index=True)
            save_full_dataframe(df_trans)
            st.success(f"Registrado com sucesso!")
            st.rerun() # Força atualização do Dashboard

    # --- ABA 3: EDITOR ---
    with tab_edit:
        st.info("A coluna 'Data_Caixa' mostra quando o dinheiro sai/entra de fato.")
        ver_tudo = st.checkbox("Ver histórico completo", value=False)
        
        df_show = df_trans.copy() if ver_tudo else df_view.copy()
        
        edited = st.data_editor(
            df_show,
            column_config={
                "Data": st.column_config.DateColumn("Data Fato", format="DD/MM/YYYY"),
                "Data_Caixa": st.column_config.DateColumn("Data Caixa", format="DD/MM/YYYY", disabled=True),
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")
            },
            column_order=["Data", "Data_Caixa", "Descricao", "Valor_Total", "Pagamento", "Cartao_Ref", "Tipo"],
            width=True,
            num_rows="dynamic",
            key="audit_editor"
        )
        
        if st.button("Salvar Ajustes"):
            if "Data_Caixa" in edited.columns:
                edited = edited.drop(columns=["Data_Caixa"])
            
            if ver_tudo:
                df_trans = edited
            else:
                df_trans = pd.concat([df_trans[~df_trans.index.isin(df_show.index)], edited], ignore_index=True)
            
            save_full_dataframe(df_trans)
            st.success("Salvo!")
            st.rerun()

    # ==============================================================================
    # ABA 4: ZONA DE PERIGO (PARCELAMENTO DE FATURA)
    # ==============================================================================
    with tab_risk:
        st.warning("⚠️ Atenção: Esta ferramenta refinancia sua dívida de cartão. Use com sabedoria.")
        
        with st.form("form_refin", clear_on_submit=True):
            col_r1, col_r2 = st.columns(2)
            
            # Seleção do Cartão
            nomes_cartoes = list(regras_cartoes.keys())
            cartao_alvo = col_r1.selectbox("Qual fatura será parcelada?", nomes_cartoes)
            
            # Valor total da dívida atual (apenas referência ou para cálculo)
            valor_divida = col_r2.number_input("Valor Total da Fatura (R$)", min_value=0.01)
            
            st.divider()
            
            c_ent, c_parc_val, c_qtd = st.columns(3)
            
            # 1. Entrada (O que você paga AGORA para o banco aceitar o acordo)
            entrada = c_ent.number_input("Valor da Entrada (Pago Agora)", min_value=0.0)
            
            # 2. Como ficou o acordo no banco
            val_parcela = c_parc_val.number_input("Valor da Parcela Fixa (C/ Juros)", min_value=0.01, help="Valor exato que virá nas próximas faturas")
            qtd_parcelas = c_qtd.number_input("Quantidade de Parcelas", min_value=1, max_value=48, value=1)
            
            # Feedback do Juros
            total_final = entrada + (val_parcela * qtd_parcelas)
            juros_total = total_final - valor_divida
            if valor_divida > 0:
                st.caption(f"💰 Total Final: R$ {total_final:,.2f} | Juros/Encargos: R$ {juros_total:,.2f}")

            if st.form_submit_button("🚨 Executar Parcelamento"):
                new_entries = []
                grupo_id = str(uuid.uuid4())[:8]
                data_hoje = date.today()
                
                # A. REGISTRAR A ENTRADA (Sai do caixa hoje, via Pix/Débito geralmente)
                if entrada > 0:
                    new_entries.append({
                        "Data": data_hoje,
                        "Tipo": "Despesa Fixa", # Ou Financeira
                        "Categoria": "Juros/Dívida",
                        "Descricao": f"Entrada Parc. Fatura {cartao_alvo}",
                        "Valor_Total": entrada,
                        "Pagamento": "Pix", # Geralmente entrada de acordo é à vista
                        "Qtd_Parcelas": 1,
                        "Cartao_Ref": "",
                        "ID_Compra": grupo_id
                    })
                
                # B. GERAR AS PARCELAS FUTURAS (Como se fosse uma compra no cartão)
                # Elas começam a cair na PRÓXIMA fatura
                for i in range(qtd_parcelas):
                    # Data base: Hoje + 1 mês * (i+1) para garantir que caia nas próximas
                    # Nota: A engine de caixa vai jogar isso para a fatura correta automaticamente
                    data_futura = data_hoje + relativedelta(months=i) 
                    
                    new_entries.append({
                        "Data": data_futura,
                        "Tipo": "Cartão", # Importante ser Cartão para somar na fatura futura
                        "Categoria": "Juros/Dívida",
                        "Descricao": f"Parc. Fatura {cartao_alvo} ({i+1}/{qtd_parcelas})",
                        "Valor_Total": val_parcela,
                        "Pagamento": "Crédito",
                        "Qtd_Parcelas": qtd_parcelas,
                        "Cartao_Ref": cartao_alvo, # Vincula ao cartão para somar com novos gastos
                        "ID_Compra": grupo_id
                    })
                
                # Salvar
                df_trans = pd.concat([df_trans, pd.DataFrame(new_entries)], ignore_index=True)
                save_full_dataframe(df_trans)
                st.error(f"Parcelamento Realizado! O valor de R$ {val_parcela:,.2f} foi adicionado às suas faturas futuras do {cartao_alvo}.")
                st.rerun()

if __name__ == "__main__":
    render_page()