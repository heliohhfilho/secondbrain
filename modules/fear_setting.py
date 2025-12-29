import streamlit as st
import pandas as pd
from datetime import date
import os

from modules import conexoes

def load_data():
    cols = [
        "ID", "Medo_Acao", "Pior_Cenario", "Prevencao", "Reparacao", 
        "Beneficios_Sucesso", "Custo_Inacao", "Data_Add", "Status"
    ]
    df = conexoes.load_gsheet("FearSetting", cols)
    
    if not df.empty:
        # Saneamento de tipos para garantir IDs numéricos
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
    return df

def save_data(df):
    # Converte tipos para garantir compatibilidade com o Google Sheets (Datas como string)
    df_save = df.copy()
    if "Data_Add" in df_save.columns:
        df_save["Data_Add"] = df_save["Data_Add"].astype(str)
    conexoes.save_gsheet("FearSetting", df_save)

def render_page():
    st.header("🛡️ Fear Setting (Gestão de Risco Pessoal)")
    st.caption("Debugando a ansiedade: Defina, Previna e Repare.")
    
    df = load_data()
    
    # --- WIZARD DE CRIAÇÃO ---
    with st.expander("➕ Novo Lab de Risco (Debugar um Medo)", expanded=df.empty):
        with st.form("form_fear"):
            st.markdown("### 1. O que você tem medo de fazer?")
            acao = st.text_input("Ex: Investir em um novo setup de Trade, Mudar de área na Engenharia...")
            
            c1, c2, c3 = st.columns(3)
            pior = c1.text_area("😱 Pior Cenário", height=100)
            prev = c2.text_area("🛡️ Prevenção", height=100)
            repar = c3.text_area("🔧 Reparação", height=100)
            
            st.markdown("---")
            c4, c5 = st.columns(2)
            benef = c4.text_area("🚀 Benefícios", height=80)
            inacao = c5.text_area("💀 Custo da Inação", height=80)
            
            if st.form_submit_button("Analisar Risco"):
                if acao:
                    new_id = 1 if df.empty else int(df['ID'].max()) + 1
                    novo = {
                        "ID": new_id, "Medo_Acao": acao, 
                        "Pior_Cenario": pior, "Prevencao": prev, "Reparacao": repar,
                        "Beneficios_Sucesso": benef, "Custo_Inacao": inacao,
                        "Data_Add": str(date.today()), "Status": "Analisado"
                    }
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df)
                    st.success("Risco Mapeado na Nuvem! A lógica venceu o medo.")
                    st.rerun()

    # --- VISUALIZAÇÃO DOS MEDOS ---
    if not df.empty:
        st.divider()
        st.subheader("🧪 Seus Experimentos de Coragem")
        
        # Filtra ativos
        ativos = df[df['Status'] == "Analisado"]
        
        for idx, row in ativos.iterrows():
            with st.container(border=True):
                st.markdown(f"### 🦁 Ação: {row['Medo_Acao']}")
                
                # Matriz Visual
                col_risco, col_bonus = st.columns([2, 1])
                
                with col_risco:
                    st.markdown("#### 📉 Análise de Downside (O que pode dar errado)")
                    st.warning(f"**Pior Caso:** {row['Pior_Cenario']}")
                    st.info(f"**Prevenção:** {row['Prevencao']}")
                    st.success(f"**Reparação:** {row['Reparacao']}")
                
                with col_bonus:
                    st.markdown("#### 📈 Análise de Upside")
                    st.write(f"✨ **Ganho:** {row['Beneficios_Sucesso']}")
                    st.error(f"☠️ **Custo de não fazer:** {row['Custo_Inacao']}")
                
                st.divider()
                
                c_act1, c_act2 = st.columns(2)
                if c_act1.button("✅ Enfrentei o Medo!", key=f"win_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Superado"
                    save_data(df)
                    st.balloons()
                    st.rerun()
                    
                if c_act2.button("🗑️ Descartar", key=f"del_fear_{row['ID']}"):
                    df = df[df['ID'] != row['ID']]
                    save_data(df)
                    st.rerun()

        # Histórico
        superados = df[df['Status'] == "Superado"]
        if not superados.empty:
            with st.expander("🏆 Cemitério de Medos (Superados)"):
                for idx, row in superados.iterrows():
                    st.caption(f"✔️ {row['Medo_Acao']} (Vencido em {row['Data_Add']})")