import streamlit as st
import pandas as pd
from datetime import date, datetime
from modules import conexoes

# --- CONFIGURAÇÕES E UTILITÁRIOS ---
def load_data_dashboard():
    """Carregamento robusto e tipagem de dados"""
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    if not df_t.empty:
        df_t["Data"] = pd.to_datetime(df_t["Data"], errors='coerce')
        # Garante numérico e força positivo para cálculos, o sinal é decidido pelo Tipo
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Cartao_Ref"] = df_t["Cartao_Ref"].fillna("")
        df_t["Categoria"] = df_t["Categoria"].fillna("Geral")
    
    # 2. Cartões (Para o Dropdown)
    cols_c = ["ID", "Nome", "Dia_Fechamento"]
    df_c = conexoes.load_gsheet("Cartoes", cols_c)
    
    return df_t, df_c

def save_full_dataframe(df):
    """Salva o DataFrame inteiro, garantindo que edições e exclusões sejam persistidas"""
    df_save = df.copy()
    if "Data" in df_save.columns:
        df_save["Data"] = pd.to_datetime(df_save["Data"]).apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    conexoes.save_gsheet("Transacoes", df_save)

# --- ENGINE DO DASHBOARD ---
def render_page():
    # CSS para ficar parecido com Excel (Compacto)
    st.markdown("""
        <style>
        .stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 5px;}
        div[data-testid="stExpander"] div[role="button"] p {font-size: 1.1rem; font-weight: bold;}
        </style>
    """, unsafe_allow_html=True)

    st.header("📊 Painel de Controle 360º")
    df_trans, df_cards = load_data_dashboard()

    # --- FILTRO GLOBAL (O "Olho" do Dashboard) ---
    with st.container():
        col_mes, col_kpi1, col_kpi2, col_kpi3 = st.columns([1, 1, 1, 1])
        data_ref = col_mes.date_input("Mês de Competência", date.today())
        
        # Filtragem Mestre
        if not df_trans.empty:
            df_mes = df_trans[
                (df_trans['Data'].dt.month == data_ref.month) & 
                (df_trans['Data'].dt.year == data_ref.year)
            ].copy()
            
            # Cálculos KPI
            receita = df_mes[df_mes['Tipo'] == 'Receita']['Valor_Total'].sum()
            
            # Despesas (Tudo que não é receita e nem investimento, pois investimento é transferência de patrimônio)
            despesas = df_mes[~df_mes['Tipo'].isin(['Receita', 'Investimento'])]['Valor_Total'].sum()
            
            # Investimentos
            investido = df_mes[df_mes['Tipo'] == 'Investimento']['Valor_Total'].sum()
            
            saldo = receita - despesas - investido

            col_kpi1.metric("💰 Receitas (Entradas)", f"R$ {receita:,.2f}")
            col_kpi2.metric("💸 Gastos Totais", f"R$ {despesas:,.2f}", delta=f"-{(despesas/receita)*100:.1f}%" if receita > 0 else "")
            col_kpi3.metric("Saldo em Caixa", f"R$ {saldo:,.2f}", delta_color="normal" if saldo >= 0 else "inverse")
        else:
            st.warning("Sem dados para carregar.")
            df_mes = pd.DataFrame()

    # --- ABAS ---
    tab_dash, tab_extrato, tab_lancamento = st.tabs(["📈 Visão Excel (Resumos)", "📝 Extrato & Edição", "➕ Novo Lançamento"])

    # ==============================================================================
    # 1. VISÃO EXCEL (A REPLICAÇÃO DA SUA PLANILHA)
    # ==============================================================================
    with tab_dash:
        col_esq, col_dir = st.columns([1, 1])
        
        # --- BLOCO 1: RESUMO POR CARTÃO (CRUCIAL PARA VOCÊ) ---
        with col_esq:
            st.subheader("💳 Faturas dos Cartões")
            if not df_mes.empty:
                # Filtra só o que é cartão ou crédito
                mask_cartao = (df_mes['Tipo'] == 'Cartão') | (df_mes['Pagamento'] == 'Crédito')
                df_cartoes = df_mes[mask_cartao]
                
                if not df_cartoes.empty:
                    # Agrupa por Nome do Cartão
                    resumo_cartoes = df_cartoes.groupby("Cartao_Ref")['Valor_Total'].sum().reset_index()
                    resumo_cartoes = resumo_cartoes.sort_values("Valor_Total", ascending=False)
                    
                    st.dataframe(
                        resumo_cartoes, 
                        column_config={
                            "Cartao_Ref": "Cartão",
                            "Valor_Total": st.column_config.NumberColumn("Fatura Atual", format="R$ %.2f")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
                    
                    # Gráfico de Rosca para ver peso de cada cartão
                    st.bar_chart(resumo_cartoes.set_index("Cartao_Ref"))
                else:
                    st.info("Nenhum gasto em cartão neste mês.")
            
            st.divider()
            
            # --- BLOCO 2: INVESTIMENTOS (SEUS FIIs/DAYTRADE) ---
            st.subheader("🚀 Investimentos do Mês")
            if not df_mes.empty:
                df_inv = df_mes[df_mes['Tipo'] == 'Investimento']
                total_inv = df_inv['Valor_Total'].sum()
                st.metric("Total Aportado", f"R$ {total_inv:,.2f}")
                
                if not df_inv.empty:
                    st.dataframe(
                        df_inv[['Data', 'Descricao', 'Valor_Total']],
                        hide_index=True,
                        use_container_width=True
                    )

        # --- BLOCO 3: METAS E ORÇAMENTO (CATEGORIAS) ---
        with col_dir:
            st.subheader("🎯 Orçamento (Metas vs Real)")
            
            # Definição das Metas (Hardcoded por enquanto, mas pode vir de banco)
            metas = {
                "Custo de Vida": 1500.00,
                "Lazer": 500.00,
                "Mercado": 800.00,
                "Carro": 300.00,
                "Investimento": 1000.00
            }
            
            if not df_mes.empty:
                # Agrupa gastos por categoria
                gastos_cat = df_mes.groupby("Categoria")['Valor_Total'].sum()
                
                for categoria, teto in metas.items():
                    # Busca aproximada (se a categoria contém a palavra chave)
                    # Ex: "Lazer Fim de Semana" cai em "Lazer"
                    gasto_atual = 0.0
                    for cat_real, valor in gastos_cat.items():
                        if categoria.lower() in cat_real.lower():
                            gasto_atual += valor
                    
                    perc = min(gasto_atual / teto, 1.0)
                    cor_barra = "green" if perc < 0.75 else "orange" if perc < 0.9 else "red"
                    
                    st.write(f"**{categoria}**")
                    c1, c2 = st.columns([3, 1])
                    c1.progress(perc)
                    c2.caption(f"R$ {gasto_atual:.0f} / {teto:.0f}")

    # ==============================================================================
    # 2. EXTRATO E EDIÇÃO (RESOLVE O PROBLEMA DE EDITAR/EXCLUIR)
    # ==============================================================================
    with tab_extrato:
        st.info("💡 **Editor Mestre:** Altere valores, descrições ou exclua linhas (selecione e aperte Delete) diretamente abaixo. Clique em Salvar para confirmar.")
        
        # Mostra TODOS os dados filtrados ou TUDO se quiser procurar histórico
        usar_filtro = st.checkbox("Filtrar apenas mês selecionado?", value=True)
        
        if usar_filtro:
            df_editor = df_mes.copy()
        else:
            df_editor = df_trans.copy()
        
        # O Editor de Dados
        edited_df = st.data_editor(
            df_editor,
            num_rows="dynamic", # Permite adicionar e deletar linhas
            column_config={
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f", min_value=0.0),
                "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Tipo": st.column_config.SelectboxColumn(options=["Receita", "Despesa Variável", "Despesa Fixa", "Cartão", "Investimento"]),
                "Pagamento": st.column_config.SelectboxColumn(options=["Pix", "Crédito", "Débito", "Dinheiro"]),
            },
            use_container_width=True,
            height=500,
            key="master_editor"
        )

        col_save, _ = st.columns([1, 4])
        if col_save.button("💾 SALVAR ALTERAÇÕES (Soberano)", type="primary"):
            if usar_filtro:
                # Se estava filtrado, precisamos atualizar APENAS as linhas desse mês no DF principal
                # 1. Remove as antigas do mês
                indices_antigos = df_trans[
                    (df_trans['Data'].dt.month == data_ref.month) & 
                    (df_trans['Data'].dt.year == data_ref.year)
                ].index
                df_trans = df_trans.drop(indices_antigos)
                
                # 2. Adiciona as novas (que vieram do editor)
                df_trans = pd.concat([df_trans, edited_df], ignore_index=True)
            else:
                # Se não estava filtrado, o editor contém tudo, então substitui tudo
                df_trans = edited_df
            
            save_full_dataframe(df_trans)
            st.success("Banco de dados atualizado com sucesso! Entradas duplicadas ou erros foram corrigidos.")
            st.rerun()

    # ==============================================================================
    # 3. NOVO LANÇAMENTO (SIMPLIFICADO PARA VELOCIDADE)
    # ==============================================================================
    with tab_lancamento:
        with st.form("quick_add", clear_on_submit=True):
            st.subheader("Novo Registro")
            l1_c1, l1_c2, l1_c3 = st.columns(3)
            data_in = l1_c1.date_input("Data", date.today())
            tipo_in = l1_c2.selectbox("Tipo", ["Despesa Variável", "Cartão", "Receita", "Investimento", "Despesa Fixa"])
            val_in = l1_c3.number_input("Valor", min_value=0.01)

            l2_c1, l2_c2 = st.columns(2)
            desc_in = l2_c1.text_input("Descrição")
            cat_in = l2_c2.text_input("Categoria (Ex: Lazer, Casa, Mercado)", value="Geral")
            
            # Lógica Condicional Visual
            l3_c1, l3_c2 = st.columns(2)
            
            lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
            
            if tipo_in == "Cartão":
                pag_in = "Crédito"
                cartao_in = l3_c1.selectbox("Fatura de Qual Cartão?", lista_cartoes)
                parc_in = l3_c2.number_input("Parcelas", 1, 60, 1)
            elif tipo_in == "Receita":
                pag_in = "Pix" # Default para receita
                cartao_in = ""
                parc_in = 1
                st.caption("Receitas são contabilizadas via Pix/Transferência por padrão.")
            else:
                pag_in = l3_c1.selectbox("Pagamento", ["Pix", "Débito", "Dinheiro"])
                cartao_in = ""
                parc_in = 1

            if st.form_submit_button("Lançar"):
                novo = {
                    "Data": data_in, "Tipo": tipo_in, "Categoria": cat_in,
                    "Descricao": desc_in, "Valor_Total": val_in, "Pagamento": pag_in,
                    "Qtd_Parcelas": parc_in, "Recorrente": False, "Cartao_Ref": cartao_in
                }
                # Adiciona e salva imediatamente
                df_trans = pd.concat([df_trans, pd.DataFrame([novo])], ignore_index=True)
                save_full_dataframe(df_trans)
                st.toast(f"Lançado: {desc_in}")
                # Não precisa de rerun aqui se form clear_on_submit=True, mas ajuda a atualizar o Dashboard
                st.rerun()

if __name__ == "__main__":
    render_page()