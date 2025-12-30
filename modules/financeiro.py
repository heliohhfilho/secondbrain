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
        # Limpeza de strings para evitar erros de "Nubank " vs "Nubank"
        df_t["Cartao_Ref"] = df_t["Cartao_Ref"].astype(str).str.strip()
        df_t["Tipo"] = df_t["Tipo"].astype(str).str.strip()
        
        if "ID_Compra" not in df_t.columns:
            df_t["ID_Compra"] = [str(uuid.uuid4())[:8] for _ in range(len(df_t))]

    if not df_c.empty:
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

# --- 2. ENGINE DE VENCIMENTO CORRIGIDA (SEM JUROS) ---
def calcular_data_caixa(row, cartoes_dict):
    """
    Define a Data de Competência (Quando o dinheiro realmente sai/entra).
    """
    # REGRA 1: RECEITA OU DÉBITO É CAIXA IMEDIATO
    # Se for salário, cai no dia. Se for débito/pix, sai no dia.
    if row['Tipo'] == 'Receita' or row['Pagamento'] != 'Crédito':
        return row['Data']
    
    # REGRA 2: CARTÃO DE CRÉDITO
    nome_cartao = row['Cartao_Ref']
    regras = cartoes_dict.get(nome_cartao)
    
    # Se não achou o cartão (nome errado), assume data da compra pra não sumir
    if not regras:
        return row['Data']
    
    dia_compra = row['Data'].day
    dia_fech = regras['fechamento']
    dia_venc = regras['vencimento']
    
    data_base = row['Data']
    
    # PASSO A: Identificar qual fatura essa compra pertence (Fechamento)
    if dia_compra <= dia_fech:
        # Comprou ANTES ou NO DIA do fechamento -> Fatura Atual
        # Ex: Fecha 29. Comprou 29. Entra nessa.
        # Ex: Fecha 29. Comprou 10. Entra nessa.
        data_referencia_fechamento = data_base
    else:
        # Comprou DEPOIS do fechamento -> Fatura Seguinte
        # Ex: Fecha 29. Comprou 30. Só entra na próxima.
        data_referencia_fechamento = data_base + relativedelta(months=1)
        
    # PASSO B: Calcular quando essa fatura é PAGA (Vencimento)
    # Se o vencimento é dia 06 e fecha dia 29, o vencimento é no MÊS SEGUINTE ao fechamento.
    if dia_venc < dia_fech:
        # Ex: Fecha 29/Jan. Vence 06. O 06 vem depois do 29? Sim, mas no calendário é mês seguinte.
        data_caixa = data_referencia_fechamento + relativedelta(months=1)
    else:
        # Ex: Fecha 02/Jan. Vence 10/Jan. Mesmo mês.
        data_caixa = data_referencia_fechamento
        
    # Ajusta o dia exato
    try:
        data_caixa = data_caixa.replace(day=dia_venc)
    except ValueError:
        # Fallback para fim de mês (ex: dia 31 em fevereiro)
        data_caixa = data_caixa + relativedelta(day=31)
        
    return data_caixa

# --- 3. DASHBOARD ---
def render_page():
    st.header("📊 Painel Financeiro (Fluxo Real)")
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

    # --- FILTRO MESTRE ---
    with st.container():
        c_mes, c_resumo = st.columns([1, 3])
        
        # Filtra pelo mês que o dinheiro ENTRA ou SAI (Caixa)
        mes_selecionado = c_mes.date_input("Visualizar Mês de Caixa", date.today())
        
        if not df_trans.empty:
            mask_mes = (df_trans['Data_Caixa'].dt.month == mes_selecionado.month) & \
                       (df_trans['Data_Caixa'].dt.year == mes_selecionado.year)
            
            df_view = df_trans[mask_mes].copy()
            df_view = df_view.sort_values("Data_Caixa")

            # KPIs (Cálculo à prova de falhas)
            receita = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            invest = df_view[df_view['Tipo'] == 'Investimento']['Valor_Total'].sum()
            
            # Despesa = Tudo que não é Receita e nem Investimento
            despesa = df_view[~df_view['Tipo'].isin(['Receita', 'Investimento'])]['Valor_Total'].sum()
            
            saldo = receita - despesa - invest
            
            k1, k2, k3, k4 = c_resumo.columns(4)
            k1.metric("Salário/Entradas", f"R$ {receita:,.2f}", help="Baseado na Data do Recebimento")
            k2.metric("Contas/Faturas", f"R$ {despesa:,.2f}", help="Baseado na Data de Vencimento")
            k3.metric("Investimentos", f"R$ {invest:,.2f}")
            k4.metric("Saldo do Mês", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")
        else:
            df_view = pd.DataFrame()

    tab_dash, tab_add, tab_edit = st.tabs(["📈 Visão 360", "➕ Lançamento", "📝 Editor (Auditoria)"])

    # --- ABA 1: VISÃO GERAL ---
    with tab_dash:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💳 Faturas a Pagar (Neste Mês)")
            # Filtra apenas o que é CRÉDITO e cai neste mês
            df_faturas = df_view[(df_view['Tipo'] == 'Cartão') | (df_view['Pagamento'] == 'Crédito')]
            
            if not df_faturas.empty:
                resumo = df_faturas.groupby("Cartao_Ref")['Valor_Total'].sum().reset_index()
                resumo['Vencimento'] = resumo['Cartao_Ref'].map(lambda x: regras_cartoes.get(x, {}).get('vencimento', '-'))
                st.dataframe(resumo, hide_index=True, use_container_width=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})
            else:
                st.info("Zero faturas vencendo neste mês.")

        with c2:
            st.subheader("📊 Para onde foi o dinheiro?")
            if not df_view.empty:
                # Exclui receita para ver só gastos
                df_cat = df_view[df_view['Tipo'] != 'Receita']
                res = df_cat.groupby("Categoria")['Valor_Total'].sum().reset_index().sort_values("Valor_Total", ascending=False)
                st.dataframe(res, hide_index=True, use_container_width=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})

    # --- ABA 2: LANÇAMENTO ---
    with tab_add:
        st.caption("O sistema calcula automaticamente o vencimento correto para evitar juros.")
        with st.form("form_smart", clear_on_submit=True):
            l1_a, l1_b, l1_c = st.columns(3)
            dt_compra = l1_a.date_input("Data da Ocorrência", date.today())
            tipo = l1_b.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartão", "Receita", "Investimento"])
            valor = l1_c.number_input("Valor TOTAL", min_value=0.01)
            
            l2_a, l2_b = st.columns(2)
            desc = l2_a.text_input("Descrição")
            
            opts = ["Pix", "Débito", "Dinheiro", "Crédito"]
            if tipo == "Cartão": opts = ["Crédito"]
            if tipo == "Receita": opts = ["Pix", "Dinheiro"]
            
            pagamento = l2_b.selectbox("Pagamento", opts)
            
            l3_a, l3_b, l3_c = st.columns(3)
            # Lógica de Cartão
            nomes_cartoes = list(regras_cartoes.keys())
            if pagamento == "Crédito":
                cartao = l3_a.selectbox("Cartão", nomes_cartoes)
                parcelas = l3_b.number_input("Vezes", 1, 60, 1)
            else:
                cartao = l3_a.text_input("Cartão", value="", disabled=True)
                parcelas = l3_b.number_input("Vezes", 1, 1, 1, disabled=True)
                
            categ = l3_c.text_input("Categoria", "Geral")

            if st.form_submit_button("Lançar"):
                rows = []
                valor_p = valor / parcelas
                uuid_grp = str(uuid.uuid4())[:8]
                
                for i in range(parcelas):
                    data_real_parcela = dt_compra + relativedelta(months=i)
                    
                    # Descrição inteligente
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
                st.success(f"Registrado!")
                st.rerun()

    # --- ABA 3: EDITOR ---
    with tab_edit:
        st.info("Confira aqui se as datas de pagamento estão corretas.")
        ver_tudo = st.checkbox("Ver histórico completo", value=False)
        
        df_show = df_trans.copy() if ver_tudo else df_view.copy()
        
        edited = st.data_editor(
            df_show,
            column_config={
                "Data": st.column_config.DateColumn("Data Fato", format="DD/MM/YYYY"),
                "Data_Caixa": st.column_config.DateColumn("Data Pagamento", format="DD/MM/YYYY", disabled=True),
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")
            },
            column_order=["Data", "Data_Caixa", "Descricao", "Valor_Total", "Pagamento", "Cartao_Ref", "Tipo"],
            use_container_width=True,
            num_rows="dynamic",
            key="audit_editor"
        )
        
        if st.button("Salvar Ajustes"):
            if "Data_Caixa" in edited.columns:
                edited = edited.drop(columns=["Data_Caixa"])
            
            if ver_tudo:
                df_trans = edited
            else:
                # Remove as linhas visualizadas e insere as editadas
                df_trans = pd.concat([df_trans[~df_trans.index.isin(df_show.index)], edited], ignore_index=True)
            
            save_full_dataframe(df_trans)
            st.success("Salvo!")
            st.rerun()

if __name__ == "__main__":
    render_page()