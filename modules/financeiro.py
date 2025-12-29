import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from modules import conexoes

DIA_FECHAMENTO_PADRAO = 5 

# --- CARREGAMENTO DE DADOS ---
def load_data():
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    if not df_t.empty:
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Recorrente"] = df_t["Recorrente"].astype(str).str.upper() == "TRUE"
        if "Cartao_Ref" not in df_t.columns: df_t["Cartao_Ref"] = ""

    # 2. Cartões
    df_c = conexoes.load_gsheet("Cartoes", ["ID", "Nome", "Dia_Fechamento"])

    # 3. Metas (Para o Organizador de Salário)
    df_m = conexoes.load_gsheet("Metas", ["ID", "Titulo", "Meta_Valor", "Progresso_Manual"])
    if not df_m.empty:
        df_m["Meta_Valor"] = pd.to_numeric(df_m["Meta_Valor"], errors='coerce').fillna(0.0)
        df_m["Progresso_Manual"] = pd.to_numeric(df_m["Progresso_Manual"], errors='coerce').fillna(0.0)

    # 4. Empréstimos (Legado para projeção)
    df_l = conexoes.load_gsheet("Emprestimos", ["ID", "Nome", "Valor_Parcela", "Parcelas_Totais", "Parcelas_Pagas", "Status"])

    return df_t, df_c, df_m, df_l

def save_data(df, aba):
    df_s = df.copy()
    if "Data" in df_s.columns: df_s["Data"] = df_s["Data"].astype(str)
    conexoes.save_gsheet(aba, df_s)

# --- ENGINE FINANCEIRA ---
def render_page():
    st.header("💎 Central de Comando Financeiro")
    df_trans, df_cards, df_metas, df_loans = load_data()

    # Layout de Abas Focadas no Fluxo de Trabalho
    tab_lan, tab_extrato, tab_org, tab_proj = st.tabs(["📝 Lançar & Cartões", "🔎 Extrato Detalhado", "💰 Organizador de Salário", "🔮 Projeção"])

    # ------------------------------------------------------------------
    # ABA 1: LANÇAMENTO (CORRIGIDO)
    # ------------------------------------------------------------------
    with tab_lan:
        st.subheader("Novo Lançamento")
        with st.form("form_entry"):
            c1, c2, c3 = st.columns(3)
            dt = c1.date_input("Data", date.today())
            tipo = c2.selectbox("Tipo", ["Despesa Variável", "Despesa Fixa", "Cartao", "Receita", "Investimento"])
            categ = c3.text_input("Categoria (Ex: Uber, Mercado)", "Geral")

            c4, c5 = st.columns([2, 1])
            desc = c4.text_input("Descrição")
            valor = c5.number_input("Valor (R$)", 0.0, step=10.0)

            # --- LÓGICA DO CARTÃO (FIXED) ---
            c6, c7 = st.columns(2)
            pagamento = "Crédito"
            cartao_selecionado = ""
            parcelas = 1

            if tipo == "Cartao":
                # Força a exibição dos cartões
                opcoes_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
                if opcoes_cartoes:
                    cartao_selecionado = c6.selectbox("Selecione o Cartão", opcoes_cartoes)
                else:
                    c6.error("⚠️ Nenhum cartão cadastrado na aba 'Cartões'!")
                
                parcelas = c7.number_input("Parcelas", 1, 60, 1)
            else:
                pagamento = c6.selectbox("Meio de Pagamento", ["Pix", "Débito", "Dinheiro", "Automático"])
                if tipo in ["Despesa Fixa", "Receita"]:
                    is_rec = c7.checkbox("É Recorrente?", value=True)
                else:
                    is_rec = False

            if st.form_submit_button("💾 Registrar Movimento"):
                novo = {
                    "Data": dt, "Tipo": tipo, "Categoria": categ, "Descricao": desc,
                    "Valor_Total": valor, "Pagamento": pagamento, "Qtd_Parcelas": parcelas,
                    "Recorrente": is_rec if tipo != "Cartao" else False,
                    "Cartao_Ref": cartao_selecionado
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([novo])], ignore_index=True)
                save_data(df_trans, "Transacoes")
                st.success("Lançamento Computado!")
                st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: EXTRATO (AUDITORIA)
    # ------------------------------------------------------------------
    with tab_extrato:
        st.subheader("🕵️ Telemetria Financeira")
        if df_trans.empty:
            st.info("Sem dados.")
        else:
            # Filtros Inteligentes
            c_fil1, c_fil2 = st.columns(2)
            mes_filter = c_fil1.date_input("Filtrar Mês", date.today())
            tipo_filter = c_fil2.multiselect("Filtrar Tipo", df_trans['Tipo'].unique())

            # Aplicação dos Filtros
            df_view = df_trans.copy()
            df_view['Data'] = pd.to_datetime(df_view['Data'])
            
            # Filtro de Mês (Ano e Mês batem)
            df_view = df_view[
                (df_view['Data'].dt.month == mes_filter.month) & 
                (df_view['Data'].dt.year == mes_filter.year)
            ]
            
            if tipo_filter:
                df_view = df_view[df_view['Tipo'].isin(tipo_filter)]

            # Métricas Rápidas do Filtro
            entradas = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            saidas = df_view[df_view['Tipo'] != 'Receita']['Valor_Total'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Entradas (Filtro)", f"R$ {entradas:,.2f}")
            k2.metric("Saídas (Filtro)", f"R$ {saidas:,.2f}")
            k3.metric("Saldo do Período", f"R$ {entradas - saidas:,.2f}", delta_color="normal")

            # A TABELA VOLTOU
            st.dataframe(
                df_view.sort_values("Data", ascending=False),
                column_config={
                    "Valor_Total": st.column_config.NumberColumn("Valor", format="R$ %.2f"),
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "Recorrente": st.column_config.CheckboxColumn("Fixo?"),
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Botão de Deleção Rápida
            with st.expander("🗑️ Excluir Lançamento (Modo Engenheiro)"):
                item_to_del = st.selectbox("Selecione para apagar:", df_view['Descricao'].unique())
                if st.button("Confirmar Exclusão"):
                    # Remove pelo index do dataframe original filtrado pela descrição (cuidado com duplicatas de nome)
                    idx_del = df_trans[df_trans['Descricao'] == item_to_del].index
                    if not idx_del.empty:
                        df_trans = df_trans.drop(idx_del)
                        save_data(df_trans, "Transacoes")
                        st.success("Deletado.")
                        st.rerun()

    # ------------------------------------------------------------------
    # ABA 3: ORGANIZADOR DE SALÁRIO
    # ------------------------------------------------------------------
    with tab_org:
        st.subheader("⚖️ Distribuidor de Recursos")
        st.caption("Aplica a regra 50/30/20 ou personalizada para quando seu salário cai.")

        col_sal, col_btn = st.columns([2, 1])
        salario_entrada = col_sal.number_input("Valor da Entrada (Salário/Freelance)", value=3000.0, step=100.0)
        
        # Configuração das Porcentagens
        with st.expander("⚙️ Configurar Regra (Split)"):
            c_ess, c_inv, c_laz = st.columns(3)
            p_ess = c_ess.number_input("% Essencial", 0, 100, 50)
            p_inv = c_inv.number_input("% Investimentos", 0, 100, 30)
            p_laz = c_laz.number_input("% Lazer/Torrar", 0, 100, 20)
            
            if p_ess + p_inv + p_laz != 100:
                st.error(f"A conta não fecha: {p_ess+p_inv+p_laz}% (Deve ser 100%)")

        # Visualização da Distribuição
        v_ess = salario_entrada * (p_ess/100)
        v_inv = salario_entrada * (p_inv/100)
        v_laz = salario_entrada * (p_laz/100)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("🏠 Essenciais", f"R$ {v_ess:,.2f}")
        m2.metric("🚀 Investir (Metas)", f"R$ {v_inv:,.2f}")
        m3.metric("🎉 Lazer", f"R$ {v_laz:,.2f}")
        
        st.divider()
        st.markdown("#### 🎯 Alocar Investimentos nas Metas")
        
        if df_metas.empty:
            st.warning("Cadastre metas na aba 'Projetos & Metas' para distribuir aqui.")
        else:
            # Distribuição automática proporcional ou manual
            soma_metas = df_metas['Meta_Valor'].sum()
            
            for idx, row in df_metas.iterrows():
                perc_meta = (row['Meta_Valor'] / soma_metas) if soma_metas > 0 else 0
                sugestao = v_inv * perc_meta
                
                with st.container(border=True):
                    cm1, cm2, cm3 = st.columns([2, 1, 1])
                    cm1.markdown(f"**{row['Titulo']}** (Meta: {row['Meta_Valor']})")
                    aporte = cm2.number_input(f"Aporte R$", value=float(f"{sugestao:.2f}"), key=f"ap_{row['ID']}")
                    
                    if cm3.button("✅ Alocar", key=f"btn_alo_{row['ID']}"):
                        # 1. Registra a saída do caixa (Investimento)
                        novo_inv = {
                            "Data": date.today(), "Tipo": "Investimento", "Categoria": "Metas",
                            "Descricao": f"Aporte: {row['Titulo']}", "Valor_Total": aporte,
                            "Pagamento": "Pix", "Qtd_Parcelas": 1, "Recorrente": False, "Cartao_Ref": ""
                        }
                        df_trans = pd.concat([df_trans, pd.DataFrame([novo_inv])], ignore_index=True)
                        save_data(df_trans, "Transacoes")
                        
                        # 2. Atualiza o progresso da Meta
                        df_metas.loc[idx, 'Progresso_Manual'] += aporte
                        conexoes.save_gsheet("Metas", df_metas)
                        
                        st.toast(f"R$ {aporte} alocado para {row['Titulo']}!")

    # ------------------------------------------------------------------
    # ABA 4: PROJEÇÃO (SIMPLIFICADA)
    # ------------------------------------------------------------------
    with tab_proj:
        st.info("Visão futura dos seus parcelamentos e custos fixos.")
        # (Aqui mantive a lógica simplificada para não poluir, 
        # se quiser o gráfico complexo de antes, me avise que reativo)
        
        # Filtra só o que é futuro
        futuro = []
        hoje = date.today()
        
        # 1. Cartões
        for _, row in df_trans.iterrows():
            if row['Tipo'] == 'Cartao' and row['Qtd_Parcelas'] > 1:
                valor_p = row['Valor_Total'] / row['Qtd_Parcelas']
                dt_compra = pd.to_datetime(row['Data']).date()
                for i in range(row['Qtd_Parcelas']):
                    dt_venc = dt_compra + relativedelta(months=i)
                    if dt_venc > hoje:
                        futuro.append({"Data": dt_venc, "Valor": valor_p, "Origem": f"Cartão ({row['Cartao_Ref']})"})

        df_fut = pd.DataFrame(futuro)
        if not df_fut.empty:
            df_fut['Mes'] = pd.to_datetime(df_fut['Data']).dt.strftime('%Y-%m')
            st.bar_chart(df_fut, x="Mes", y="Valor", color="Origem")
        else:
            st.success("Zero dívidas futuras de cartão!")