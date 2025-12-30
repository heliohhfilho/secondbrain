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
        df_t["Cartao_Ref"] = df_t["Cartao_Ref"].fillna("")
        if "ID_Compra" not in df_t.columns:
            df_t["ID_Compra"] = [str(uuid.uuid4())[:8] for _ in range(len(df_t))]

    if not df_c.empty:
        # Garante tipos numéricos para os dias
        df_c["Dia_Fechamento"] = pd.to_numeric(df_c["Dia_Fechamento"], errors='coerce').fillna(1).astype(int)
        df_c["Dia_Vencimento"] = pd.to_numeric(df_c["Dia_Vencimento"], errors='coerce').fillna(10).astype(int)

    return df_t, df_c

def save_full_dataframe(df):
    df_save = df.copy()
    # Remove colunas calculadas antes de salvar para não sujar o banco
    if "Data_Caixa" in df_save.columns:
        df_save = df_save.drop(columns=["Data_Caixa"])
        
    if "Data" in df_save.columns:
        df_save["Data"] = pd.to_datetime(df_save["Data"]).apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    
    conexoes.save_gsheet("Transacoes", df_save)

# --- 2. ENGINE DE VENCIMENTO (A LÓGICA DE OURO) ---
def calcular_data_caixa(row, cartoes_dict):
    """
    Define em qual mês o dinheiro vai sair da conta (Regime de Caixa).
    """
    # Se não é cartão de crédito, o caixa é na data da compra
    if row['Pagamento'] != 'Crédito' and row['Tipo'] != 'Cartão':
        return row['Data']
    
    # Se for cartão, precisamos ver as regras dele
    nome_cartao = row['Cartao_Ref']
    regras = cartoes_dict.get(nome_cartao)
    
    # Se não achar o cartão (ex: excluiu), assume data da compra
    if not regras:
        return row['Data']
    
    dia_compra = row['Data'].day
    dia_fech = regras['fechamento']
    dia_venc = regras['vencimento']
    
    # Lógica do Ciclo:
    # Se comprou ANTES ou NO dia do fechamento, entra na fatura atual.
    # Se comprou DEPOIS, entra na próxima.
    
    data_base = row['Data']
    
    if dia_compra <= dia_fech:
        # Cai na fatura deste mês
        # Ex: Compra 29/12, Fecha 31/12. Cai na fatura que fecha em Dez.
        data_fatura_fecha = data_base.replace(day=min(dia_fech, 28)) 
    else:
        # Cai na próxima fatura
        # Ex: Compra 02/01, Fecha 01/01. Já virou. Cai na fatura de Fev.
        data_fatura_fecha = data_base + relativedelta(months=1)
        
    # Agora calculamos o VENCIMENTO (Quando sai o dinheiro)
    # Se o vencimento é dia 06 e fechamento dia 31, o vencimento é no mês SEGUINTE ao fechamento.
    if dia_venc < dia_fech:
        # Ex: Fecha 31/12, Vence 06/01. (Vencimento é menor que fechamento)
        data_caixa = data_fatura_fecha + relativedelta(months=1)
    else:
        # Ex: Fecha 02, Vence 10. (Mesmo mês)
        data_caixa = data_fatura_fecha
        
    # Ajusta o dia exato do vencimento
    try:
        data_caixa = data_caixa.replace(day=dia_venc)
    except ValueError:
        # Caso caia dia 31 em mês de 30 dias, joga pro dia 28/30
        data_caixa = data_caixa + relativedelta(day=31) # Último dia do mês
        
    return data_caixa

# --- 3. DASHBOARD ---
def render_page():
    st.header("📊 Painel de Engenharia Financeira (Regime de Caixa)")
    df_trans, df_cards = load_data_dashboard()

    # Cria dicionário de regras para performance O(1)
    regras_cartoes = {}
    if not df_cards.empty:
        for _, row in df_cards.iterrows():
            regras_cartoes[row['Nome']] = {
                'fechamento': int(row['Dia_Fechamento']),
                'vencimento': int(row['Dia_Vencimento'])
            }

    # --- APLICA A ENGINE ---
    # Cria coluna virtual 'Data_Caixa' que representa a competência real
    if not df_trans.empty:
        df_trans['Data_Caixa'] = df_trans.apply(lambda row: calcular_data_caixa(row, regras_cartoes), axis=1)
    else:
        df_trans['Data_Caixa'] = pd.to_datetime([])

    # --- FILTROS ---
    with st.container():
        c_mes, c_resumo = st.columns([1, 3])
        
        # Filtro Global por Mês de CAIXA (Pagamento)
        # Padrão: Mês atual
        mes_selecionado = c_mes.date_input("Mês de Caixa (Pagamento)", date.today())
        
        # Filtra onde Data_Caixa == Mês Selecionado
        if not df_trans.empty:
            mask_mes = (df_trans['Data_Caixa'].dt.month == mes_selecionado.month) & \
                       (df_trans['Data_Caixa'].dt.year == mes_selecionado.year)
            
            df_view = df_trans[mask_mes].copy()
            
            # Ordena por dia de pagamento
            df_view = df_view.sort_values("Data_Caixa")

            # KPIs
            receita = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            invest = df_view[df_view['Tipo'] == 'Investimento']['Valor_Total'].sum()
            despesa = df_view[~df_view['Tipo'].isin(['Receita', 'Investimento'])]['Valor_Total'].sum()
            saldo = receita - despesa - invest
            
            k1, k2, k3, k4 = c_resumo.columns(4)
            k1.metric("Entradas Previstas", f"R$ {receita:,.2f}")
            k2.metric("Saídas Totais", f"R$ {despesa:,.2f}", help="Soma de pix, débito e faturas que vencem neste mês")
            k3.metric("Investimentos", f"R$ {invest:,.2f}")
            k4.metric("Saldo Previsto", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")
        else:
            df_view = pd.DataFrame()

    tab_dash, tab_add, tab_edit = st.tabs(["📈 Visão 360", "➕ Lançamento Inteligente", "📝 Editor de Caixa"])

    # ==============================================================================
    # ABA 1: VISÃO 360 (AGRUPADA CORRETAMENTE)
    # ==============================================================================
    with tab_dash:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("💳 Faturas Vencendo Este Mês")
            # Mostra apenas gastos de cartão que caíram neste mês de caixa
            df_faturas = df_view[(df_view['Tipo'] == 'Cartão') | (df_view['Pagamento'] == 'Crédito')]
            
            if not df_faturas.empty:
                resumo = df_faturas.groupby("Cartao_Ref")['Valor_Total'].sum().reset_index()
                # Pega dia de vencimento para exibir
                resumo['Dia Venc'] = resumo['Cartao_Ref'].map(lambda x: regras_cartoes.get(x, {}).get('vencimento', '-'))
                
                st.dataframe(
                    resumo, 
                    column_config={
                        "Valor_Total": st.column_config.NumberColumn("Valor da Fatura", format="R$ %.2f"),
                        "Dia Venc": st.column_config.NumberColumn("Dia", format="%d")
                    },
                    hide_index=True, use_container_width=True
                )
            else:
                st.success("Nenhuma fatura vence neste mês selecionado.")

        with c2:
            st.subheader("📊 Categorias")
            if not df_view.empty:
                df_cat = df_view[df_view['Tipo'] != 'Receita']
                res = df_cat.groupby("Categoria")['Valor_Total'].sum().reset_index().sort_values("Valor_Total", ascending=False)
                st.dataframe(res, hide_index=True, use_container_width=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})

    # ==============================================================================
    # ABA 2: LANÇAMENTO (COM PROJEÇÃO FUTURA CORRETA)
    # ==============================================================================
    with tab_add:
        st.caption("O sistema calculará automaticamente em qual fatura cairá cada parcela.")
        with st.form("form_smart", clear_on_submit=True):
            col_a, col_b, col_c = st.columns(3)
            dt_compra = col_a.date_input("Data da Compra", date.today())
            tipo = col_b.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartão", "Receita", "Investimento"])
            valor = col_c.number_input("Valor TOTAL", min_value=0.01)
            
            col_d, col_e = st.columns(2)
            desc = col_d.text_input("Descrição")
            
            # Se for Crédito, habilita cartão
            opts = ["Pix", "Débito", "Dinheiro", "Crédito"]
            if tipo == "Cartão": opts = ["Crédito"]
            pagamento = col_e.selectbox("Meio de Pagamento", opts)
            
            col_f, col_g = st.columns(2)
            lista_nomes = list(regras_cartoes.keys())
            
            if pagamento == "Crédito":
                cartao = col_f.selectbox("Cartão Utilizado", lista_nomes)
                parcelas = col_g.number_input("Parcelas", 1, 60, 1)
            else:
                cartao = col_f.text_input("Cartão", value="", disabled=True)
                parcelas = col_g.number_input("Parcelas", 1, 1, 1, disabled=True)
                
            categ = st.text_input("Categoria", "Geral")

            if st.form_submit_button("Lançar"):
                rows = []
                valor_p = valor / parcelas
                uuid_grp = str(uuid.uuid4())[:8]
                
                for i in range(parcelas):
                    # Data da compra avança 1 mês por parcela
                    data_real_parcela = dt_compra + relativedelta(months=i)
                    
                    desc_final = desc
                    if parcelas > 1: desc_final = f"{desc} ({i+1}/{parcelas})"
                    
                    rows.append({
                        "Data": data_real_parcela,
                        "Tipo": tipo,
                        "Categoria": categ,
                        "Descricao": desc_final,
                        "Valor_Total": valor_p,
                        "Pagamento": pagamento,
                        "Qtd_Parcelas": parcelas,
                        "Cartao_Ref": cartao,
                        "ID_Compra": uuid_grp
                    })
                
                df_trans = pd.concat([df_trans, pd.DataFrame(rows)], ignore_index=True)
                save_full_dataframe(df_trans)
                st.success(f"Lançamento realizado! {parcelas} parcelas projetadas.")
                st.rerun()

    # ==============================================================================
    # ABA 3: EDITOR (MOSTRA DATA REAL vs DATA CAIXA)
    # ==============================================================================
    with tab_edit:
        st.info("A coluna 'Data_Caixa' é calculada automaticamente baseada no vencimento do cartão.")
        ver_tudo = st.checkbox("Ver todo histórico", value=False)
        
        df_show = df_trans.copy() if ver_tudo else df_view.copy()
        
        # Mostra a Data Caixa para conferência
        edited = st.data_editor(
            df_show,
            column_config={
                "Data": st.column_config.DateColumn("Data Compra", format="DD/MM/YYYY"),
                "Data_Caixa": st.column_config.DateColumn("Vencimento (Caixa)", format="DD/MM/YYYY", disabled=True),
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")
            },
            column_order=["Data", "Data_Caixa", "Descricao", "Valor_Total", "Pagamento", "Cartao_Ref", "Categoria"],
            use_container_width=True,
            num_rows="dynamic",
            key="editor_caixa"
        )
        
        if st.button("Salvar Alterações"):
            # A Data_Caixa é recalculada no load, não precisamos salvar ela
            if "Data_Caixa" in edited.columns:
                edited = edited.drop(columns=["Data_Caixa"])
                
            if ver_tudo:
                df_trans = edited
            else:
                # Atualiza apenas as linhas que estavam visíveis
                # (Simplificação: num sistema real usaria ID, aqui substituimos o range)
                df_trans = pd.concat([df_trans[~df_trans.index.isin(df_show.index)], edited], ignore_index=True)
                
            save_full_dataframe(df_trans)
            st.success("Dados atualizados!")
            st.rerun()

if __name__ == "__main__":
    render_page()