import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import graphviz

from modules import conexoes

@st.cache_data(ttl=600)
def load_data():
    # Definição das colunas para cada aba
    cols_conf = ["Inicio", "Fim"]
    cols_hor = ["Dia_Semana", "Hora_Inicio", "Materia", "Sala"]
    cols_mat = ["Materia", "Semestre_Ref", "Status", "Pre_Requisito", "Professor"]
    cols_aval = ["Materia", "Nome", "Data", "Peso", "Nota", "Concluido"]
    cols_top = ["Materia", "Topico", "Prova_Ref", "Teoria_Ok", "Exercicio_Ok", "Revisao_Ok"]

    # Carregamento via Google Sheets
    df_conf = conexoes.load_gsheet("Fac_Config", cols_conf)
    if df_conf.empty:
        df_conf = pd.DataFrame([{"Inicio": str(date.today()), "Fim": str(date.today() + timedelta(days=120))}])
    
    df_h = conexoes.load_gsheet("Fac_Horarios", cols_hor)
    df_m = conexoes.load_gsheet("Fac_Materias", cols_mat)
    df_a = conexoes.load_gsheet("Fac_Avaliacoes", cols_aval)
    df_t = conexoes.load_gsheet("Fac_Topicos", cols_top)

    # --- SANEAMENTO DE TIPOS (GSheets -> Python Types) ---
    if not df_a.empty:
        df_a["Peso"] = pd.to_numeric(df_a["Peso"], errors='coerce').fillna(1.0)
        df_a["Nota"] = pd.to_numeric(df_a["Nota"], errors='coerce').fillna(0.0)
        df_a["Concluido"] = df_a["Concluido"].astype(str).str.upper() == "TRUE"

    if not df_t.empty:
        for col in ["Teoria_Ok", "Exercicio_Ok", "Revisao_Ok"]:
            df_t[col] = df_t[col].astype(str).str.upper() == "TRUE"
        if "Prova_Ref" not in df_t.columns: df_t["Prova_Ref"] = "Geral"

    if not df_m.empty:
        # CONVERSÃO CRÍTICA: String "Mat A, Mat B" -> Lista ["Mat A", "Mat B"]
        def str_to_list(x):
            if pd.isna(x) or x == "-" or str(x).strip() == "":
                return []
            # Separa por vírgula e remove espaços extras
            return [i.strip() for i in str(x).split(",") if i.strip()]
            
        df_m["Pre_Requisito"] = df_m["Pre_Requisito"].apply(str_to_list)

    return df_conf, df_h, df_m, df_a, df_t

def save_data(df, aba):
    # Converte tudo para string antes de subir para evitar erros de serialização
    df_save = df.copy()
    if "Pre_Requisito" in df_save.columns:
        def list_to_str(x):
            if isinstance(x, list):
                return ", ".join(x)
            return x
        df_save["Pre_Requisito"] = df_save["Pre_Requisito"].apply(list_to_str)

    if "Data" in df_save.columns: df_save["Data"] = df_save["Data"].astype(str)
    conexoes.save_gsheet(aba, df_save)

# --- ADICIONE ESSA FUNÇÃO FORA DO RENDER_PAGE (Lógica do Caminho Crítico) ---
# --- LÓGICA DO CAMINHO CRÍTICO (CORRIGIDA PARA LISTAS) ---
def calcular_previsao_semestres(df_mat):
    # Filtra o que falta fazer
    pendentes = df_mat[df_mat['Status'] != 'Concluído'].copy()
    
    if pendentes.empty:
        return 0, []

    # Cria dicionário de adjacência (Matéria -> Lista de Pré-requisitos Pendentes)
    adj = {}
    todos_pendentes = set(pendentes['Materia'].unique())
    
    for _, row in pendentes.iterrows():
        materia = row['Materia']
        prereqs = row['Pre_Requisito'] # Isso agora é uma LISTA (ex: ['Calc1', 'GA'])
        
        # Filtra apenas os pré-requisitos que AINDA faltam fazer
        # Se o pré-requisito já foi concluído, ele não gera dependência/atraso no grafo
        prereqs_ativos = []
        if isinstance(prereqs, list):
            for p in prereqs:
                if p in todos_pendentes:
                    prereqs_ativos.append(p)
        
        if prereqs_ativos:
            adj[materia] = prereqs_ativos

    # Memoization para guardar (Profundidade, Caminho)
    memo = {}

    def get_critical_path(mat):
        # Se a matéria não tem dependências pendentes, profundidade é 1
        if mat not in adj: 
            return 1, [mat]
        
        if mat in memo: 
            return memo[mat]
        
        pais = adj[mat]
        
        # Encontra qual dos pré-requisitos vai demorar mais (o gargalo)
        max_depth = 0
        melhor_caminho = []
        
        for pai in pais:
            d, caminho_pai = get_critical_path(pai)
            if d > max_depth:
                max_depth = d
                melhor_caminho = caminho_pai
        
        # A profundidade atual é 1 + a maior profundidade dos pais
        current_depth = 1 + max_depth
        current_path = melhor_caminho + [mat] # Adiciona a matéria atual ao fim do caminho
        
        memo[mat] = (current_depth, current_path)
        return current_depth, current_path

    max_semestres = 0
    caminho_critico_final = []
    
    # Testa todas as matérias pendentes para ver qual gera o caminho mais longo
    for mat in todos_pendentes:
        depth, path = get_critical_path(mat)
        if depth > max_semestres:
            max_semestres = depth
            caminho_critico_final = path

    return max_semestres, caminho_critico_final

def simular_cronograma(df):
    concluidas = set(df[df['Status'] == 'Concluído']['Materia'])
    cursando_agora = set(df[df['Status'] == 'Cursando']['Materia'])
    pendentes = df[df['Status'] == 'Futuro'].copy()
    
    cronograma = {}
    semestre_idx = 1
    
    # Base de conhecimentos (O que eu já tenho)
    conhecimento_atual = concluidas.union(cursando_agora)

    while not pendentes.empty:
        materias_disponiveis = []
        
        for idx, row in pendentes.iterrows():
            prereqs = row['Pre_Requisito'] # Agora isso é uma lista ex: ["Calc1", "GA"]
            
            # Regra: Se a lista for vazia OU se TODOS os itens da lista estiverem no conhecimento atual
            if not prereqs or all(p in conhecimento_atual for p in prereqs):
                materias_disponiveis.append(idx)
        
        if not materias_disponiveis:
            break # Travou (Ciclo ou pré-req faltante)
            
        cronograma[semestre_idx] = pendentes.loc[materias_disponiveis, 'Materia'].tolist()
        
        # O aluno "passou" nessas matérias, adiciona ao conhecimento
        novas_concluidas = set(pendentes.loc[materias_disponiveis, 'Materia'])
        conhecimento_atual.update(novas_concluidas)
        
        pendentes = pendentes.drop(materias_disponiveis)
        semestre_idx += 1
        
    return cronograma

def render_page():
    st.header("🎓 Engenharia Acadêmica")
    df_conf, df_hor, df_mat, df_aval, df_top = load_data()
    
    # ... (MANTENHA O CÓDIGO DO DETECTOR DE FÉRIAS AQUI) ...
    hoje = date.today()
    inicio_sem = pd.to_datetime(df_conf.iloc[0]['Inicio']).date()
    fim_sem = pd.to_datetime(df_conf.iloc[0]['Fim']).date()
    em_ferias = not (inicio_sem <= hoje <= fim_sem)

    with st.sidebar:
        st.subheader("📅 Calendário")
        # ... (MANTENHA O INPUT DE DATAS AQUI) ...
        c1, c2 = st.columns(2)
        ini = c1.date_input("Início", inicio_sem)
        fim = c2.date_input("Fim", fim_sem)
        if ini != inicio_sem or fim != fim_sem:
            df_conf.at[0, 'Inicio'] = str(ini)
            df_conf.at[0, 'Fim'] = str(fim)
            save_data(df_conf, "Fac_Config")
            st.rerun()

        st.divider()
        # CORREÇÃO 1: Garante que a lista 'cursando' esteja sempre fresca
        cursando = df_mat[df_mat['Status'] == 'Cursando']['Materia'].tolist()
        
        # Adicionei a nova opção no menu
        view_mode = st.radio("Visão", ["Dashboard & Horários", "Fluxo & Previsão (Novo)"] + cursando + ["Grade Curricular (CRUD)"])

    # ==============================================================================
    # MODO NOVO: FLUXOGRAMA E PREVISÃO
    # ==============================================================================
    if view_mode == "Fluxo & Previsão (Novo)":
        st.subheader("🔭 Visão Estratégica do Curso")

        # 1. Cálculo de Previsão
        semestres_restantes, caminho_critico = calcular_previsao_semestres(df_mat)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Semestres Mínimos", semestres_restantes)
        ano_previsto = date.today().year + (semestres_restantes // 2)
        c2.metric("Formatura Estimada", f"Fim de {ano_previsto}")
        c3.metric("Matérias Pendentes", len(df_mat[df_mat['Status'] == 'Futuro']))
        
        if caminho_critico:
            st.caption(f"🔒 **Seu Gargalo (Caminho Crítico):** {' → '.join(caminho_critico)}")
            st.info("Essa é a sequência de matérias que trava sua formatura. Priorize essas!")

        st.divider()

        # 2. Visualização Graphviz
        st.subheader("🗺️ Mapa de Dependências")
        
        graph = graphviz.Digraph()
        graph.attr(rankdir='LR') # Da esquerda para direita
        
        # Cores baseadas no Status
        colors = {'Concluído': '#90EE90', 'Cursando': '#87CEFA', 'Futuro': '#D3D3D3'}
        
        for _, row in df_mat.iterrows():
            mat = row['Materia']
            status = row['Status']
            prereqs = row['Pre_Requisito'] # Lista
            
            # Nó
            graph.node(mat, label=mat, style='filled', fillcolor=colors.get(status, 'white'), shape='box')
            
            # Arestas (Setas) - Loop na lista de pré-requisitos
            if isinstance(prereqs, list):
                for req in prereqs:
                    if req in df_mat['Materia'].values:
                        req_status = df_mat[df_mat['Materia'] == req]['Status'].values[0]
                        edge_color = 'red' if req_status == 'Futuro' else 'black'
                        graph.edge(req, mat, color=edge_color)

        st.graphviz_chart(graph, width='stretch')

# ==============================================================================
    # MODO 1: DASHBOARD & GESTÃO DE HORÁRIOS (ATUALIZADO)
    # ==============================================================================
    if view_mode == "Dashboard & Horários":
        
        # --- BLOCO SUPERIOR (Contexto) ---
        if em_ferias:
            st.info("🏖️ Modo Férias Ativo")
        else:
            # Barra de progresso do semestre
            total = (fim_sem - inicio_sem).days
            passados = (hoje - inicio_sem).days
            perc = max(0.0, min(1.0, passados / total)) if total > 0 else 0
            st.progress(perc, text=f"Semestre: {perc*100:.1f}% concluído")

        st.divider()

        # Abas para separar a visualização da edição
        tab_hoje, tab_gestao, tab_completa = st.tabs(["📅 Aulas de Hoje", "➕ Adicionar/Remover Horários", "🗓️ Grade Completa"])

        # --- ABA 1: O QUE TEM PRA HOJE? ---
        with tab_hoje:
            dias_map = {0:"Segunda", 1:"Terça", 2:"Quarta", 3:"Quinta", 4:"Sexta", 5:"Sábado", 6:"Domingo"}
            hoje_str = dias_map[hoje.weekday()]
            
            st.subheader(f"Rotina de {hoje_str}")
            
            # Filtra apenas aulas de hoje
            aulas = df_hor[df_hor['Dia_Semana'] == hoje_str].sort_values("Hora_Inicio")
            
            if not aulas.empty:
                for _, row in aulas.iterrows():
                    # Card estilo "Ticket"
                    with st.container(border=True):
                        c_hora, c_info = st.columns([1, 4])
                        with c_hora:
                            st.markdown(f"### {row['Hora_Inicio']}")
                        with c_info:
                            st.markdown(f"**{row['Materia']}**")
                            st.caption(f"📍 Sala: {row['Sala']}")
            else:
                st.info(f"Sem aulas registradas para {hoje_str}. Dia de estudar cálculo? 📚")

        # --- ABA 2: ADICIONAR SLOT (A LÓGICA QUE VOCÊ PEDIU) ---
        with tab_gestao:
            st.subheader("Configurar Horários da Semana")
            
            c1, c2 = st.columns([1, 2])
            
            # Lado Esquerdo: Formulário de Adição
            with c1:
                st.markdown("##### ➕ Novo Horário")
                with st.form("add_horario_form"):
                    # 1. Só pega matérias que você está CURSANDO
                    mat_cursando = df_mat[df_mat['Status'] == 'Cursando']['Materia'].unique().tolist()
                    
                    if not mat_cursando:
                        st.warning("Você não tem matérias marcadas como 'Cursando'. Vá na aba 'Grade Curricular' primeiro.")
                        materia_selecionada = None
                    else:
                        materia_selecionada = st.selectbox("Matéria", mat_cursando)
                    
                    dia_selecionado = st.selectbox("Dia", ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"])
                    hora_selecionada = st.time_input("Início da Aula")
                    sala_digitada = st.text_input("Sala / Bloco", placeholder="Ex: B-201")
                    
                    if st.form_submit_button("Adicionar Aula"):
                        if materia_selecionada:
                            novo_slot = {
                                "Dia_Semana": dia_selecionado,
                                "Hora_Inicio": str(hora_selecionada)[:5], # Formata HH:MM
                                "Materia": materia_selecionada,
                                "Sala": sala_digitada
                            }
                            df_hor = pd.concat([df_hor, pd.DataFrame([novo_slot])], ignore_index=True)
                            save_data(df_hor, "Fac_Horarios")
                            st.success("Horário adicionado!")
                            st.rerun()

            # Lado Direito: Lista para Excluir
            with c2:
                st.markdown("##### 🗑️ Horários Cadastrados")
                if not df_hor.empty:
                    # Mostra uma tabela onde você pode selecionar linhas para deletar
                    # Usando checkbox na tabela para multiselect delete
                    
                    df_view = df_hor.sort_values(by=["Dia_Semana", "Hora_Inicio"])
                    
                    # Hackzinho para ordenar dias da semana corretamente na visualização
                    ordem_dias = {"Segunda":1, "Terça":2, "Quarta":3, "Quinta":4, "Sexta":5, "Sábado":6}
                    df_view['Ordem'] = df_view['Dia_Semana'].map(ordem_dias)
                    df_view = df_view.sort_values(['Ordem', 'Hora_Inicio']).drop(columns=['Ordem'])

                    rows_to_delete = []
                    for idx, row in df_view.iterrows():
                        cols = st.columns([2, 2, 2, 2, 1])
                        cols[0].write(f"**{row['Dia_Semana']}**")
                        cols[1].write(row['Hora_Inicio'])
                        cols[2].write(row['Materia'])
                        cols[3].write(row['Sala'])
                        if cols[4].button("❌", key=f"del_h_{idx}"):
                            # Remove pelo índice original (que preservamos ao iterar df_hor, cuidado com sort)
                            # A forma mais segura é buscar match exato
                            mask = (df_hor['Dia_Semana'] == row['Dia_Semana']) & \
                                   (df_hor['Hora_Inicio'] == row['Hora_Inicio']) & \
                                   (df_hor['Materia'] == row['Materia'])
                            df_hor = df_hor[~mask]
                            save_data(df_hor, "Fac_Horarios")
                            st.rerun()
                else:
                    st.caption("Nenhum horário cadastrado ainda.")

        # --- ABA 3: VISÃO GERAL (MATRIZ) ---
        with tab_completa:
            st.subheader("Visão Semanal")
            if not df_hor.empty:
                # Pivot Table para criar aquela grade clássica de horários
                # Isso é apenas visualização
                st.dataframe(
                    df_hor.sort_values("Hora_Inicio"),
                    column_config={
                        "Dia_Semana": "Dia",
                        "Hora_Inicio": "Horário",
                        "Materia": "Disciplina",
                        "Sala": "Local"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Adicione horários na aba ao lado.")

    # ==============================================================================
    # MODO 2: GRADE INTERATIVA & GESTÃO (O PEDIDO REAL)
    # ==============================================================================
    elif view_mode == "Grade Curricular (CRUD)":
        st.subheader("🎛️ Painel de Controle da Graduação")
        
        # --- TABELA DE EDIÇÃO EM MASSA ---
        st.info("Marque abaixo o que você já fez (Concluído), o que está fazendo (Cursando) e o que falta.")
        
        # Editor poderoso: Permite mudar status de várias matérias rápido
        edited_df = st.data_editor(
            df_mat,
            column_config={
                "Materia": st.column_config.TextColumn("Matéria", disabled=True),
                "Status": st.column_config.SelectboxColumn(
                    "Situação", options=["Concluído", "Cursando", "Futuro"], required=True
                ),
                # AQUI ESTÁ O TRUQUE VISUAL: ListColumn
                "Pre_Requisito": st.column_config.ListColumn(
                    "Pré-Requisitos",
                    help="Lista de matérias necessárias",
                    width="medium"
                ),
                "Semestre_Ref": st.column_config.NumberColumn("Semestre Ideal"),
            },
            hide_index=True,
            width='stretch',
            key="editor_grade_principal"
        )

        # Botão de Salvar manual para garantir o processamento
        col_save, _ = st.columns([1, 4])
        if col_save.button("💾 Salvar Alterações", type="primary"):
            save_data(edited_df, "Fac_Materias") # Nossa função save_data agora converte lista->string
            st.success("Salvo!")
            st.rerun()

        # --- PREVISÃO INTELIGENTE (A LÓGICA QUE VOCÊ PEDIU) ---
        st.divider()
        st.subheader("🔮 Previsão de Formatura (Baseado em Pré-Requisitos)")
        
        cronograma_futuro = simular_cronograma(edited_df)
        
        if not cronograma_futuro and not edited_df[edited_df['Status']=='Futuro'].empty:
            st.error("⚠️ Erro de Lógica: Há matérias travadas! Verifique se os nomes dos Pré-Requisitos estão escritos exatamente iguais aos nomes das matérias.")
        elif not cronograma_futuro:
            st.balloons()
            st.success("Você não tem matérias pendentes! Parabéns, Engenheiro!")
        else:
            qtd_semestres = len(cronograma_futuro)
            st.write(f"Com base no que você está cursando e nos pré-requisitos, faltam **{qtd_semestres} semestres** letivos.")
            
            # Visualização Semestre a Semestre
            cols = st.columns(min(qtd_semestres, 4)) # Mostra até 4 colunas lado a lado
            for i, (semestre_num, materias) in enumerate(cronograma_futuro.items()):
                with cols[i % 4]: # Quebra de linha se tiver muitos semestres
                    with st.container(border=True):
                        st.markdown(f"**+{semestre_num}º Semestre**")
                        for m in materias:
                            st.caption(f"• {m}")

        # --- ÁREA DE ADICIONAR NOVA MATÉRIA ---
        st.divider()
        with st.expander("➕ Adicionar Nova Matéria (Com Multi-Seleção)", expanded=True):
            with st.form("nova_materia"):
                c1, c2 = st.columns([1, 1])
                nm = c1.text_input("Nome da Matéria Nova")
                
                # Pega todas as matérias existentes para o dropdown
                todas_materias = df_mat['Materia'].sort_values().unique().tolist()
                
                # O MULTI-SELECT PARA EVITAR ERROS DE DIGITAÇÃO
                reqs = c2.multiselect("Pré-Requisitos", options=todas_materias)
                
                c3, c4 = st.columns(2)
                sem = c3.number_input("Semestre Ideal", 1, 12, 1)
                stt = c4.selectbox("Status Inicial", ["Futuro", "Cursando", "Concluído"])
                
                if st.form_submit_button("Cadastrar Matéria"):
                    if nm and nm not in todas_materias:
                        nova = {
                            "Materia": nm, 
                            "Semestre_Ref": sem, 
                            "Status": stt, 
                            "Pre_Requisito": reqs, # Salva como Lista direto
                            "Professor": "-"
                        }
                        # Concatena
                        df_mat = pd.concat([df_mat, pd.DataFrame([nova])], ignore_index=True)
                        save_data(df_mat, "Fac_Materias")
                        st.success(f"'{nm}' cadastrada com sucesso!")
                        st.rerun()
                    elif nm in todas_materias:
                        st.error("Essa matéria já existe!")
                    else:
                        st.warning("Preencha o nome.")