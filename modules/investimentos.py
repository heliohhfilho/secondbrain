import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import date
from dateutil.relativedelta import relativedelta
import os

from modules import conexoes

def load_data():
    # 1. Investimentos
    cols_inv = ["Ativo", "Tipo", "Qtd", "Preco_Unitario", "Total_Pago", "Data_Compra", "DY_Mensal", "Total_Atual"]
    df_i = conexoes.load_gsheet("Investimentos", cols_inv)
    
    if not df_i.empty:
        # Saneamento forçado para cálculos
        for col in ["Qtd", "Preco_Unitario", "Total_Pago", "DY_Mensal", "Total_Atual"]:
            if col in df_i.columns:
                df_i[col] = pd.to_numeric(df_i[col], errors='coerce').fillna(0.0)
        df_i['Total_Atual'] = df_i['Qtd'] * df_i['Preco_Unitario']

    # 2. Transações
    cols_trans = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Qtd_Parcelas", "Recorrente", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_trans)
    if not df_t.empty:
        df_t["Valor_Total"] = pd.to_numeric(df_t["Valor_Total"], errors='coerce').fillna(0.0)

    return df_i, df_t

def save_data(df_inv, df_trans=None):
    # Converte datas para string antes de enviar para a nuvem
    df_inv_save = df_inv.copy()
    if "Data_Compra" in df_inv_save.columns:
        df_inv_save["Data_Compra"] = df_inv_save["Data_Compra"].astype(str)
        
    conexoes.save_gsheet("Investimentos", df_inv_save)
    
    if df_trans is not None:
        df_trans_save = df_trans.copy()
        if "Data" in df_trans_save.columns:
            df_trans_save["Data"] = df_trans_save["Data"].astype(str)
        conexoes.save_gsheet("Transacoes", df_trans_save)

def calcular_medias_financeiras(df_trans):
    if df_trans.empty: return 3000.0, 500.0
    
    # --- CORREÇÃO DO ERRO DE DATA AQUI ---
    # errors='coerce' transforma datas inválidas em NaT (Not a Time) sem travar
    df_trans['Data'] = pd.to_datetime(df_trans['Data'], errors='coerce')
    
    # Remove linhas onde a data não pôde ser lida
    df_trans = df_trans.dropna(subset=['Data'])
    
    start_date = pd.Timestamp.now() - pd.Timedelta(days=180)
    df_recent = df_trans[df_trans['Data'] >= start_date]
    
    gastos = df_recent[df_recent['Tipo'].isin(['Despesa Fixa', 'Cartao', 'Emprestimo'])]
    media_custo = gastos.groupby(gastos['Data'].dt.to_period('M'))['Valor_Total'].sum().mean() if not gastos.empty else 3000.0
    
    aportes = df_recent[(df_recent['Tipo'] == 'Aporte Investimento') | (df_recent['Categoria'] == 'Investimento')]
    media_aporte = aportes.groupby(aportes['Data'].dt.to_period('M'))['Valor_Total'].sum().mean() if not aportes.empty else 500.0
    
    return abs(media_custo), abs(media_aporte)

def render_page():
    st.header("🧠 Inteligência de Investimentos & FIRE")
    
    df_inv, df_trans = load_data()
    media_custo_vida, media_aporte_real = calcular_medias_financeiras(df_trans)
    patrimonio_total = df_inv['Total_Atual'].sum()
    
    with st.sidebar:
        st.header("⚙️ Estratégia")
        with st.expander("1. Divisão da Renda", expanded=True):
            meta_invest = st.slider("Investimento", 0, 100, 30, 5)
            meta_custo = st.slider("Custo de Vida", 0, 100, 50, 5)
            meta_lazer = st.slider("Lazer/Sonhos", 0, 100, 20, 5)
        with st.expander("2. Alocação", expanded=True):
            target_fii = st.slider("Target FIIs (%)", 0, 100, 50, 5)
            target_cdi = st.slider("Target Renda Fixa (%)", 0, 100, 100-target_fii, 5)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patrimônio Total", f"R$ {patrimonio_total:,.2f}")
    c2.metric("Custo Médio", f"R$ {media_custo_vida:,.2f}")
    c3.metric("Aporte Médio", f"R$ {media_aporte_real:,.2f}")
    
    renda_passiva_est = patrimonio_total * 0.008 
    cob_fire = (renda_passiva_est / media_custo_vida * 100) if media_custo_vida > 0 else 0
    c4.metric("FIRE (%)", f"{cob_fire:.1f}%", f"R$ {renda_passiva_est:,.0f}/mês")

    st.divider()
    tab_rebal, tab_fire, tab_crud = st.tabs(["⚖️ Rebalanceamento", "🔮 Simulador FIRE", "📝 Carteira Manual"])

    with tab_rebal:
        st.subheader("Onde eu aporto hoje?")
        df_inv['Macro_Tipo'] = df_inv['Tipo'].apply(lambda x: 'FII' if x in ['FII', 'Ação'] else 'Renda Fixa')
        posicao_macro = df_inv.groupby('Macro_Tipo')['Total_Atual'].sum().reset_index()
        
        # Proteção contra carteira vazia
        val_fii = posicao_macro[posicao_macro['Macro_Tipo'] == 'FII']['Total_Atual'].sum() if not posicao_macro.empty else 0
        val_cdi = posicao_macro[posicao_macro['Macro_Tipo'] == 'Renda Fixa']['Total_Atual'].sum() if not posicao_macro.empty else 0
        
        ideal_fii = patrimonio_total * (target_fii / 100)
        delta_fii = ideal_fii - val_fii
        delta_cdi = (patrimonio_total * (target_cdi / 100)) - val_cdi
        
        c_vis, c_act = st.columns([1, 2])
        with c_vis:
            if patrimonio_total > 0:
                fig = px.pie(values=[val_fii, val_cdi], names=['FIIs/Ações', 'Renda Fixa'])
                st.plotly_chart(fig, width=True)
            else:
                st.info("Sem dados.")
        with c_act:
            if delta_fii > 0: st.success(f"✅ COMPRAR FIIs! Aporte sugerido: R$ {delta_fii:,.2f}")
            elif delta_cdi > 0: st.info(f"🔹 COMPRAR RENDA FIXA! Aporte sugerido: R$ {delta_cdi:,.2f}")
            else: st.write("Carteira balanceada.")

        st.divider()
        st.subheader("🔬 Raio-X dos FIIs")
        fiis = df_inv[df_inv['Macro_Tipo'] == 'FII'].copy()
        if not fiis.empty:
            carteira_fiis = fiis.groupby('Ativo').agg({'Qtd':'sum', 'Total_Atual':'sum', 'Preco_Unitario':'mean'}).reset_index()
            meta_por_ativo = ideal_fii / max(1, len(carteira_fiis))
            carteira_fiis['Falta ($)'] = meta_por_ativo - carteira_fiis['Total_Atual']
            carteira_fiis['Comprar (Qtd)'] = (carteira_fiis['Falta ($)'] / carteira_fiis['Preco_Unitario'].replace(0, 1)).apply(np.ceil)
            sugestao = carteira_fiis[carteira_fiis['Falta ($)'] > 0].sort_values('Falta ($)', ascending=False)
            if not sugestao.empty: st.dataframe(sugestao[['Ativo', 'Total_Atual', 'Falta ($)', 'Comprar (Qtd)']], hide_index=True, width=True)
            else: st.success("FIIs balanceados.")

    with tab_fire:
        st.subheader("🔮 Quando eu paro de trabalhar?")
        c_s1, c_s2 = st.columns(2)
        sim_ap = c_s1.number_input("Aporte Mensal Simulado", value=float(media_aporte_real))
        sim_cus = c_s2.number_input("Custo de Vida Futuro", value=float(media_custo_vida))
        magico = sim_cus * 300
        if patrimonio_total < magico:
            st.metric("Número Mágico (300x)", f"R$ {magico:,.2f}")
            taxa_mensal = (1 + 0.06)**(1/12) - 1
            saldo = patrimonio_total
            meses = 0
            dados_graf = []
            while saldo < magico and meses < 600:
                saldo += (saldo * taxa_mensal) + sim_ap
                meses += 1
                if meses % 6 == 0: dados_graf.append({"Meses": meses, "Saldo": saldo, "Meta": magico})
            st.success(f"Liberdade em {meses//12} anos e {meses%12} meses.")
            if dados_graf: st.line_chart(pd.DataFrame(dados_graf), x="Meses", y=["Saldo", "Meta"])
        else: st.balloons(); st.success("Você já atingiu a liberdade financeira!")

    with tab_crud:
        st.subheader("📝 Adicionar e Registrar no Financeiro")
        with st.form("add_inv"):
            c1, c2, c3, c4 = st.columns(4)
            n_ativo = c1.text_input("Ativo").upper()
            n_tipo = c2.selectbox("Tipo", ["FII", "Ação", "Renda Fixa", "CDI", "Cripto"])
            n_qtd = c3.number_input("Qtd", 0.0, step=1.0)
            n_preco = c4.number_input("Preço Pago", 0.0, step=0.01)
            
            if st.form_submit_button("Adicionar Aporte"):
                valor_total = n_qtd * n_preco
                # 1. Investimentos
                novo_inv = {
                    "Ativo": n_ativo, "Tipo": n_tipo, "Qtd": n_qtd, 
                    "Preco_Unitario": n_preco, "Total_Pago": valor_total, 
                    "Data_Compra": date.today()
                }
                df_inv = pd.concat([df_inv, pd.DataFrame([novo_inv])], ignore_index=True)
                
                # 2. Financeiro
                nova_trans = {
                    "Data": date.today(), 
                    "Tipo": "Aporte Investimento", 
                    "Categoria": "Investimentos", 
                    "Descricao": f"Compra {n_ativo} ({n_qtd}x)", 
                    "Valor_Total": valor_total, 
                    "Pagamento": "Pix", 
                    "Qtd_Parcelas": 1, 
                    "Recorrente": False,
                    "Cartao_Ref": None
                }
                df_trans = pd.concat([df_trans, pd.DataFrame([nova_trans])], ignore_index=True)
                
                save_data(df_inv, df_trans)
                st.success("Aporte registrado!")
                st.rerun()
        
        st.write("Edição Rápida")
        df_edit = st.data_editor(df_inv, num_rows="dynamic")
        if st.button("Salvar Edições"):
            df_edit['Total_Atual'] = df_edit['Qtd'] * df_edit['Preco_Unitario']
            save_data(df_edit) 
            st.rerun()