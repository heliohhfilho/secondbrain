import streamlit as st
import pandas as pd
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from modules import conexoes

DIA_FECHAMENTO_PADRAO = 5 

# --- CARREGAMENTO DE DADOS (COM PROTEÇÃO DE DATA) ---
def load_data():
    # 1. Transações
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    if not df_t.empty:
        # Tratamento de Data Robusto
        df_t["Data"] = pd.to_datetime(df_t["Data"], format='mixed', dayfirst=False, errors='coerce')
        
        df_t["Qtd_Parcelas"] = pd.to_numeric(df_t["Qtd_Parcelas"], errors='coerce').fillna(1).astype(int)
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)
        df_t["Recorrente"] = df_t["Recorrente"].astype(str).str.upper() == "TRUE"
        if "Cartao_Ref" not in df_t.columns: df_t["Cartao_Ref"] = ""

    # 2. Cartões
    df_c = conexoes.load_gsheet("Cartoes", ["ID", "Nome", "Dia_Fechamento"])

    # 3. Metas
    df_m = conexoes.load_gsheet("Metas", ["ID", "Titulo", "Meta_Valor", "Progresso_Manual"])
    if not df_m.empty:
        df_m["Meta_Valor"] = pd.to_numeric(df_m["Meta_Valor"], errors='coerce').fillna(0.0)
        df_m["Progresso_Manual"] = pd.to_numeric(df_m["Progresso_Manual"], errors='coerce').fillna(0.0)

    # 4. Empréstimos
    df_l = conexoes.load_gsheet("Emprestimos", ["ID", "Nome", "Valor_Parcela", "Parcelas_Totais", "Parcelas_Pagas", "Status"])

    return df_t, df_c, df_m, df_l

def save_data(df, aba):
    df_s = df.copy()
    # Converte datas para string padrão YYYY-MM-DD para o Google Sheets não confundir
    if "Data" in df_s.columns: 
        df_s["Data"] = pd.to_datetime(df_s["Data"], errors='coerce').dt.strftime('%Y-%m-%d').fillna(str(date.today()))
    conexoes.save_gsheet(aba, df_s)

# --- ENGINE FINANCEIRA ---
def render_page():
    st.header("💎 Central Financeira Definitiva")
    df_trans, df_cards, df_metas, df_loans = load_data()

    tab_lan, tab_extrato, tab_org, tab_proj = st.tabs(["📝 Lançar (Formulário)", "🔎 Extrato", "💰 Organizador", "🔮 Projeção"])

    # ------------------------------------------------------------------
    # ABA 1: LANÇAMENTO (FORMULÁRIO UNIVERSAL)
    # ------------------------------------------------------------------
    with tab_lan:
        st.info("Preencha os dados da movimentação abaixo.")
        with st.form("form_entry"):
            # LINHA 1: Básico
            c1, c2, c3 = st.columns(3)
            dt = c1.date_input("Data", date.today())
            tipo = c2.selectbox("Tipo de Movimento", ["Despesa Variável", "Despesa Fixa", "Cartao", "Receita", "Investimento"])
            categ = c3.text_input("Categoria", "Geral")

            # LINHA 2: Detalhes
            c4, c5 = st.columns([2, 1])
            desc = c4.text_input("Descrição (Ex: Jantar, Compra Amazon)")
            valor = c5.number_input("Valor Total (R$)", 0.0, step=10.0)

            st.divider()
            
            # LINHA 3: Pagamento & Parcelamento (CORRIGIDO)
            c6, c7, c8 = st.columns(3)
            
            # Lógica de Pagamento
            # Se o tipo for Cartão, forçamos o pagamento a ser Crédito
            idx_pag = 0
            opcoes_pag = ["Crédito", "Débito", "Pix", "Dinheiro", "Automático"]
            if tipo == "Cartao":
                idx_pag = 0 # Crédito
            
            pagamento = c6.selectbox("Forma de Pagamento", opcoes_pag, index=idx_pag)
            
            # Lógica do Seletor de Cartão
            # Mostra se for Tipo Cartão OU se Pagamento for Crédito
            cartao_selecionado = ""
            if tipo == "Cartao" or pagamento == "Crédito":
                lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
                if lista_cartoes:
                    cartao_selecionado = c7.selectbox("Qual Cartão?", lista_cartoes)
                else:
                    # FALLBACK: Se não tiver cartão cadastrado, deixa digitar para não travar
                    cartao_selecionado = c7.text_input("Nome do Cartão (Digite)", placeholder="Ex: Nubank")
            else:
                c7.caption("🚫 Sem cartão vinculado")

            # Parcelas (SEMPRE VISÍVEL AGORA)
            parcelas = c8.number_input("Qtd. Parcelas", min_value=1, max_value=60, value=1, help="Deixe 1 se for à vista")

            # Checkbox de Recorrência
            is_rec = st.checkbox("É uma conta fixa mensal? (Recorrente)", value=(True if tipo == "Despesa Fixa" else False))

            if st.form_submit_button("💾 Salvar Lançamento", type="primary"):
                novo = {
                    "Data": dt,
                    "Tipo": tipo, 
                    "Categoria": categ, 
                    "Descricao": desc,
                    "Valor_Total": valor, 
                    "Pagamento": pagamento, 
                    "Qtd_Parcelas": parcelas,
                    "Recorrente": is_rec,
                    "Cartao_Ref": cartao_selecionado
                }
                
                # Consolidação
                df_trans = pd.concat([df_trans, pd.DataFrame([novo])], ignore_index=True)
                save_data(df_trans, "Transacoes")
                st.success(f"✅ Lançamento salvo! ({desc} - {parcelas}x)")
                st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: EXTRATO (AUDITORIA)
    # ------------------------------------------------------------------
    with tab_extrato:
        st.subheader("🕵️ Extrato Completo")
        if df_trans.empty:
            st.warning("Nenhum lançamento registrado.")
        else:
            # Filtros
            c_fil1, c_fil2 = st.columns(2)
            mes_filter = c_fil1.date_input("Filtrar por Mês", date.today())
            
            df_view = df_trans.copy()
            # Tratamento de erro de data antes de filtrar
            df_view = df_view.dropna(subset=['Data'])
            
            df_view = df_view[
                (df_view['Data'].dt.month == mes_filter.month) & 
                (df_view['Data'].dt.year == mes_filter.year)
            ]
            
            # Cards de Resumo
            ent = df_view[df_view['Tipo'] == 'Receita']['Valor_Total'].sum()
            sai = df_view[df_view['Tipo'] != 'Receita']['Valor_Total'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Entradas", f"R$ {ent:,.2f}")
            k2.metric("Saídas", f"R$ {sai:,.2f}")
            k3.metric("Saldo Líquido", f"R$ {ent - sai:,.2f}")

            # Tabela Editável (Para visualização rápida)
            st.dataframe(
                df_view.sort_values("Data", ascending=False),
                column_config={
                    "Valor_Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "Qtd_Parcelas": st.column_config.NumberColumn("Parc.", format="%d"),
                },
                use_container_width=True,
                hide_index=True
            )
            
            # Botão de Exclusão
            with st.expander("🗑️ Excluir Lançamento"):
                if not df_view.empty:
                    # Cria uma string única para identificar (Descricao + Valor)
                    df_view['Label'] = df_view['Descricao'] + " (R$ " + df_view['Valor_Total'].astype(str) + ")"
                    item_to_del = st.selectbox("Selecione o item:", df_view['Label'].unique())
                    
                    if st.button("Confirmar Exclusão"):
                        # Busca o item original na base completa
                        mask = (df_trans['Descricao'] + " (R$ " + df_trans['Valor_Total'].astype(str) + ")") == item_to_del
                        idx_del = df_trans[mask].index
                        
                        if not idx_del.empty:
                            df_trans = df_trans.drop(idx_del)
                            save_data(df_trans, "Transacoes")
                            st.success("Item removido.")
                            st.rerun()

    # ------------------------------------------------------------------
    # ABA 3: ORGANIZADOR
    # ------------------------------------------------------------------
    with tab_org:
        st.subheader("⚖️ Organizador de Salário")
        col_sal, col_dummy = st.columns([2, 1])
        salario_entrada = col_sal.number_input("Valor da Entrada", value=3000.0, step=100.0)
        
        with st.expander("⚙️ Configurar % (50/30/20)"):
            c_ess, c_inv, c_laz = st.columns(3)
            p_ess = c_ess.number_input("% Essencial", 0, 100, 50)
            p_inv = c_inv.number_input("% Investimentos", 0, 100, 30)
            p_laz = c_laz.number_input("% Lazer", 0, 100, 20)

        v_ess = salario_entrada * (p_ess/100)
        v_inv = salario_entrada * (p_inv/100)
        v_laz = salario_entrada * (p_laz/100)
        
        m1, m2, m3 = st.columns(3)
        m1.metric("🏠 Contas Fixas", f"R$ {v_ess:,.2f}")
        m2.metric("🚀 Futuro", f"R$ {v_inv:,.2f}")
        m3.metric("🎉 Gastar", f"R$ {v_laz:,.2f}")
        
        st.divider()
        st.markdown("#### 🎯 Alocar em Metas")
        
        if df_metas.empty:
            st.info("Cadastre metas na aba 'Projetos & Metas' para usar esta função.")
        else:
            soma_metas = df_metas['Meta_Valor'].sum()
            for idx, row in df_metas.iterrows():
                # Sugestão de aporte proporcional
                perc_meta = (row['Meta_Valor'] / soma_metas) if soma_metas > 0 else 0
                sugestao = v_inv * perc_meta
                
                with st.container(border=True):
                    cm1, cm2, cm3 = st.columns([2, 1, 1])
                    cm1.markdown(f"**{row['Titulo']}**")
                    aporte = cm2.number_input(f"Valor", value=float(f"{sugestao:.2f}"), key=f"ap_{row['ID']}")
                    
                    if cm3.button("Alocar", key=f"btn_alo_{row['ID']}"):
                        novo_inv = {
                            "Data": date.today(), "Tipo": "Investimento", "Categoria": "Metas",
                            "Descricao": f"Aporte: {row['Titulo']}", "Valor_Total": aporte,
                            "Pagamento": "Pix", "Qtd_Parcelas": 1, "Recorrente": False, "Cartao_Ref": ""
                        }
                        df_trans = pd.concat([df_trans, pd.DataFrame([novo_inv])], ignore_index=True)
                        save_data(df_trans, "Transacoes")
                        
                        df_metas.loc[idx, 'Progresso_Manual'] += aporte
                        conexoes.save_gsheet("Metas", df_metas)
                        st.toast(f"Alocado em {row['Titulo']}!")

    # ------------------------------------------------------------------
    # ABA 4: PROJEÇÃO
    # ------------------------------------------------------------------
    with tab_proj:
        st.subheader("🔮 Futuro das Parcelas")
        
        # Filtra apenas o que é cartão parcelado para o gráfico
        if not df_trans.empty:
            futuro = []
            hoje = date.today()
            
            # Filtra onde tem parcela > 1 e Tipo Cartao
            df_parcelados = df_trans[(df_trans['Tipo'] == 'Cartao') & (df_trans['Qtd_Parcelas'] > 1)].dropna(subset=['Data'])
            
            for _, row in df_parcelados.iterrows():
                try:
                    valor_p = row['Valor_Total'] / row['Qtd_Parcelas']
                    dt_compra = row['Data'].date()
                    
                    for i in range(int(row['Qtd_Parcelas'])):
                        dt_venc = dt_compra + relativedelta(months=i)
                        # Só mostra o que vence no futuro
                        if dt_venc > hoje:
                            futuro.append({
                                "Data": dt_venc, 
                                "Valor": valor_p, 
                                "Cartão": str(row['Cartao_Ref'])
                            })
                except: continue

            df_fut = pd.DataFrame(futuro)
            if not df_fut.empty:
                df_fut['Mes'] = pd.to_datetime(df_fut['Data']).dt.strftime('%Y-%m')
                st.bar_chart(df_fut, x="Mes", y="Valor", color="Cartão")
            else:
                st.success("Você não tem dívidas parceladas futuras no cartão!")