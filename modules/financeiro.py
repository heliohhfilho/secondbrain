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
    if "Data" in df_s.columns: 
        df_s["Data"] = pd.to_datetime(df_s["Data"], errors='coerce').dt.strftime('%Y-%m-%d').fillna(str(date.today()))
    conexoes.save_gsheet(aba, df_s)

# --- ENGINE FINANCEIRA ---
def render_page():
    st.header("💎 Central Financeira Definitiva")
    df_trans, df_cards, df_metas, df_loans = load_data()

    tab_lan, tab_extrato, tab_org, tab_proj = st.tabs(["📝 Lançar (Formulário)", "🔎 Extrato (Fluxo)", "💰 Organizador", "🔮 Projeção"])

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
            valor = c5.number_input("Valor Total (R$)", 0.0, step=10.0, help="Coloque o valor TOTAL da compra. Se for parcelado, o sistema divide automaticamente.")

            st.divider()
            
            # LINHA 3: Pagamento & Parcelamento
            c6, c7, c8 = st.columns(3)
            
            idx_pag = 0
            opcoes_pag = ["Crédito", "Débito", "Pix", "Dinheiro", "Automático"]
            if tipo == "Cartao": idx_pag = 0 
            pagamento = c6.selectbox("Forma de Pagamento", opcoes_pag, index=idx_pag)
            
            cartao_selecionado = ""
            if tipo == "Cartao" or pagamento == "Crédito":
                lista_cartoes = df_cards['Nome'].unique().tolist() if not df_cards.empty else []
                if lista_cartoes:
                    cartao_selecionado = c7.selectbox("Qual Cartão?", lista_cartoes)
                else:
                    cartao_selecionado = c7.text_input("Nome do Cartão", placeholder="Ex: Nubank")
            else:
                c7.caption("🚫 Sem cartão vinculado")

            parcelas = c8.number_input("Qtd. Parcelas", min_value=1, max_value=60, value=1)

            is_rec = st.checkbox("É recorrente?", value=(True if tipo == "Despesa Fixa" else False))

            if st.form_submit_button("💾 Salvar Lançamento", type="primary"):
                novo = {
                    "Data": dt, "Tipo": tipo, "Categoria": categ, "Descricao": desc,
                    "Valor_Total": valor, "Pagamento": pagamento, "Qtd_Parcelas": parcelas,
                    "Recorrente": is_rec, "Cartao_Ref": cartao_selecionado
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([novo])], ignore_index=True)
                save_data(df_trans, "Transacoes")
                st.success(f"✅ Lançamento salvo! ({desc} - {parcelas}x)")
                st.rerun()

    # ------------------------------------------------------------------
    # ABA 2: EXTRATO (CORRIGIDO: VISÃO DE PARCELA)
    # ------------------------------------------------------------------
    with tab_extrato:
        st.subheader("🕵️ Extrato do Mês")
        if df_trans.empty:
            st.warning("Nenhum lançamento registrado.")
        else:
            # Filtros
            c_fil1, c_fil2 = st.columns(2)
            mes_filter = c_fil1.date_input("Filtrar por Mês", date.today())
            
            df_view = df_trans.copy()
            df_view = df_view.dropna(subset=['Data'])
            
            # Filtra pelo mês selecionado
            df_view = df_view[
                (df_view['Data'].dt.month == mes_filter.month) & 
                (df_view['Data'].dt.year == mes_filter.year)
            ]
            
            # --- CORREÇÃO DE ENGENHARIA AQUI ---
            # Cria coluna de "Valor Efetivo (Mês)" para o cálculo bater
            # Se parcelas > 1, o impacto no mês é Valor_Total / Parcelas
            df_view['Impacto_Mes'] = df_view.apply(
                lambda x: x['Valor_Total'] / x['Qtd_Parcelas'] if x['Qtd_Parcelas'] > 1 else x['Valor_Total'], axis=1
            )
            
            # Cálculos baseados no Impacto Mensal e não no Total Contratado
            ent = df_view[df_view['Tipo'] == 'Receita']['Impacto_Mes'].sum()
            # Saídas: Tudo que não é Receita
            sai = df_view[df_view['Tipo'] != 'Receita']['Impacto_Mes'].sum()
            
            k1, k2, k3 = st.columns(3)
            k1.metric("Entradas", f"R$ {ent:,.2f}")
            k2.metric("Saídas (Real)", f"R$ {sai:,.2f}", help="Soma das parcelas e gastos à vista deste mês")
            k3.metric("Saldo Líquido", f"R$ {ent - sai:,.2f}")

            st.caption("Nota: Compras parceladas mostram o valor da parcela nesta tabela para facilitar seu fluxo de caixa.")
            
            st.dataframe(
                df_view.sort_values("Data", ascending=False),
                column_config={
                    "Impacto_Mes": st.column_config.NumberColumn("Valor (Mês)", format="R$ %.2f"),
                    "Valor_Total": st.column_config.NumberColumn("Valor Total", format="R$ %.2f"),
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY"),
                    "Qtd_Parcelas": st.column_config.NumberColumn("Parc.", format="%d"),
                },
                column_order=["Data", "Descricao", "Categoria", "Impacto_Mes", "Valor_Total", "Qtd_Parcelas", "Tipo", "Cartao_Ref"],
                use_container_width=True,
                hide_index=True
            )
            
            # Botão de Exclusão
            with st.expander("🗑️ Excluir Lançamento"):
                if not df_view.empty:
                    df_view['Label'] = df_view['Descricao'] + " (Total: R$ " + df_view['Valor_Total'].astype(str) + ")"
                    item_to_del = st.selectbox("Selecione o item:", df_view['Label'].unique())
                    
                    if st.button("Confirmar Exclusão"):
                        # Logica reversa para achar o ID correto
                        mask = (df_trans['Descricao'] + " (Total: R$ " + df_trans['Valor_Total'].astype(str) + ")") == item_to_del
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
        if not df_trans.empty:
            futuro = []
            hoje = date.today()
            
            df_parcelados = df_trans[(df_trans['Tipo'] == 'Cartao') & (df_trans['Qtd_Parcelas'] > 1)].dropna(subset=['Data'])
            
            for _, row in df_parcelados.iterrows():
                try:
                    valor_p = row['Valor_Total'] / row['Qtd_Parcelas']
                    dt_compra = row['Data'].date()
                    for i in range(int(row['Qtd_Parcelas'])):
                        dt_venc = dt_compra + relativedelta(months=i)
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