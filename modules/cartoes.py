import streamlit as st
import pandas as pd
from datetime import date
import os
import numpy as np
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols_padrao = ["ID", "Nome", "Bandeira", "Dia_Fechamento", "Dia_Vencimento", "Pontos_por_Dolar", "Limite"]
    df = conexoes.load_gsheet("Cartoes", cols_padrao)
    
    if not df.empty:
        # Saneamento de Tipos (Essencial para cálculos de milhas)
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
        df['Pontos_por_Dolar'] = pd.to_numeric(df['Pontos_por_Dolar'], errors='coerce').fillna(1.0)
        df['Dia_Fechamento'] = pd.to_numeric(df['Dia_Fechamento'], errors='coerce').fillna(1).astype(int)
        df['Dia_Vencimento'] = pd.to_numeric(df['Dia_Vencimento'], errors='coerce').fillna(10).astype(int)
        df['Limite'] = pd.to_numeric(df['Limite'], errors='coerce').fillna(0.0)
        
    return df

def save_data(df):
    conexoes.save_gsheet("Cartoes", df)

def calcular_pontos_acumulados(df_cartoes):
    # Puxa transações da nuvem para o cruzamento de dados (JOIN)
    cols_t = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento", "Cartao_Ref"]
    df_t = conexoes.load_gsheet("Transacoes", cols_t)
    
    # Se não houver transações ou coluna de referência, retorna colunas zeradas
    if df_t.empty or "Cartao_Ref" not in df_t.columns:
        df_cartoes['Valor_Total'] = 0.0
        df_cartoes['Pontos_Est'] = 0.0
        return df_cartoes
    
    # Saneamento básico das transações
    df_t['Valor_Total'] = pd.to_numeric(df_t['Valor_Total'], errors='coerce').fillna(0.0)
    
    # Filtra apenas gastos no crédito vinculados a cartões cadastrados
    gastos_credito = df_t[(df_t['Tipo'] == 'Cartao') & (df_t['Cartao_Ref'].notna())]
    
    if gastos_credito.empty: 
        df_cartoes['Valor_Total'] = 0.0
        df_cartoes['Pontos_Est'] = 0.0
        return df_cartoes
    
    # Agrupamento (Engine de Cálculo)
    gastos_por_cartao = gastos_credito.groupby('Cartao_Ref')['Valor_Total'].sum().reset_index()
    
    # Merge técnico (Equivalente ao LEFT JOIN em SQL)
    resumo = pd.merge(df_cartoes, gastos_por_cartao, left_on='Nome', right_on='Cartao_Ref', how='left')
    resumo['Valor_Total'] = resumo['Valor_Total'].fillna(0.0)
    
    # Constante de mercado (Poderia vir de uma API no futuro)
    DOLAR_PRECO = 5.80
    resumo['Gasto_USD'] = resumo['Valor_Total'] / DOLAR_PRECO
    resumo['Pontos_Est'] = resumo['Gasto_USD'] * resumo['Pontos_por_Dolar']
    
    return resumo

def render_page():
    st.header("💳 Central de Cartões & Milhas")
    st.caption("Gestão estratégica de crédito e pontuação na nuvem.")
    
    df = load_data()
    
    with st.sidebar:
        st.subheader("➕ Novo Cartão")
        with st.form("form_card"):
            c_nome = st.text_input("Apelido do Cartão")
            c_band = st.selectbox("Bandeira", ["Mastercard", "Visa", "Elo", "Amex", "Outra"])
            c_fech = st.number_input("Dia Fechamento", 1, 31, 1)
            c_venc = st.number_input("Dia Vencimento", 1, 31, 10)
            c_pts = st.number_input("Pontos por Dólar", 0.0, 10.0, 1.0)
            c_lim = st.number_input("Limite Total (R$)", 0.0)
            
            if st.form_submit_button("Cadastrar Plástico"):
                max_id = df['ID'].max() if not df.empty else 0
                new_id = int(max_id) + 1
                
                novo = {
                    "ID": new_id, "Nome": c_nome, "Bandeira": c_band,
                    "Dia_Fechamento": c_fech, "Dia_Vencimento": c_venc,
                    "Pontos_por_Dolar": c_pts, "Limite": c_lim
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Cartão sincronizado com a nuvem!")
                st.rerun()

    if not df.empty:
        df_calc = calcular_pontos_acumulados(df)
        
        # Dashboard de Milhagem
        total_pts = df_calc['Pontos_Est'].sum()
        valor_pts = (total_pts / 1000) * 20.00 # Estimativa padrão de mercado
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Cartões", len(df))
        c2.metric("Milhas Est.", f"{total_pts:,.0f}")
        c3.metric("Patrimônio em Milhas", f"R$ {valor_pts:,.2f}")
        
        st.divider()
        
        # Tabela de Eficiência
        view_df = df_calc[['Nome', 'Bandeira', 'Pontos_por_Dolar', 'Valor_Total', 'Pontos_Est']].copy()
        view_df.rename(columns={'Valor_Total': 'Gasto Total', 'Pontos_Est': 'Pontos'}, inplace=True)
        view_df = view_df.sort_values("Pontos", ascending=False)
        
        st.dataframe(
            view_df,
            column_config={
                "Pontos": st.column_config.ProgressColumn("Milhas Acumuladas", format="%.0f", min_value=0, max_value=max(view_df['Pontos'].max(), 100)),
                "Gasto Total": st.column_config.NumberColumn(format="R$ %.2f")
            },
            width=True, hide_index=True
        )
        
        # Visualização de Dados
        c_bar, c_pie = st.columns(2)
        with c_bar:
            st.caption("Distribuição de Gastos")
            st.bar_chart(view_df.set_index("Nome")['Gasto Total'])
        with c_pie:
            st.caption("Share de Milhas por Cartão")
            if view_df['Pontos'].sum() > 0:
                import plotly.express as px
                fig = px.pie(view_df, values='Pontos', names='Nome', hole=0.4)
                st.plotly_chart(fig, width=True)
            else:
                st.info("Lance transações para ver o share.")

        with st.expander("🗑️ Gerenciar Carteira"):
            c_sel = st.selectbox("Selecione para excluir", df['Nome'].unique())
            if st.button("Confirmar Exclusão"):
                df = df[df['Nome'] != c_sel]
                save_data(df)
                st.rerun()
    else:
        st.info("Carteira vazia. Adicione um cartão para iniciar a gestão.")