import streamlit as st
import pandas as pd
from datetime import date
import os

# --- ARQUIVOS ---
PATH_EISEN = os.path.join('data', 'eisenhower_tasks.csv')

def load_data():
    if not os.path.exists(PATH_EISEN):
        return pd.DataFrame(columns=["ID", "Tarefa", "Importante", "Urgente", "Status", "Data_Add"])
    return pd.read_csv(PATH_EISEN)

def save_data(df):
    df.to_csv(PATH_EISEN, index=False)

def render_page():
    st.header("🧠 Matriz de Eisenhower")
    st.caption("Pare de apagar incêndios (Q1) e comece a planejar o futuro (Q2).")
    
    df = load_data()
    
    # --- SIDEBAR: NOVA TAREFA ---
    with st.sidebar:
        st.subheader("➕ Nova Tarefa")
        with st.form("form_eisen"):
            e_task = st.text_input("Descrição da Tarefa")
            
            c1, c2 = st.columns(2)
            e_imp = c1.checkbox("É Importante?", value=True, help="Tem impacto no seu longo prazo/metas?")
            e_urg = c2.checkbox("É Urgente?", value=False, help="Tem prazo estourando agora?")
            
            if st.form_submit_button("Classificar"):
                if e_task:
                    new_id = 1 if df.empty else df['ID'].max() + 1
                    novo = {
                        "ID": new_id, "Tarefa": e_task, 
                        "Importante": e_imp, "Urgente": e_urg, 
                        "Status": "Pendente", "Data_Add": date.today()
                    }
                    df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df)
                    st.success("Tarefa alocada!")
                    st.rerun()

    # --- PROCESSAMENTO DOS QUADRANTES ---
    # Filtra apenas pendentes
    pendentes = df[df['Status'] == "Pendente"]
    
    # Q1: Importante & Urgente (Crises)
    q1 = pendentes[(pendentes['Importante'] == True) & (pendentes['Urgente'] == True)]
    
    # Q2: Importante & Não Urgente (Planejamento/Estratégia) -> ONDE VOCÊ DEVE VIVER
    q2 = pendentes[(pendentes['Importante'] == True) & (pendentes['Urgente'] == False)]
    
    # Q3: Não Importante & Urgente (Interrupções/Delegar)
    q3 = pendentes[(pendentes['Importante'] == False) & (pendentes['Urgente'] == True)]
    
    # Q4: Não Importante & Não Urgente (Distrações/Eliminar)
    q4 = pendentes[(pendentes['Importante'] == False) & (pendentes['Urgente'] == False)]

    # --- LAYOUT VISUAL (GRID 2x2) ---
    
    # Linha Superior
    c_q1, c_q2 = st.columns(2)
    
    with c_q1:
        st.error(f"🔥 Q1: FAÇA AGORA ({len(q1)})")
        st.caption("Crises, Prazos, Problemas Reais.")
        for idx, row in q1.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Tarefa']}**")
                if st.button("Concluir", key=f"q1_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Concluído"
                    save_data(df)
                    st.rerun()

    with c_q2:
        st.info(f"📅 Q2: AGENDE/PLANEJE ({len(q2)})")
        st.caption("Estratégia, Estudos, Academia, Projetos.")
        for idx, row in q2.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Tarefa']}**")
                if st.button("Concluir", key=f"q2_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Concluído"
                    save_data(df)
                    st.rerun()

    st.divider()
    
    # Linha Inferior
    c_q3, c_q4 = st.columns(2)
    
    with c_q3:
        st.warning(f"✋ Q3: DELEGUE ({len(q3)})")
        st.caption("Interrupções, Algumas Reuniões, E-mails.")
        for idx, row in q3.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Tarefa']}**")
                if st.button("Concluir", key=f"q3_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Concluído"
                    save_data(df)
                    st.rerun()

    with c_q4:
        st.warning(f"🗑️ Q4: ELIMINE ({len(q4)})")
        st.caption("Redes Sociais, Fofoca, Trivialidades.")
        for idx, row in q4.iterrows():
            with st.container(border=True):
                st.write(f"**{row['Tarefa']}**")
                c_a, c_b = st.columns(2)
                if c_a.button("Feito", key=f"q4_ok_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Concluído"
                    save_data(df)
                    st.rerun()
                if c_b.button("Excluir", key=f"q4_del_{row['ID']}"):
                    df.loc[df['ID'] == row['ID'], 'Status'] = "Deletado"
                    save_data(df)
                    st.rerun()
                    
    # --- HISTÓRICO ---
    with st.expander("📜 Histórico de Conclusões"):
        concluidos = df[df['Status'] == "Concluído"].sort_values("ID", ascending=False)
        if not concluidos.empty:
            for idx, row in concluidos.iterrows():
                st.caption(f"✅ {row['Tarefa']}")