import streamlit as st
import pandas as pd
from datetime import datetime, date
import os
import uuid # Para gerar IDs únicos e garantir integridade relacional

# --- CAMINHOS DOS ARQUIVOS ---
PROJETOS_PATH = os.path.join('data', 'projetos.csv')
TAREFAS_PATH = os.path.join('data', 'tarefas_projetos.csv')

# --- FUNÇÕES DE BANCO DE DADOS ---
def load_data():
    # Projetos: ID, Nome, Descricao, Data_Inicio, Status (Ativo/Arquivado)
    if not os.path.exists(PROJETOS_PATH):
        df_proj = pd.DataFrame(columns=["ID", "Nome", "Descricao", "Data_Inicio", "Status"])
    else:
        df_proj = pd.read_csv(PROJETOS_PATH)

    # Tarefas: ID, Projeto_ID, Nome, Status (Backlog, Dev, Done), Data_Inicio, Data_Fim
    if not os.path.exists(TAREFAS_PATH):
        df_task = pd.DataFrame(columns=["ID_Tarefa", "Projeto_ID", "Nome", "Status", "Data_Inicio", "Data_Fim"])
    else:
        df_task = pd.read_csv(TAREFAS_PATH)
        
    return df_proj, df_task

def save_data(df_proj, df_task):
    df_proj.to_csv(PROJETOS_PATH, index=False)
    df_task.to_csv(TAREFAS_PATH, index=False)

def calculate_progress(proj_id, df_tasks):
    tasks_proj = df_tasks[df_tasks['Projeto_ID'] == proj_id]
    if tasks_proj.empty:
        return 0.0, 0, 0
    total = len(tasks_proj)
    concluidas = len(tasks_proj[tasks_proj['Status'] == "Concluido"])
    return (concluidas / total), concluidas, total

def render_page():
    st.header("🚀 Gerenciamento de Projetos & Kanban")
    
    df_proj, df_task = load_data()

    # --- SIDEBAR: CRIAÇÃO (CRUD) ---
    with st.sidebar:
        st.subheader("Novo Projeto")
        p_nome = st.text_input("Nome do Projeto")
        p_desc = st.text_area("Descrição / Objetivo")
        
        if st.button("Criar Projeto"):
            if p_nome:
                new_proj = {
                    "ID": str(uuid.uuid4())[:8], # ID curto único
                    "Nome": p_nome,
                    "Descricao": p_desc,
                    "Data_Inicio": date.today(),
                    "Status": "Ativo"
                }
                df_proj = pd.concat([df_proj, pd.DataFrame([new_proj])], ignore_index=True)
                save_data(df_proj, df_task)
                st.success("Projeto criado!")
                st.rerun()

        st.divider()
        
        # Só permite criar tarefa se existir projeto
        if not df_proj.empty:
            st.subheader("Nova Tarefa")
            # Dropdown mostra Nome mas retorna ID
            proj_map = dict(zip(df_proj['Nome'], df_proj['ID']))
            proj_selecionado_nome = st.selectbox("Vincular ao Projeto", list(proj_map.keys()))
            proj_selecionado_id = proj_map[proj_selecionado_nome]
            
            t_nome = st.text_input("Nome da Tarefa")
            t_status = st.selectbox("Status Inicial", ["Backlog", "Em Desenvolvimento", "Concluido"])
            
            if st.button("Adicionar Tarefa"):
                if t_nome:
                    # Lógica de data de conclusão se já nascer pronta
                    dt_fim = date.today() if t_status == "Concluido" else None
                    
                    new_task = {
                        "ID_Tarefa": str(uuid.uuid4())[:8],
                        "Projeto_ID": proj_selecionado_id,
                        "Nome": t_nome,
                        "Status": t_status,
                        "Data_Inicio": date.today(),
                        "Data_Fim": dt_fim
                    }
                    df_task = pd.concat([df_task, pd.DataFrame([new_task])], ignore_index=True)
                    save_data(df_proj, df_task)
                    st.success("Tarefa adicionada!")
                    st.rerun()

    # --- MAIN AREA ---
    if df_proj.empty:
        st.info("Comece criando um projeto na barra lateral.")
        return

    # Tabs para separar Visão Macro (Gerente) de Visão Micro (Executor)
    tab_kanban, tab_visao_geral = st.tabs(["🏗️ Kanban Board", "📊 Visão Geral dos Projetos"])

    # ==========================
    # ABA 1: KANBAN (Onde o trabalho acontece)
    # ==========================
    with tab_kanban:
        # Filtro de Projeto para o Kanban
        proj_nomes = df_proj['Nome'].tolist()
        filtro_proj = st.selectbox("Filtrar Projeto:", proj_nomes)
        
        # Pega o ID do projeto filtrado
        id_filtro = df_proj[df_proj['Nome'] == filtro_proj].iloc[0]['ID']
        
        # Filtra tarefas deste projeto
        tasks_view = df_task[df_task['Projeto_ID'] == id_filtro]
        
        # Métricas rápidas do projeto selecionado
        prog, done, total = calculate_progress(id_filtro, df_task)
        st.progress(prog)
        st.caption(f"Progresso: {int(prog*100)}% ({done}/{total} tarefas)")

        # Colunas do Kanban
        c_backlog, c_dev, c_done = st.columns(3)
        
        # --- COLUNA BACKLOG ---
        with c_backlog:
            st.markdown("### 📌 Backlog")
            for idx, row in tasks_view[tasks_view['Status'] == "Backlog"].iterrows():
                with st.container(border=True):
                    st.write(f"**{row['Nome']}**")
                    st.caption(f"Desde: {row['Data_Inicio']}")
                    
                    # Botão Mover para Direita
                    if st.button("Iniciar ➡️", key=f"start_{row['ID_Tarefa']}"):
                        real_idx = df_task[df_task['ID_Tarefa'] == row['ID_Tarefa']].index[0]
                        df_task.at[real_idx, 'Status'] = "Em Desenvolvimento"
                        save_data(df_proj, df_task)
                        st.rerun()
                    
                    # Excluir
                    if st.button("🗑️", key=f"del_{row['ID_Tarefa']}"):
                        real_idx = df_task[df_task['ID_Tarefa'] == row['ID_Tarefa']].index[0]
                        df_task = df_task.drop(real_idx)
                        save_data(df_proj, df_task)
                        st.rerun()

        # --- COLUNA EM DESENVOLVIMENTO ---
        with c_dev:
            st.markdown("### 🔨 Em Desenv.")
            for idx, row in tasks_view[tasks_view['Status'] == "Em Desenvolvimento"].iterrows():
                with st.container(border=True):
                    st.write(f"**{row['Nome']}**")
                    st.caption(f"Início: {row['Data_Inicio']}")
                    
                    c1, c2 = st.columns(2)
                    # Mover Esquerda
                    if c1.button("⬅️ Voltar", key=f"back_{row['ID_Tarefa']}"):
                        real_idx = df_task[df_task['ID_Tarefa'] == row['ID_Tarefa']].index[0]
                        df_task.at[real_idx, 'Status'] = "Backlog"
                        save_data(df_proj, df_task)
                        st.rerun()
                    
                    # Mover Direita
                    if c2.button("Pronto ➡️", key=f"finish_{row['ID_Tarefa']}"):
                        real_idx = df_task[df_task['ID_Tarefa'] == row['ID_Tarefa']].index[0]
                        df_task.at[real_idx, 'Status'] = "Concluido"
                        df_task.at[real_idx, 'Data_Fim'] = date.today() # Marca Timestamp
                        save_data(df_proj, df_task)
                        st.rerun()

        # --- COLUNA CONCLUÍDO ---
        with c_done:
            st.markdown("### ✅ Concluído")
            for idx, row in tasks_view[tasks_view['Status'] == "Concluido"].iterrows():
                with st.container(border=True):
                    st.write(f"~~{row['Nome']}~~")
                    
                    # Cálculo de Lead Time (Duração)
                    d_inicio = pd.to_datetime(row['Data_Inicio']).date()
                    d_fim = pd.to_datetime(row['Data_Fim']).date() if pd.notnull(row['Data_Fim']) else date.today()
                    duracao = (d_fim - d_inicio).days
                    
                    st.caption(f"Lead Time: {duracao} dias")
                    
                    # Voltar (Reabrir tarefa)
                    if st.button("⬅️ Reabrir", key=f"reopen_{row['ID_Tarefa']}"):
                        real_idx = df_task[df_task['ID_Tarefa'] == row['ID_Tarefa']].index[0]
                        df_task.at[real_idx, 'Status'] = "Em Desenvolvimento"
                        df_task.at[real_idx, 'Data_Fim'] = None # Limpa data de fim
                        save_data(df_proj, df_task)
                        st.rerun()

    # ==========================
    # ABA 2: VISÃO GERAL (PORTFÓLIO)
    # ==========================
    with tab_visao_geral:
        st.subheader("Portfólio de Projetos")
        
        for idx, row in df_proj.iterrows():
            with st.expander(f"📂 {row['Nome']}", expanded=True):
                c1, c2 = st.columns([3, 1])
                
                # Dados do Projeto
                with c1:
                    st.write(f"**Objetivo:** {row['Descricao']}")
                    st.caption(f"Iniciado em: {row['Data_Inicio']}")
                    
                    # Progresso
                    prog, done, total = calculate_progress(row['ID'], df_task)
                    st.progress(prog)
                    st.write(f"**Progresso:** {int(prog*100)}% ({done} de {total} tarefas)")
                
                # Ações do Projeto
                with c2:
                    if st.button("🗑️ Excluir Projeto", key=f"del_proj_{row['ID']}", type="primary"):
                        # Exclusão em Cascata (Deleta tarefas filhas)
                        df_task = df_task[df_task['Projeto_ID'] != row['ID']]
                        df_proj = df_proj.drop(idx)
                        save_data(df_proj, df_task)
                        st.rerun()