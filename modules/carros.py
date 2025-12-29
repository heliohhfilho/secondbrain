import streamlit as st
import pandas as pd
import numpy as np
from datetime import date
import os
import math
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols = [
        "ID", "Marca", "Modelo", "Ano", "Versao", "KM", "Cambio", 
        "Valor_Oferta", "Valor_FIPE", "Link", "Status", "Data_Add"
    ]
    df = conexoes.load_gsheet("Carros", cols)
    
    # Saneamento de tipos para cálculos
    if not df.empty:
        df["Valor_Oferta"] = pd.to_numeric(df["Valor_Oferta"], errors='coerce').fillna(0.0)
        df["Valor_FIPE"] = pd.to_numeric(df["Valor_FIPE"], errors='coerce').fillna(0.0)
        df["KM"] = pd.to_numeric(df["KM"], errors='coerce').fillna(0).astype(int)
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
    return df

def save_data(df):
    conexoes.save_gsheet("Carros", df)

def calcular_custos_anuais(valor_carro):
    ipva = valor_carro * 0.02  # Média 2% (Ajustado conforme seu comentário no código)
    seguro = valor_carro * 0.05 
    manutencao = valor_carro * 0.03 
    total_anual = ipva + seguro + manutencao
    return ipva, seguro, manutencao, total_anual

def calcular_financiamento(valor, entrada, taxa_mes, meses):
    saldo_devedor = valor - entrada
    if saldo_devedor <= 0: return 0.0, valor, 0.0
    
    i = taxa_mes / 100
    if i == 0: return saldo_devedor / meses, saldo_devedor, 0.0
    
    # Fórmula Price (PMT)
    parcela = saldo_devedor * ( (i * (1+i)**meses) / ((1+i)**meses - 1) )
    total_pago = (parcela * meses) + entrada
    total_juros = (parcela * meses) - saldo_devedor
    return parcela, total_pago, total_juros

def get_renda_mensal_media():
    # Puxa as transações também da nuvem para manter a integridade
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    if df_t.empty: return 5000.0
    
    df_t['Valor_Total'] = pd.to_numeric(df_t['Valor_Total'], errors='coerce').fillna(0.0)
    df_t['Data'] = pd.to_datetime(df_t['Data'], errors='coerce')
    
    df_rec = df_t[df_t['Tipo'] == 'Receita']
    if df_rec.empty: return 5000.0
    
    total = df_rec['Valor_Total'].sum()
    meses = df_t['Data'].dt.to_period('M').nunique()
    return total / max(1, meses)

def render_page():
    st.header("🏎️ Garagem & Sonhos Automotivos")
    st.caption("Análise técnica e financeira da sua próxima nave.")
    
    df = load_data()
    renda_media = get_renda_mensal_media()
    
    with st.expander("⚙️ Configurações de Mercado"):
        c1, c2 = st.columns(2)
        meta_gasto_carro_perc = c1.slider("Meta: % da Renda para Carro", 5, 50, 20)
        taxa_juros_padrao = c2.number_input("Taxa de Juros Financiamento (% a.m.)", 0.1, 5.0, 1.89)
        teto_gasto_mensal = renda_media * (meta_gasto_carro_perc / 100)
        st.info(f"Renda Média: **R$ {renda_media:,.2f}** | Teto Mensal Carro: **R$ {teto_gasto_mensal:,.2f}**")

    with st.sidebar:
        st.subheader("➕ Cadastrar Carro")
        with st.form("form_carro"):
            c_marca = st.text_input("Marca")
            c_modelo = st.text_input("Modelo")
            c_ano = st.number_input("Ano", 1950, 2026, 2015)
            c_versao = st.text_input("Versão")
            c_km = st.number_input("KM", 0, 500000, 80000)
            c_cambio = st.selectbox("Câmbio", ["Manual", "Automático", "CVT", "Dupla Embreagem"])
            c_valor = st.number_input("Valor Pedido (R$)", 0.0)
            c_fipe = st.number_input("Tabela FIPE (R$)", 0.0)
            c_link = st.text_input("Link do Anúncio")
            
            if st.form_submit_button("Estacionar na Garagem"):
                new_id = 1 if df.empty else int(df['ID'].max()) + 1
                novo = {
                    "ID": new_id, "Marca": c_marca, "Modelo": c_modelo, 
                    "Ano": c_ano, "Versao": c_versao, "KM": c_km, "Cambio": c_cambio,
                    "Valor_Oferta": c_valor, "Valor_FIPE": c_fipe, 
                    "Link": c_link, "Status": "Analisando", "Data_Add": str(date.today())
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Carro cadastrado na nuvem!")
                st.rerun()

    if df.empty:
        st.info("Sua garagem está vazia.")
        return

    st.divider()
    carros_ativos = df[df['Status'] == "Analisando"]
    
    for idx, row in carros_ativos.iterrows():
        with st.container(border=True):
            col_img, col_dados, col_fin = st.columns([1, 2, 2])
            
            with col_img:
                st.markdown(f"### {row['Marca']}")
                st.markdown(f"**{row['Modelo']}**")
                st.caption(f"{row['Ano']} | {row['KM']} km")
                if row['Link']: st.markdown(f"[Anúncio]({row['Link']})")
                
                if st.button("🗑️ Remover", key=f"del_car_{row['ID']}"):
                    df = df[df['ID'] != row['ID']]
                    save_data(df)
                    st.rerun()

            with col_dados:
                st.markdown("#### 💰 Preço vs FIPE")
                delta_fipe = row['Valor_Oferta'] - row['Valor_FIPE']
                perc_fipe = (delta_fipe / row['Valor_FIPE'] * 100) if row['Valor_FIPE'] > 0 else 0
                
                c1, c2 = st.columns(2)
                c1.metric("Pedido", f"R$ {row['Valor_Oferta']:,.0f}")
                c2.metric("FIPE", f"R$ {row['Valor_FIPE']:,.0f}", f"{perc_fipe:+.1f}%", delta_color="normal" if delta_fipe <= 0 else "inverse")
                
                ipva, seg, manut, total_anual = calcular_custos_anuais(row['Valor_FIPE'])
                st.caption(f"Custo Mensal Estimado (IPVA/Seg/Man): **R$ {total_anual/12:,.0f}**")

            with col_fin:
                st.markdown("#### 🏦 Simulação")
                entrada = st.number_input("Entrada (R$)", 0.0, float(row['Valor_Oferta']), float(row['Valor_Oferta'])*0.3, key=f"ent_{row['ID']}")
                meses = st.selectbox("Parcelas", [12, 24, 36, 48, 60], index=2, key=f"mes_{row['ID']}")
                
                parcela, total_pagar, juros_pagos = calcular_financiamento(row['Valor_Oferta'], entrada, taxa_juros_padrao, meses)
                custo_mensal_total = parcela + (total_anual/12)
                
                comprometimento = (custo_mensal_total / renda_media) * 100
                
                if custo_mensal_total <= teto_gasto_mensal:
                    st.success(f"✅ Dentro da Meta ({comprometimento:.1f}%)")
                else:
                    st.error(f"❌ Estoura Meta ({comprometimento:.1f}%)")
                
                st.write(f"Custo Real Mensal: **R$ {custo_mensal_total:,.2f}**")
                if juros_pagos > 0: st.caption(f"⚠️ Juros totais: R$ {juros_pagos:,.0f}")