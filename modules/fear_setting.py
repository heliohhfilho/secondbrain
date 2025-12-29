import streamlit as st
import pandas as pd
from datetime import date
import os

# --- ARQUIVOS ---
PATH_FEAR = os.path.join('data', 'fear_setting.csv')

def load_data():
    if not os.path.exists(PATH_FEAR):
        return pd.DataFrame(columns=[
            "ID", "Medo_Acao", "Pior_Cenario", "Prevencao", "Reparacao", 
            "Beneficios_Sucesso", "Custo_Inacao", "Data_Add", "Status"
        ])
    return pd.read_csv(PATH_FEAR)

def save_data(df):
    df.to_csv(PATH_FEAR, index=False)

def render_page():
    st.header("🛡️ Fear Setting (Gestão de Risco Pessoal)")
    st.caption("Debugando a ansiedade: Defina, Previna e Repare.")
    
    df = load_data()
    
    # --- WIZARD DE CRIAÇÃO ---
    with st.expander("➕ Novo Lab de Risco (Debugar um Medo)", expanded=df.empty):
        with st.form("form_fear"):
            st.markdown("### 1. O que você tem medo de fazer?")
            acao = st.text_input("Ex: Pedir demissão para virar Freelancer, Chamar alguém para sair, Investir tudo em Bitcoin...")
            
            c1, c2, c3 = st.columns(3)
            pior = c1.text_area("😱 Pior Cenário (Definir)", placeholder="Ficar sem dinheiro, ser rejeitado, perder tudo...", height=100)
            prev = c2.text_area("🛡️ Prevenção (O que fazer antes?)", placeholder="Juntar reserva de emergência, estudar antes...", height=100)
            repar = c3.text_area("🔧 Reparação (Se der errado?)", placeholder="Voltar a morar com os pais, procurar emprego novo...", height=100)
            
            st.markdown("---")
            c4, c5 = st.columns(2)
            benef = c4.text_area("🚀 Benefícios (Se der certo?)", placeholder="Liberdade, lucro alto, felicidade...", height=80)
            inacao = c5.text_area("💀 Custo da Inação (Se eu não fizer nada?)", placeholder="Ficar estagnado, infeliz, arrependido em 1 ano...", height=80)
            
            if st.form_submit_button("Analisar Risco"):
                if acao:
                    new_id = 1 if df.empty else df['ID'].max() + 1
                    novo = {
                        "ID": new_id, "Medo_Acao": acao, 
                        "Pior_Cenario": pior, "Prevencao": prev, "Reparacao": repar,
                        "Beneficios_Sucesso": benef, "Custo_Inacao": inacao,
                        "Data_Add": date.today(), "Status": "Analisado"
                    }
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df)
                    st.success("Risco Mapeado! A lógica venceu o medo.")
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