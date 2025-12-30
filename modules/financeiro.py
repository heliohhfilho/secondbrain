import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from modules import conexoes # Mantendo seu módulo original

# --- CONFIGURAÇÕES GLOBAIS ---
st.set_page_config(layout="wide", page_title="Financeiro Eng.", page_icon="📈")

# --- FUNÇÕES AUXILIARES (UTILS) ---
def load_data_safe():
    """Carregamento resiliente dos dados para evitar quebras de tipo."""
    # 1. Transações
    df_t = conexoes.load_gsheet("Transacoes", ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"])
    if not df_t.empty:
        df_t["Data"] = pd.to_datetime(df_t["Data"], errors='coerce')
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
    
    # 2. Cartões
    df_c = conexoes.load_gsheet("Cartoes", ["ID", "Nome", "Dia_Fechamento"])
    
    # 3. Empréstimos (Schema atualizado para suportar amortização)
    df_l = conexoes.load_gsheet("Emprestimos", ["ID", "Nome", "Valor_Parcela_Original", "Saldo_Devedor_Atual", "Parcelas_Restantes", "Status", "Dia_Vencimento"])
    if not df_l.empty:
        df_l["Valor_Parcela_Original"] = pd.to_numeric(df_l["Valor_Parcela_Original"], errors='coerce').fillna(0.0)
        df_l["Parcelas_Restantes"] = pd.to_numeric(df_l["Parcelas_Restantes"], errors='coerce').fillna(0).astype(int)

    return df_t, df_c, df_l

def save_changes(df, tab_name):
    """Função genérica de salvamento (Commit)"""
    df_save = df.copy()
    if "Data" in df_save.columns:
        df_save["Data"] = df_save["Data"].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    conexoes.save_gsheet(tab_name, df_save)

# --- APP PRINCIPAL ---
def render_page():
    st.title("🏎️ Controle Financeiro - Engenharia de Capital")
    df_trans, df_cards, df_loans = load_data_safe()

    tab_input, tab_flow, tab_macro, tab_debt = st.tabs([
        "📝 Input (C.R.U.E)", 
        "🔎 Fluxo Micro (Mês)", 
        "🔭 Visão Macro (Ano)", 
        "🏦 Engenharia de Dívida"
    ])

    # ==============================================================================
    # 1. ABA DE INPUT (CORRIGIDA)
    # ==============================================================================
    with tab_input:
        st.caption("Otimizado para lançamentos rápidos e consistentes.")
        
        with st.form("main_form", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            dt_input = c1.date_input("Data do Fato", date.today())
            tipo_mov = c2.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartão", "Receita", "Investimento", "Amortização"])
            categ = c3.text_input("Categoria", "Geral")

            c4, c5 = st.columns([3, 1])
            desc = c4.text_input("Descrição")
            valor = c5.number_input("Valor Efetivo (R$)", min_value=0.01, format="%.2f")

            st.markdown("---")
            c6, c7, c8 = st.columns(3)
            
            # Lógica Condicional de Pagamento
            pgto_opts = ["Pix", "Débito", "Dinheiro", "Crédito"]
            # Se for Receita, não faz sentido ser Crédito
            if tipo_mov == "Receita":
                pgto_opts = ["Pix", "Transferência", "Dinheiro"]
            
            forma_pgto = c6.selectbox("Método", pgto_opts)
            
            # Lógica Condicional de Cartão (Só habilita se for Crédito ou Gasto Cartão)
            lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
            cartao_ref = ""
            
            if tipo_mov == "Cartão" or forma_pgto == "Crédito":
                cartao_ref = c7.selectbox("Alocar em qual fatura?", lista_cartoes)
            else:
                c7.text_input("Alocar em qual fatura?", value="N/A", disabled=True)

            parc = c8.number_input("Parcelas", 1, 60, 1)

            if st.form_submit_button("🚀 Lançar no Sistema"):
                novo_reg = {
                    "Data": dt_input, "Tipo": tipo_mov, "Categoria": categ,
                    "Descricao": desc, "Valor_Total": valor, "Pagamento": forma_pgto,
                    "Qtd_Parcelas": parc, "Recorrente": False, "Cartao_Ref": cartao_ref
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([novo_reg])], ignore_index=True)
                save_changes(df_trans, "Transacoes")
                st.success("Registro inserido com sucesso!")
                st.rerun()

    # ==============================================================================
    # 2. FLUXO MICRO (EDITE DIRETAMENTE AQUI)
    # ==============================================================================
    with tab_flow:
        st.subheader("Extrato Mensal Editável")
        col_filtro, _ = st.columns([1,3])
        mes_ref = col_filtro.date_input("Mês de Referência", date.today())
        
        # Filtro de Data
        mask_mes = (df_trans['Data'].dt.month == mes_ref.month) & (df_trans['Data'].dt.year == mes_ref.year)
        df_mes = df_trans[mask_mes].copy()

        # Data Editor permite CRUE direto na tabela
        edited_df = st.data_editor(
            df_mes,
            num_rows="dynamic",
            column_config={
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
            use_container_width=True,
            key="editor_micro"
        )

        # Botão para salvar alterações feitas na tabela
        if st.button("💾 Persistir Alterações do Mês"):
            # Atualiza o dataframe principal com as mudanças do mês
            df_trans.update(edited_df)
            # Para deleções, precisaria de logica mais complexa de index, 
            # mas o update cobre edições. Para deletar, use o num_rows dynamic.
            save_changes(df_trans, "Transacoes")
            st.success("Base de dados atualizada.")

    # ==============================================================================
    # 3. VISÃO MACRO (EXCEL STYLE)
    # ==============================================================================
    with tab_macro:
        st.subheader("📅 Visão Anual (Projeção & Realizado)")
        if not df_trans.empty:
            df_trans['Mes_Ano'] = df_trans['Data'].dt.to_period('M')
            
            # Pivot Table: Linhas = Categoria, Colunas = Mês, Valores = Soma
            pivot = df_trans.pivot_table(
                index="Categoria", 
                columns="Mes_Ano", 
                values="Valor_Total", 
                aggfunc="sum", 
                fill_value=0
            )
            
            # Adiciona totalizadores
            pivot.loc['TOTAL'] = pivot.sum()
            
            st.dataframe(pivot.style.format("R$ {:,.2f}"), use_container_width=True)
            st.caption("Nota: Valores negativos ou saídas devem ser interpretados conforme o tipo.")
        else:
            st.info("Insira dados para gerar a projeção.")

    # ==============================================================================
    # 4. ENGENHARIA DE DÍVIDA (AMORTIZAÇÃO)
    # ==============================================================================
    with tab_debt:
        c_left, c_right = st.columns([1, 2])
        
        with c_left:
            st.markdown("### 🛡️ Gestão de Passivo")
            with st.form("add_loan"):
                st.write("Novo Contrato")
                nome_div = st.text_input("Instituição/Motivo")
                val_parc = st.number_input("Valor da Parcela Original", min_value=0.0)
                tot_parc = st.number_input("Total de Parcelas", min_value=1)
                
                if st.form_submit_button("Criar Dívida"):
                    novo_emprestimo = {
                        "ID": len(df_loans) + 1,
                        "Nome": nome_div,
                        "Valor_Parcela_Original": val_parc,
                        "Saldo_Devedor_Atual": val_parc * tot_parc, # Estimativa inicial
                        "Parcelas_Restantes": tot_parc,
                        "Status": "Ativo",
                        "Dia_Vencimento": 10
                    }
                    df_loans = pd.concat([df_loans, pd.DataFrame([novo_emprestimo])], ignore_index=True)
                    save_changes(df_loans, "Emprestimos")
                    st.rerun()

        with c_right:
            st.markdown("### 📉 Amortização & Pagamentos")
            
            ativos = df_loans[df_loans['Status'] == 'Ativo']
            
            for idx, row in ativos.iterrows():
                with st.expander(f"{row['Nome']} | Restam: {row['Parcelas_Restantes']}x", expanded=True):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.metric("Parcela Base", f"R$ {row['Valor_Parcela_Original']:,.2f}")
                    c_b.metric("Restante (aprox)", f"R$ {row['Valor_Parcela_Original'] * row['Parcelas_Restantes']:,.2f}")
                    
                    st.markdown("#### Realizar Pagamento ou Amortização")
                    
                    with st.form(f"pay_form_{row['ID']}"):
                        col_val, col_elim = st.columns(2)
                        valor_pago = col_val.number_input("Valor Desembolsado (R$)", min_value=0.0, step=100.0, help="Quanto saiu do seu bolso hoje?")
                        parc_elim = col_elim.number_input("Parcelas Eliminadas", min_value=0, step=1, help="Inclui a do mês + as amortizadas de trás pra frente")
                        
                        if st.form_submit_button("🔥 Processar Pagamento"):
                            # 1. Atualiza Dívida
                            novo_restante = max(0, row['Parcelas_Restantes'] - parc_elim)
                            df_loans.loc[idx, 'Parcelas_Restantes'] = novo_restante
                            
                            if novo_restante == 0:
                                df_loans.loc[idx, 'Status'] = "Quitado"
                                st.balloons()
                            
                            save_changes(df_loans, "Emprestimos")
                            
                            # 2. Lança no Fluxo de Caixa (Saída Real)
                            lancamento_amort = {
                                "Data": date.today(),
                                "Tipo": "Despesa Fixa",
                                "Categoria": "Amortização Dívida",
                                "Descricao": f"Pagto {row['Nome']} (-{parc_elim} parc)",
                                "Valor_Total": valor_pago,
                                "Pagamento": "Pix", # Geralmente amortização é à vista
                                "Qtd_Parcelas": 1,
                                "Recorrente": False,
                                "Cartao_Ref": ""
                            }
                            df_trans = pd.concat([df_trans, pd.DataFrame([lancamento_amort])], ignore_index=True)
                            save_changes(df_trans, "Transacoes")
                            
                            st.success("Amortização processada e fluxo atualizado!")
                            st.rerun()

if __name__ == "__main__":
    main()