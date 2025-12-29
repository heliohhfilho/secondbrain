import streamlit as st
import pandas as pd
from datetime import date
import os
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols = ["Item", "Categoria", "Valor_Est", "Prioridade", "Link", "Status", "Data_Add"]
    df = conexoes.load_gsheet("Compras", cols)
    if not df.empty:
        df["Valor_Est"] = pd.to_numeric(df["Valor_Est"], errors='coerce').fillna(0.0)
    return df

def load_cartoes():
    # Puxa os nomes dos cartões cadastrados na nuvem
    df_c = conexoes.load_gsheet("Cartoes", ["Nome"])
    return df_c['Nome'].tolist() if not df_c.empty else []

def save_data(df):
    conexoes.save_gsheet("Compras", df)

def lancar_no_financeiro(item, valor, parcelas, pagamento, cartao_ref=None):
    # Puxa a aba de transações atualizada
    cols_f = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_fin = conexoes.load_gsheet("Transacoes", cols_f)
    
    novo = {
        "Data": str(date.today()), 
        "Tipo": "Cartao" if pagamento == "Crédito" else "Despesa Fixa", 
        "Categoria": "Compras/Wishlist", 
        "Descricao": f"Compra: {item}", 
        "Valor_Total": float(valor), 
        "Pagamento": pagamento, 
        "Qtd_Parcelas": int(parcelas), 
        "Recorrente": "False",
        "Cartao_Ref": cartao_ref
    }
    
    df_updated = pd.concat([df_fin, pd.DataFrame([novo])], ignore_index=True)
    conexoes.save_gsheet("Transacoes", df_updated)
    return True

def get_financial_snapshot():
    receita_media = 0.0
    sobra_caixa = 0.0
    renda_passiva = 0.0
    
    # 1. Fluxo de Caixa (da Nuvem)
    df_t = conexoes.load_gsheet("Transacoes", ["Data", "Tipo", "Valor_Total"])
    if not df_t.empty:
        df_t['Valor_Total'] = pd.to_numeric(df_t['Valor_Total'], errors='coerce').fillna(0.0)
        df_t['Data'] = pd.to_datetime(df_t['Data'], errors='coerce')
        start_date = pd.Timestamp.now() - pd.Timedelta(days=90)
        df_recent = df_t[df_t['Data'] >= start_date]
        
        if not df_recent.empty:
            receitas = df_recent[df_recent['Tipo'] == 'Receita']['Valor_Total'].sum()
            despesas = df_recent[df_recent['Tipo'].isin(['Despesa Fixa', 'Cartao', 'Emprestimo'])]['Valor_Total'].sum()
            meses = max(1, df_recent['Data'].dt.to_period('M').nunique())
            receita_media = receitas / meses
            sobra_caixa = (receitas - despesas) / meses

    # 2. Renda Passiva (da Nuvem)
    df_i = conexoes.load_gsheet("Investimentos", ["Qtd", "DY_Mensal", "Total_Atual", "Preco_Unitario"])
    if not df_i.empty:
        for col in df_i.columns: df_i[col] = pd.to_numeric(df_i[col], errors='coerce').fillna(0.0)
        
        if 'DY_Mensal' in df_i.columns and df_i['DY_Mensal'].sum() > 0:
            renda_passiva = (df_i['Qtd'] * df_i['DY_Mensal']).sum()
        else:
            # Estimativa técnica baseada em patrimônio total
            total_patrimonio = df_i['Total_Atual'].sum() if 'Total_Atual' in df_i.columns else (df_i['Qtd'] * df_i['Preco_Unitario']).sum()
            renda_passiva = total_patrimonio * 0.008

    return receita_media, sobra_caixa, renda_passiva

def render_page():
    st.header("🛍️ Gestão de Desejos & Impacto")
    
    df = load_data()
    lista_cartoes = load_cartoes()
    rec_med, sobra_med, renda_pass = get_financial_snapshot()
    
    with st.expander("📊 Poder de Compra (Diagnóstico)", expanded=True):
        c1, c2 = st.columns(2)
        c1.metric("Sobra Mensal (Média)", f"R$ {sobra_med:,.2f}")
        c2.metric("Renda Passiva (Mês)", f"R$ {renda_pass:,.2f}")
        if sobra_med < 0:
            st.error("⚠️ Atenção: Você está gastando mais do que ganha!")

    with st.sidebar:
        st.subheader("➕ Novo Desejo")
        with st.form("add_compra"):
            c_item = st.text_input("Item")
            c_cat = st.selectbox("Categoria", ["Eletrônicos", "Moda", "Casa", "Hobby", "Outros"])
            c_val = st.number_input("Preço (R$)", 0.0)
            c_prio = st.select_slider("Prioridade", ["Baixa", "Média", "Alta", "CRÍTICA"])
            c_link = st.text_input("Link")
            
            if st.form_submit_button("Adicionar"):
                novo = {
                    "Item": c_item, "Categoria": c_cat, "Valor_Est": c_val,
                    "Prioridade": c_prio, "Link": c_link, "Status": "Pendente",
                    "Data_Add": str(date.today())
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Sincronizado!")
                st.rerun()

    st.divider()
    t1, t2 = st.tabs(["🛒 Lista de Desejos", "✅ Histórico"])
    
    with t1:
        if not df.empty:
            pendentes = df[df['Status'] == "Pendente"].copy()
            prio_map = {"CRÍTICA": 0, "Alta": 1, "Média": 2, "Baixa": 3}
            pendentes['Prio_Sort'] = pendentes['Prioridade'].map(prio_map)
            pendentes = pendentes.sort_values("Prio_Sort")
            
            for idx, row in pendentes.iterrows():
                val_item = row['Valor_Est']
                impacto_vista = (val_item / sobra_med * 100) if sobra_med > 0 else 100
                
                with st.container(border=True):
                    c_main, c_impact, c_act = st.columns([3, 2, 1.5])
                    
                    cor = "red" if row['Prioridade'] == "CRÍTICA" else "orange" if row['Prioridade'] == "Alta" else "green"
                    c_main.markdown(f"**:{cor}[{row['Prioridade']}]** | **{row['Item']}**")
                    c_main.caption(f"R$ {val_item:,.2f} | {row['Categoria']}")
                    
                    c_impact.progress(min(impacto_vista/100, 1.0), text=f"Impacto: {impacto_vista:.0f}%")
                    
                    with c_act.popover("🛍️ Comprar"):
                        p_metodo = st.selectbox("Forma", ["Crédito", "Pix", "Débito"], key=f"pg_{idx}")
                        p_parc = 1
                        p_card = None
                        
                        if p_metodo == "Crédito":
                            p_parc = st.number_input("Parcelas", 1, 24, 1, key=f"pc_{idx}")
                            p_card = st.selectbox("Cartão", lista_cartoes, key=f"cd_{idx}")
                        
                        if st.button("Confirmar", key=f"btn_buy_{idx}"):
                            df.loc[df.index == idx, 'Status'] = "Comprado"
                            save_data(df)
                            lancar_no_financeiro(row['Item'], val_item, p_parc, p_metodo, p_card)
                            st.toast("Lançado no Financeiro!", icon="🎉")
                            st.rerun()
                            
                    if c_act.button("🗑️", key=f"del_{idx}"):
                        save_data(df.drop(idx))
                        st.rerun()
        else:
            st.info("Lista vazia.")

    with t2:
        comprados = df[df['Status'] == "Comprado"]
        if not comprados.empty:
            for idx, row in comprados.iterrows():
                with st.container(border=True):
                    c1, c2 = st.columns([4, 1])
                    c1.markdown(f"~~{row['Item']}~~ (R$ {row['Valor_Est']:,.2f})")
                    if c2.button("↩️", key=f"undo_{idx}"):
                        df.loc[idx, 'Status'] = "Pendente"
                        save_data(df)
                        st.rerun()