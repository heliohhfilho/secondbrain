import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import graphviz
import time

from modules import conexoes

@st.cache_data(ttl=600)
def load_data():
    # Definição das colunas para cada aba
    cols_conf = ["Inicio", "Fim"]
    cols_hor = ["Dia_Semana", "Hora_Inicio", "Materia", "Sala"]
    cols_mat = ["Materia", "Semestre_Ref", "Status", "Pre_Requisito", "Professor"]
    cols_aval = ["Materia", "Nome", "Data", "Peso", "Nota", "Concluido", "Topicos_Ref"]
    cols_top = ["Materia", "Topico", "Status"]
    cols_rec = ["Materia", "Nome", "Link", "Tipo"]

    # Carregamento via Google Sheets
    df_conf = conexoes.load_gsheet("Fac_Config", cols_conf)
    if df_conf.empty:
        df_conf = pd.DataFrame([{"Inicio": str(date.today()), "Fim": str(date.today() + timedelta(days=120))}])
    
    df_rec = conexoes.load_gsheet("Fac_Recursos", cols_rec)
    df_h = conexoes.load_gsheet("Fac_Horarios", cols_hor)
    df_m = conexoes.load_gsheet("Fac_Materias", cols_mat)
    df_a = conexoes.load_gsheet("Fac_Avaliacoes", cols_aval)
    df_t = conexoes.load_gsheet("Fac_Topicos", cols_top)

    # --- SANEAMENTO DE TIPOS (GSheets -> Python Types) ---
    if not df_a.empty:
        df_a["Peso"] = pd.to_numeric(df_a["Peso"], errors='coerce').fillna(1.0)
        df_a["Nota"] = pd.to_numeric(df_a["Nota"], errors='coerce').fillna(0.0)
        df_a["Concluido"] = df_a["Concluido"].astype(str).str.upper() == "TRUE"
        if "Topicos_Ref" not in df_a.columns: df_a["Topicos_Ref"] = "-"
        df_a["Topicos_Ref"] = df_a["Topicos_Ref"].apply(str_to_list)

    if not df_t.empty:
        if "Status" not in df_t.columns: df_t["Status"] = "A Fazer"

    if not df_m.empty:
        def str_to_list(x):
            if pd.isna(x) or x == "-" or str(x).strip() == "":
                return []
            # Separa por vírgula e remove espaços extras
            return [i.strip() for i in str(x).split(",") if i.strip()]
            
        df_m["Pre_Requisito"] = df_m["Pre_Requisito"].apply(str_to_list)

    def str_to_list(x):
        if pd.isna(x) or x == "-" or str(x).strip() == "": return []
        return [i.strip() for i in str(x).split(",") if i.strip()]

    return df_conf, df_h, df_m, df_a, df_t, df_rec

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
    df_conf, df_hor, df_mat, df_aval, df_top, df_rec = load_data()

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
    # MODO NOVO: FLUXOGRAMA ESTRUTURADO POR SEMESTRE
    # ==============================================================================
    if view_mode == "Fluxo & Previsão (Novo)":
        st.subheader("🔭 Visão Estratégica do Curso")

        # 1. Cálculo de Previsão (Lógica mantém, só exibição muda)
        semestres_restantes, caminho_critico = calcular_previsao_semestres(df_mat)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Gargalo (Caminho Crítico)", f"{semestres_restantes} Semestres")
        
        # Lógica de Ano Previsto (Considerando 2 semestres por ano)
        semestre_atual_ano = 1 if date.today().month <= 6 else 2
        ano_atual = date.today().year
        semestres_para_add = semestres_restantes
        
        ano_final = ano_atual + (semestres_para_add // 2)
        sem_final = semestre_atual_ano + (semestres_para_add % 2)
        if sem_final > 2:
            ano_final += 1
            sem_final = 1
            
        c2.metric("Formatura Estimada", f"{sem_final}º Sem/{ano_final}")
        
        # Filtro de matérias pendentes reais (Status != Concluído)
        pendentes_cnt = len(df_mat[df_mat['Status'] != 'Concluído'])
        c3.metric("Matérias Pendentes", pendentes_cnt)
        
        if caminho_critico:
            st.info(f"🚧 **Atenção:** Sua formatura está travada por esta sequência: **{' → '.join(caminho_critico)}**")

        st.divider()

        # 2. Visualização Graphviz (AGORA COM CLUSTERS DE SEMESTRE)
        st.subheader("🗺️ Mapa de Dependências")
        st.caption("As colunas representam os semestres ideais. Linhas vermelhas indicam pré-requisitos que você ainda não cumpriu.")
        
        # Configuração Global do Gráfico
        graph = graphviz.Digraph()
        graph.attr(rankdir='LR') # Left to Right
        graph.attr(splines='ortho') # Linhas retas/angulares (menos bagunça que curvas)
        graph.attr(nodesep='0.4') # Espaço entre nós
        graph.attr(ranksep='1.0') # Espaço entre semestres

        # Cores
        color_map = {
            'Concluído': {'fill': "#024419", 'border': "#000000", 'font': "#BCFCD5"}, # Verde Suave
            'Cursando':  {'fill': "#011f46", 'border': "#000000", 'font': "#a8bcff"}, # Azul Suave
            'Futuro':    {'fill': "#A70000", 'border': "#000000", 'font': "#fdcbcb"}  # Cinza
        }

        # Agrupa matérias por semestre para criar os "Clusters"
        # Garante que Semestre_Ref seja numérico e trata erros
        df_mat['Semestre_Ref'] = pd.to_numeric(df_mat['Semestre_Ref'], errors='coerce').fillna(99).astype(int)
        semestres_unicos = sorted(df_mat['Semestre_Ref'].unique())

        # Adiciona nós (bolinhas) organizados por semestre
        for sem in semestres_unicos:
            if sem == 99: continue # Pula semestres inválidos se houver
            
            # Subgrafo (Cluster) do Semestre
            with graph.subgraph(name=f'cluster_{sem}') as c:
                # Verifica se o semestre está 100% concluído para pintar o fundo
                materias_semestre = df_mat[df_mat['Semestre_Ref'] == sem]
                todas_concluidas = all(materias_semestre['Status'] == 'Concluído')
                
                label_sem = f"{sem}º Semestre" + (" ✅" if todas_concluidas else "")
                c.attr(label=label_sem)
                c.attr(style='filled')
                c.attr(color="#00ff4c" if todas_concluidas else '#ffffff') # Fundo verde claro se 100%
                
                for _, row in materias_semestre.iterrows():
                    mat = row['Materia']
                    status = row['Status']
                    style = color_map.get(status, color_map['Futuro'])
                    
                    # Cria o Nó
                    # Shape 'box' economiza espaço. 'Mrecord' permite formatação interna se precisar.
                    c.node(mat, label=mat, 
                           shape='box', 
                           style='filled,rounded', 
                           fillcolor=style['fill'], 
                           color=style['border'], 
                           fontcolor=style['font'],
                           fontsize='10')

        # Adiciona as Arestas (Setas) DEPOIS de criar todos os nós
        # Isso evita que o graphviz crie nós fantasmas fora dos clusters
        lista_materias_existentes = set(df_mat['Materia'].unique())
        
        for _, row in df_mat.iterrows():
            destino = row['Materia']
            prereqs = row['Pre_Requisito'] # Lista
            
            if isinstance(prereqs, list):
                for origem in prereqs:
                    if origem in lista_materias_existentes:
                        # Define cor da seta
                        # Se o pré-requisito NÃO está concluído, a seta é vermelha (BLOQUEIO)
                        status_origem = df_mat[df_mat['Materia'] == origem]['Status'].values[0]
                        
                        if status_origem == 'Concluído':
                            edge_color = '#cbd5e1' # Cinza claro (já passou, não bloqueia mais)
                            penwidth = '1'
                        else:
                            edge_color = '#ef4444' # Vermelho (Alerta de bloqueio)
                            penwidth = '2'
                            
                        graph.edge(origem, destino, color=edge_color, penwidth=penwidth)

        # Renderiza
        try:
            st.graphviz_chart(graph, use_container_width=True)
        except Exception as e:
            st.error(f"Erro ao gerar gráfico. Verifique se o Graphviz está instalado no sistema. Detalhe: {e}")

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

    # ==============================================================================
    # MODO 3: LMS GAMIFICADO & GESTÃO DA MATÉRIA
    # ==============================================================================
    else:
        materia_atual = view_mode
        st.title(f"🥋 Dojo: {materia_atual}")
        
        # Filtra dados da matéria atual
        # ATENÇÃO: Adicione df_rec no desempacotamento lá no início do render_page:
        # df_conf, df_hor, df_mat, df_aval, df_top, df_rec = load_data() 
        
        my_aval = df_aval[df_aval['Materia'] == materia_atual].copy()
        my_top = df_top[df_top['Materia'] == materia_atual].copy()
        my_rec = df_rec[df_rec['Materia'] == materia_atual].copy()

        # --- HUD DO JOGADOR (XP & STATUS) ---
        if not my_top.empty:
            total_tops = len(my_top)
            dominados = len(my_top[my_top['Status'] == 'Dominado'])
            xp = int((dominados / total_tops) * 100)
            
            c_xp, c_msg = st.columns([3, 1])
            c_xp.progress(xp, text=f"Nível de Domínio (XP): {xp}%")
            if xp == 100: c_msg.markdown("🏆 **MESTRE!**")
            elif xp > 50: c_msg.markdown("⚔️ **Veterano**")
            else: c_msg.markdown("🌱 **Novato**")
        
        st.divider()

        # ABAS DO SISTEMA
        tab_kanban, tab_provas, tab_recursos, tab_pomodoro = st.tabs([
            "📋 Kanban de Tópicos", 
            "📝 Avaliações & Média", 
            "📚 Biblioteca (Links)",
            "⏱️ Foco (Pomodoro)"
        ])

        # --- ABA 1: KANBAN (TOPICOS) ---
        with tab_kanban:
            st.caption("Use o método Kanban: Mova os cards da esquerda para a direita.")
            
            c_todo, c_doing, c_done = st.columns(3)
            
            # Funções auxiliares de visualização
            def render_kanban_col(title, status_filter, color, next_status=None):
                st.markdown(f"### :{color}[{title}]")
                itens = my_top[my_top['Status'] == status_filter]
                
                with st.container(border=True):
                    if itens.empty:
                        st.caption("Vazio...")
                    
                    for idx, row in itens.iterrows():
                        st.markdown(f"**{row['Topico']}**")
                        
                        # Botões de Movimento
                        b_col1, b_col2 = st.columns(2)
                        if status_filter != "Dominado":
                            if b_col1.button("➡️ Avançar", key=f"next_{idx}"):
                                df_top.at[idx, 'Status'] = next_status
                                save_data(df_top, "Fac_Topicos")
                                st.rerun()
                        
                        if b_col2.button("🗑️", key=f"del_top_{idx}"):
                            df_top.drop(idx, inplace=True)
                            save_data(df_top, "Fac_Topicos")
                            st.rerun()
                        st.divider()

            with c_todo: render_kanban_col("A Fazer", "A Fazer", "red", "Estudando")
            with c_doing: render_kanban_col("Estudando", "Estudando", "orange", "Dominado")
            with c_done: render_kanban_col("Dominado", "Dominado", "green", None)

            # Adicionar Novo Tópico
            with st.expander("➕ Adicionar Novos Tópicos"):
                with st.form("add_topic"):
                    novo_t = st.text_area("Digite os tópicos (um por linha)")
                    if st.form_submit_button("Adicionar"):
                        lista_novos = [t.strip() for t in novo_t.split("\n") if t.strip()]
                        for item in lista_novos:
                            n = {"Materia": materia_atual, "Topico": item, "Status": "A Fazer"}
                            df_top = pd.concat([df_top, pd.DataFrame([n])], ignore_index=True)
                        save_data(df_top, "Fac_Topicos")
                        st.rerun()

        # --- ABA 2: AVALIAÇÕES (COM CÁLCULO DE MÉDIA E VÍNCULO) ---
        with tab_provas:
            c1, c2 = st.columns([2, 1])
            
            with c1:
                st.subheader("Boletim")
                if not my_aval.empty:
                    # Editor de Notas
                    edited_aval = st.data_editor(
                        my_aval,
                        column_config={
                            "Materia": None,
                            "Topicos_Ref": st.column_config.ListColumn("O que cai?"),
                            "Peso": st.column_config.NumberColumn("Peso", min_value=0.0, step=0.1),
                            "Nota": st.column_config.NumberColumn("Sua Nota", min_value=0.0, max_value=10.0),
                            "Concluido": st.column_config.CheckboxColumn("Feito?"),
                        },
                        hide_index=True,
                        key="editor_provas_materia"
                    )
                    
                    # Botão Salvar Notas
                    if st.button("💾 Atualizar Notas"):
                        # Atualiza o dataframe original com as edições desta matéria
                        df_aval.update(edited_aval)
                        save_data(df_aval, "Fac_Avaliacoes")
                        st.success("Boletim atualizado!")
                        st.rerun()

            # Painel de Média (Direita)
            with c2:
                st.subheader("Performance")
                if not my_aval.empty:
                    # Filtra só o que já foi feito para calcular a média atual
                    feitos = my_aval[my_aval['Concluido'] == True]
                    
                    if not feitos.empty and feitos['Peso'].sum() > 0:
                        media_pond = (feitos['Nota'] * feitos['Peso']).sum() / feitos['Peso'].sum()
                        
                        delta_color = "normal" if media_pond >= 6 else "inverse"
                        st.metric("Média Atual (Ponderada)", f"{media_pond:.2f}", delta="Meta: 6.0", delta_color=delta_color)
                        
                        # Simulação: Quanto preciso tirar?
                        restantes = my_aval[my_aval['Concluido'] == False]
                        if not restantes.empty:
                            peso_restante = restantes['Peso'].sum()
                            peso_feito = feitos['Peso'].sum()
                            nota_atual_acumulada = (feitos['Nota'] * feitos['Peso']).sum()
                            
                            # Fórmula: (Acumulado + X * PesoRestante) / PesoTotal >= 6
                            # X >= (6 * PesoTotal - Acumulado) / PesoRestante
                            peso_total = peso_feito + peso_restante
                            meta_final = 6.0
                            
                            nota_nec = (meta_final * peso_total - nota_atual_acumulada) / peso_restante
                            
                            if nota_nec <= 0:
                                st.success("🎉 Você já passou matematicamente!")
                            elif nota_nec > 10:
                                st.error(f"💀 Impossível passar (Precisa de {nota_nec:.1f})")
                            else:
                                st.warning(f"🎯 Precisa de média **{nota_nec:.1f}** nas próximas.")
                    else:
                        st.info("Nenhuma prova concluída ainda.")

            # Criar Nova Prova com Vínculo de Tópicos
            st.divider()
            with st.expander("📅 Agendar Nova Prova/Trabalho"):
                with st.form("new_exam"):
                    c_n, c_d, c_p = st.columns([2, 1, 1])
                    nome_p = c_n.text_input("Nome (Ex: P1)")
                    data_p = c_d.date_input("Data")
                    peso_p = c_p.number_input("Peso", 0.0, 10.0, 1.0)
                    
                    # O PULO DO GATO: Selecionar tópicos existentes
                    opcoes_topicos = my_top['Topico'].tolist()
                    tops_sel = st.multiselect("Quais tópicos vão cair?", options=opcoes_topicos)
                    
                    if st.form_submit_button("Agendar"):
                        n = {
                            "Materia": materia_atual, "Nome": nome_p, "Data": data_p, 
                            "Peso": peso_p, "Nota": 0.0, "Concluido": False,
                            "Topicos_Ref": tops_sel # Salva a lista
                        }
                        df_aval = pd.concat([df_aval, pd.DataFrame([n])], ignore_index=True)
                        save_data(df_aval, "Fac_Avaliacoes")
                        st.rerun()

        # --- ABA 3: BIBLIOTECA (RECURSOS) ---
        with tab_recursos:
            st.info("Centralize aqui PDFs, links do Drive, vídeos do YouTube, etc.")
            
            # Adicionar Recurso
            c_add, c_list = st.columns([1, 2])
            
            with c_add:
                with st.form("add_rec"):
                    r_nome = st.text_input("Nome do Recurso")
                    r_link = st.text_input("Link (URL)")
                    r_tipo = st.selectbox("Tipo", ["PDF", "Vídeo", "Site", "Drive", "Outro"])
                    if st.form_submit_button("Salvar"):
                        nr = {"Materia": materia_atual, "Nome": r_nome, "Link": r_link, "Tipo": r_tipo}
                        df_rec = pd.concat([df_rec, pd.DataFrame([nr])], ignore_index=True)
                        save_data(df_rec, "Fac_Recursos")
                        st.rerun()
            
            with c_list:
                if not my_rec.empty:
                    for _, row in my_rec.iterrows():
                        icones = {"PDF": "📄", "Vídeo": "▶️", "Site": "🔗", "Drive": "📁", "Outro": "📦"}
                        ico = icones.get(row['Tipo'], "📄")
                        st.markdown(f"**{ico} [{row['Nome']}]({row['Link']})**")
                else:
                    st.caption("Nenhum material salvo.")

        # --- ABA 4: POMODORO (SIMPLES) ---
        with tab_pomodoro:
            st.subheader("⏱️ Timer de Foco")
            c_timer, c_config = st.columns(2)
            
            with c_config:
                tempo_min = st.number_input("Minutos de Foco", 1, 120, 25)
                st.caption("A técnica Pomodoro sugere 25min focado + 5min descanso.")
            
            with c_timer:
                if st.button("🔥 Iniciar Foco"):
                    progress_text = "Focando... Não saia desta tela!"
                    my_bar = st.progress(0, text=progress_text)
                    total_sec = tempo_min * 60
                    
                    for percent_complete in range(100):
                        time.sleep(total_sec / 100)
                        my_bar.progress(percent_complete + 1, text=f"Focando... {percent_complete+1}%")
                    
                    st.balloons()
                    st.success("Sessão concluída! Descanse.")