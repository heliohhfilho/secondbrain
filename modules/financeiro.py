import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from modules import conexoes

# --- FUNÇÕES AUXILIARES ---
def load_data():
    """
    Carrega os dados passando as colunas obrigatórias para o módulo conexoes.
    """
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    if not df_t.empty:
        df_t["Data"] = pd.to_datetime(df_t["Data"], errors='coerce')
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
    
    # 2. Cartões
    cols_c = ["ID", "Nome", "Dia_Fechamento"]
    df_c = conexoes.load_gsheet("Cartoes", cols_c)
    
    # 3. Empréstimos 
    # Passamos as colunas originais para garantir que o load_gsheet funcione
    cols_l = ["ID", "Nome", "Valor_Parcela", "Parcelas_Totais", "Parcelas_Pagas", "Status", "Dia_Vencimento"]
    df_l = conexoes.load_gsheet("Emprestimos", cols_l)
    
    if not df_l.empty:
        # --- MIGRAÇÃO DE SCHEMA (PÓS-LOAD) ---
        # Garante que as colunas novas de engenharia existam no DataFrame, mesmo que não venham da planilha
        
        if "Valor_Parcela_Original" not in df_l.columns:
            val_antigo = df_l.get("Valor_Parcela", 0.0)
            df_l["Valor_Parcela_Original"] = pd.to_numeric(val_antigo, errors='coerce').fillna(0.0)
            
        if "Parcelas_Restantes" not in df_l.columns:
            tot = pd.to_numeric(df_l.get("Parcelas_Totais", 0), errors='coerce').fillna(0)
            pag = pd.to_numeric(df_l.get("Parcelas_Pagas", 0), errors='coerce').fillna(0)
            df_l["Parcelas_Restantes"] = (tot - pag).astype(int)
        
        # Tipagem forçada para evitar erros de cálculo
        df_l["Valor_Parcela_Original"] = pd.to_numeric(df_l["Valor_Parcela_Original"], errors='coerce').fillna(0.0)
        df_l["Parcelas_Restantes"] = pd.to_numeric(df_l["Parcelas_Restantes"], errors='coerce').fillna(0).astype(int)
        
        if "Status" not in df_l.columns:
            df_l["Status"] = "Ativo"

    return df_t, df_c, df_l

def save_changes(df, tab_name):
    """Salva os dados formatando a data corretamente para o Google Sheets"""
    df_save = df.copy()
    if "Data" in df_save.columns:
        df_save["Data"] = pd.to_datetime(df_save["Data"]).apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    conexoes.save_gsheet(tab_name, df_save)

# --- ENGINE FINANCEIRA ---
def render_page():
    st.header("💎 Central Financeira - Engenharia")
    df_trans, df_cards, df_loans = load_data()

    tab_input, tab_flow, tab_macro, tab_debt = st.tabs([
        "📝 Input (C.R.U.E)", 
        "🔎 Extrato (Mês)", 
        "🔭 Visão Macro", 
        "🏦 Empréstimos"
    ])

    # ==============================================================================
    # 1. ABA DE INPUT 
    # ==============================================================================
    with tab_input:
        st.info("Preencha os dados da movimentação.")
        
        with st.form("main_form", clear_on_submit=True):
            # Linha 1
            c1, c2, c3 = st.columns(3)
            dt_input = c1.date_input("Data", date.today())
            tipo_mov = c2.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartão", "Receita", "Investimento", "Amortização"])
            categ = c3.text_input("Categoria", "Geral")

            # Linha 2
            c4, c5 = st.columns([2, 1])
            desc = c4.text_input("Descrição")
            valor = c5.number_input("Valor (R$)", min_value=0.01, step=10.0, format="%.2f")

            st.divider()
            
            # Linha 3 - Lógica de Pagamento
            c6, c7, c8 = st.columns(3)
            
            # Define opções de pagamento baseado no tipo
            if tipo_mov == "Receita":
                pgto_opts = ["Pix", "Transferência", "Dinheiro"]
                idx_pg = 0
            elif tipo_mov == "Cartão":
                pgto_opts = ["Crédito"] # Força Crédito se o tipo é Cartão
                idx_pg = 0
            else:
                pgto_opts = ["Pix", "Débito", "Crédito", "Dinheiro", "Automático"]
                idx_pg = 0 

            forma_pgto = c6.selectbox("Forma Pagamento", pgto_opts, index=idx_pg)
            
            # Lógica de Cartão: SÓ habilita se for Crédito ou Tipo Cartão
            lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
            cartao_ref = ""
            
            # Se for Crédito OU selecionou Tipo Cartão, mostra o selectbox
            if forma_pgto == "Crédito" or tipo_mov == "Cartão":
                cartao_ref = c7.selectbox("Qual Cartão?", lista_cartoes)
            else:
                c7.text_input("Cartão", value="N/A", disabled=True)
                cartao_ref = ""

            parc = c8.number_input("Parcelas", 1, 60, 1)

            if st.form_submit_button("💾 Salvar Lançamento", type="primary"):
                novo_reg = {
                    "Data": dt_input, "Tipo": tipo_mov, "Categoria": categ,
                    "Descricao": desc, "Valor_Total": valor, "Pagamento": forma_pgto,
                    "Qtd_Parcelas": parc, "Recorrente": False, "Cartao_Ref": cartao_ref
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([novo_reg])], ignore_index=True)
                save_changes(df_trans, "Transacoes")
                st.success(f"✅ Lançado: {desc} - R$ {valor}")
                st.rerun()

    # ==============================================================================
    # 2. FLUXO MICRO (EDITÁVEL)
    # ==============================================================================
    with tab_flow:
        st.subheader("🕵️ Extrato do Mês")
        col_filtro, _ = st.columns([1,3])
        mes_ref = col_filtro.date_input("Filtrar Mês", date.today())
        
        if not df_trans.empty:
            # Filtro de Data
            mask_mes = (df_trans['Data'].dt.month == mes_ref.month) & (df_trans['Data'].dt.year == mes_ref.year)
            df_mes = df_trans[mask_mes].copy()
            
            # Cálculo de totais
            entradas = df_mes[df_mes['Tipo'] == 'Receita']['Valor_Total'].sum()
            saidas = df_mes[df_mes['Tipo'] != 'Receita']['Valor_Total'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Entradas", f"R$ {entradas:,.2f}")
            k2.metric("Saídas", f"R$ {saidas:,.2f}")
            k3.metric("Saldo Líquido", f"R$ {entradas - saidas:,.2f}")

            st.caption("Edite diretamente na tabela abaixo para corrigir ou excluir lançamentos.")
            
            # Data Editor com opção de deletar
            edited_df = st.data_editor(
                df_mes,
                num_rows="dynamic", # Permite adicionar/remover linhas
                column_config={
                    "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f"),
                    "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                    "Qtd_Parcelas": st.column_config.NumberColumn(format="%d"),
                },
                column_order=["Data", "Descricao", "Valor_Total", "Tipo", "Categoria", "Pagamento", "Cartao_Ref"],
                use_container_width=True,
                key="editor_micro_key"
            )

            if st.button("💾 Salvar Alterações da Tabela"):
                # Atualiza o DF principal: Remove as linhas antigas desse mês e insere as novas editadas
                df_trans = df_trans[~mask_mes]
                df_trans = pd.concat([df_trans, edited_df], ignore_index=True)
                
                save_changes(df_trans, "Transacoes")
                st.success("Tabela atualizada com sucesso!")
                st.rerun()

    # ==============================================================================
    # 3. VISÃO MACRO
    # ==============================================================================
    with tab_macro:
        st.subheader("📅 Visão Anual")
        if not df_trans.empty:
            df_view = df_trans.copy()
            df_view['Mes_Ano'] = df_view['Data'].dt.to_period('M')
            
            pivot = df_view.pivot_table(
                index="Categoria", 
                columns="Mes_Ano", 
                values="Valor_Total", 
                aggfunc="sum", 
                fill_value=0
            )
            # Ordenar colunas cronologicamente
            pivot = pivot.sort_index(axis=1)
            
            st.dataframe(pivot.style.format("R$ {:,.2f}"), use_container_width=True)
        else:
            st.info("Sem dados para projeção.")

    # ==============================================================================
    # 4. EMPRÉSTIMOS E AMORTIZAÇÃO
    # ==============================================================================
    with tab_debt:
        c_left, c_right = st.columns([1, 2])
        
        # --- CADASTRO ---
        with c_left:
            st.markdown("### ➕ Novo Contrato")
            with st.form("add_loan"):
                nome_div = st.text_input("Nome (Ex: Financiamento)")
                val_parc = st.number_input("Valor Parcela", min_value=0.0)
                tot_parc = st.number_input("Total de Parcelas", min_value=1, value=12)
                
                if st.form_submit_button("Cadastrar"):
                    new_id = 1 if df_loans.empty else df_loans['ID'].max() + 1 if 'ID' in df_loans else 1
                    novo_emp = {
                        "ID": new_id,
                        "Nome": nome_div,
                        "Valor_Parcela_Original": val_parc,
                        "Parcelas_Restantes": tot_parc,
                        "Status": "Ativo",
                        # Campos de compatibilidade
                        "Valor_Parcela": val_parc,
                        "Parcelas_Totais": tot_parc,
                        "Parcelas_Pagas": 0
                    }
                    df_loans = pd.concat([df_loans, pd.DataFrame([novo_emp])], ignore_index=True)
                    save_changes(df_loans, "Emprestimos")
                    st.success("Cadastrado!")
                    st.rerun()

        # --- GESTÃO ---
        with c_right:
            st.markdown("### 📉 Carteira Ativa")
            
            # Filtra ativos
            if not df_loans.empty and "Status" in df_loans.columns:
                ativos = df_loans[df_loans['Status'] == 'Ativo']
            else:
                ativos = pd.DataFrame()

            if ativos.empty:
                st.info("Nenhuma dívida ativa.")
            else:
                for idx, row in ativos.iterrows():
                    val_p = row.get('Valor_Parcela_Original', 0)
                    restante = row.get('Parcelas_Restantes', 0)
                    saldo_est = val_p * restante

                    with st.expander(f"💳 {row['Nome']} | Restam: {restante}x", expanded=True):
                        col_info, col_action = st.columns([1, 1])
                        
                        with col_info:
                            st.metric("Parcela", f"R$ {val_p:,.2f}")
                            st.metric("Saldo Devedor (Est.)", f"R$ {saldo_est:,.2f}")

                        with col_action:
                            st.markdown("**Amortizar ou Pagar**")
                            with st.form(f"pay_{row.get('ID', idx)}"):
                                v_pago = st.number_input("Valor Pago (R$)", min_value=0.0, step=10.0, key=f"v_{row.get('ID', idx)}")
                                p_elim = st.number_input("Parcelas Eliminadas", min_value=1, step=1, key=f"p_{row.get('ID', idx)}")
                                
                                if st.form_submit_button("🔥 Lançar Pagamento"):
                                    # 1. Atualiza Dívida
                                    novo_saldo_p = max(0, restante - p_elim)
                                    # Busca pelo ID ou Index para garantir update correto
                                    if 'ID' in df_loans.columns:
                                        real_idx = df_loans[df_loans['ID'] == row['ID']].index[0]
                                    else:
                                        real_idx = idx
                                        
                                    df_loans.at[real_idx, 'Parcelas_Restantes'] = novo_saldo_p
                                    # Atualiza pagas tb para manter consistencia
                                    pagas_atual = df_loans.at[real_idx, 'Parcelas_Pagas'] if 'Parcelas_Pagas' in df_loans.columns else 0
                                    df_loans.at[real_idx, 'Parcelas_Pagas'] = pagas_atual + p_elim
                                    
                                    if novo_saldo_p == 0:
                                        df_loans.at[real_idx, 'Status'] = "Quitado"
                                    
                                    save_changes(df_loans, "Emprestimos")
                                    
                                    # 2. Lança no Fluxo
                                    rec = {
                                        "Data": date.today(),
                                        "Tipo": "Despesa Fixa",
                                        "Categoria": "Amortização",
                                        "Descricao": f"Pagto {row['Nome']}",
                                        "Valor_Total": v_pago,
                                        "Pagamento": "Pix",
                                        "Qtd_Parcelas": 1,
                                        "Cartao_Ref": ""
                                    }
                                    df_trans = pd.concat([df_trans, pd.DataFrame([rec])], ignore_index=True)
                                    save_changes(df_trans, "Transacoes")
                                    
                                    st.toast("Pagamento processado!")
                                    st.rerun()

if __name__ == "__main__":
    render_page()