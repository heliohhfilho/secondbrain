import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from modules import conexoes
import uuid

# --- CONFIGURAÇÕES E UTILITÁRIOS ---
def load_data_dashboard():
    """Carregamento com tipagem forte"""
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Cartao_Ref", "ID_Compra"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    if not df_t.empty:
        df_t["Data"] = pd.to_datetime(df_t["Data"], errors='coerce')
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Cartao_Ref"] = df_t["Cartao_Ref"].fillna("")
        # Cria ID único se não existir para rastreabilidade
        if "ID_Compra" not in df_t.columns:
            df_t["ID_Compra"] = [str(uuid.uuid4())[:8] for _ in range(len(df_t))]
    
    cols_c = ["ID", "Nome", "Dia_Fechamento"]
    df_c = conexoes.load_gsheet("Cartoes", cols_c)
    
    return df_t, df_c

def save_full_dataframe(df):
    df_save = df.copy()
    if "Data" in df_save.columns:
        df_save["Data"] = pd.to_datetime(df_save["Data"]).apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else "")
    conexoes.save_gsheet("Transacoes", df_save)

def get_intervalo_competencia(data_ref):
    """
    Retorna data_inicio e data_fim baseado no ciclo 06 (mês anterior) a 05 (mês atual).
    Ex: Se data_ref é Jan/2026, pega de 06/12/2025 a 05/01/2026.
    """
    mes_atual = data_ref.replace(day=5)
    mes_anterior = (mes_atual - relativedelta(months=1)).replace(day=6)
    return mes_anterior, mes_atual

# --- ENGINE DO DASHBOARD ---
def render_page():
    st.header("📊 Painel de Engenharia Financeira")
    df_trans, df_cards = load_data_dashboard()

    # --- FILTRO POR CICLO DE PAGAMENTO ---
    with st.container():
        c_mes, c_resumo = st.columns([1, 3])
        
        # O usuário escolhe o Mês de Referência (O Mês que ele "Recebe")
        mes_selecionado = c_mes.date_input("Mês de Competência (Pagamento)", date.today())
        
        start_date, end_date = get_intervalo_competencia(mes_selecionado)
        
        st.caption(f"📅 Ciclo Vigente: **{start_date.strftime('%d/%m/%Y')}** até **{end_date.strftime('%d/%m/%Y')}**")

        # Filtro Inteligente (Range Date)
        if not df_trans.empty:
            mask_ciclo = (df_trans['Data'] >= pd.Timestamp(start_date)) & (df_trans['Data'] <= pd.Timestamp(end_date))
            df_view = df_trans[mask_ciclo].copy()
            
            # KPI Engine
            receita = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            invest = df_view[df_view['Tipo'] == 'Investimento']['Valor_Total'].sum()
            
            # Despesas = Tudo que não é Receita nem Investimento
            despesa = df_view[~df_view['Tipo'].isin(['Receita', 'Investimento'])]['Valor_Total'].sum()
            
            saldo = receita - despesa - invest
            
            k1, k2, k3, k4 = c_resumo.columns(4)
            k1.metric("Entradas (05)", f"R$ {receita:,.2f}")
            k2.metric("Gastos Ciclo", f"R$ {despesa:,.2f}")
            k3.metric("Investido", f"R$ {invest:,.2f}")
            k4.metric("Saldo Líquido", f"R$ {saldo:,.2f}", delta_color="normal" if saldo > 0 else "inverse")

    tab_dash, tab_add, tab_edit = st.tabs(["📈 Dashboard 360", "➕ Novo Lançamento (Parcelado)", "📝 Editor Full"])

    # ==============================================================================
    # 1. DASHBOARD 360
    # ==============================================================================
    with tab_dash:
        col_esq, col_dir = st.columns(2)
        
        with col_esq:
            st.subheader("💳 Faturas (Vencimento dia 05)")
            # Filtra cartões neste ciclo
            df_card = df_view[df_view['Cartao_Ref'] != ""].copy()
            if not df_card.empty:
                resumo = df_card.groupby("Cartao_Ref")['Valor_Total'].sum().reset_index()
                st.dataframe(resumo, use_container_width=True, hide_index=True)
                st.bar_chart(resumo.set_index("Cartao_Ref"))
            else:
                st.info("Sem gastos de cartão neste ciclo.")

        with col_dir:
            st.subheader("📊 Breakdown por Categoria")
            if not df_view.empty:
                # Agrupa despesas
                df_cat = df_view[~df_view['Tipo'].isin(['Receita'])].copy()
                resumo_cat = df_cat.groupby("Categoria")['Valor_Total'].sum().reset_index().sort_values("Valor_Total", ascending=False)
                st.dataframe(resumo_cat, use_container_width=True, hide_index=True, column_config={"Valor_Total": st.column_config.NumberColumn(format="R$ %.2f")})

    # ==============================================================================
    # 2. NOVO LANÇAMENTO (COM ENGINE DE PARCELAS)
    # ==============================================================================
    with tab_add:
        st.markdown("##### 🚀 Engine de Lançamento")
        st.caption("Ao lançar parcelado, o sistema projeta automaticamente os meses futuros.")
        
        with st.form("form_engine", clear_on_submit=True):
            # Linha 1
            c1, c2, c3 = st.columns(3)
            dt_fat = c1.date_input("Data da Compra", date.today())
            tipo = c2.selectbox("Classificação", ["Despesa Variável", "Despesa Fixa", "Receita", "Investimento", "Cartão"])
            desc = c3.text_input("Descrição (Ex: Notebook)")

            # Linha 2 - Valores
            c4, c5, c6 = st.columns(3)
            val_total = c4.number_input("Valor TOTAL da Compra", min_value=0.01, step=10.0)
            
            # Lógica de Pagamento
            opts_pg = ["Pix", "Dinheiro", "Débito"]
            if tipo in ["Cartão", "Despesa Variável", "Despesa Fixa"]: 
                opts_pg.insert(0, "Crédito")
            
            metodo = c5.selectbox("Método", opts_pg)
            categ = c6.text_input("Categoria", "Geral")

            # Linha 3 - Condicional Cartão
            st.divider()
            c7, c8 = st.columns(2)
            
            lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
            cartao_select = ""
            qtd_parc = 1
            
            # SE FOR CRÉDITO OU CARTÃO -> OBRIGA PREENCHER
            disable_card = True
            if metodo == "Crédito" or tipo == "Cartão":
                disable_card = False
                cartao_select = c7.selectbox("Fatura do Cartão", lista_cartoes)
                qtd_parc = c8.number_input("Dividido em quantas vezes?", min_value=1, max_value=60, value=1)
                
                if qtd_parc > 1:
                    st.info(f"ℹ️ O sistema criará {qtd_parc} lançamentos de R$ {val_total/qtd_parc:.2f} nas datas futuras.")
            else:
                c7.text_input("Cartão", value="N/A", disabled=True)
                c8.number_input("Parcelas", value=1, disabled=True)

            if st.form_submit_button("Processar Lançamento"):
                # Geração de ID Único para o grupo de parcelas
                group_id = str(uuid.uuid4())[:8]
                new_rows = []
                
                valor_parcela = val_total / qtd_parc
                
                for i in range(qtd_parc):
                    # Calcula data futura
                    # Se compra dia 10/01, parc 1 é 10/01, parc 2 é 10/02...
                    data_venc = dt_fat + relativedelta(months=i)
                    
                    desc_final = desc
                    if qtd_parc > 1:
                        desc_final = f"{desc} ({i+1}/{qtd_parc})"

                    row = {
                        "Data": data_venc,
                        "Tipo": tipo,
                        "Categoria": categ,
                        "Descricao": desc_final,
                        "Valor_Total": valor_parcela,
                        "Pagamento": metodo,
                        "Qtd_Parcelas": qtd_parc, # Informativo
                        "Cartao_Ref": cartao_select,
                        "ID_Compra": group_id
                    }
                    new_rows.append(row)
                
                df_trans = pd.concat([df_trans, pd.DataFrame(new_rows)], ignore_index=True)
                save_full_dataframe(df_trans)
                st.success(f"✅ Lançamento processado! {qtd_parc} parcelas geradas.")
                st.rerun()

    # ==============================================================================
    # 3. EDITOR (MANUTENÇÃO)
    # ==============================================================================
    with tab_edit:
        st.info("Aqui você edita ou exclui qualquer registro.")
        ver_tudo = st.checkbox("Ver todo o histórico (Desmarcar filtro de ciclo)", value=False)
        
        df_edit_source = df_trans.copy() if ver_tudo else df_view.copy()
        
        edited = st.data_editor(
            df_edit_source,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "Valor_Total": st.column_config.NumberColumn(format="R$ %.2f"),
                "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
            },
            key="editor_main"
        )
        
        if st.button("Salvar Edições"):
            if ver_tudo:
                df_trans = edited
            else:
                # Remove o range editado do original e insere o novo
                # (Estratégia segura: usar ID se possivel, mas aqui vamos por índice/filtro)
                df_trans = df_trans[~mask_ciclo]
                df_trans = pd.concat([df_trans, edited], ignore_index=True)
            
            save_full_dataframe(df_trans)
            st.success("Base atualizada.")
            st.rerun()

if __name__ == "__main__":
    render_page()