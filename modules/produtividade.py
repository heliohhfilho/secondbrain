import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import os
import plotly.express as px

from modules import conexoes
def load_data():
    # 1. Tarefas
    cols_t = ["Tarefa", "Data", "Concluido", "Prioridade"]
    df_t = conexoes.load_gsheet("Tarefas", cols_t)
    if not df_t.empty:
        df_t["Concluido"] = df_t["Concluido"].astype(str).str.upper() == "TRUE"
        
    # 2. Log de Produtividade (Deep Work)
    cols_log = ["Data", "Tipo", "Subtipo", "Valor", "Unidade", "Detalhe"]
    df_log = conexoes.load_gsheet("Log_Produtividade", cols_log)
    if not df_log.empty:
        df_log["Valor"] = pd.to_numeric(df_log["Valor"], errors='coerce').fillna(0)

    # 3. Configuração de Hábitos
    cols_h_conf = ["Habito", "Categoria", "Ativo"]
    df_h_conf = conexoes.load_gsheet("Habitos_Config", cols_h_conf)
    if df_h_conf.empty:
        defaults = [
            {"Habito": "Acordar às 06h", "Categoria": "Rotina", "Ativo": "True"},
            {"Habito": "Exercício Físico", "Categoria": "Saúde", "Ativo": "True"},
            {"Habito": "Leitura Técnica", "Categoria": "Intelecto", "Ativo": "True"}
        ]
        df_h_conf = pd.DataFrame(defaults)
        conexoes.save_gsheet("Habitos_Config", df_h_conf)
    else:
        df_h_conf["Ativo"] = df_h_conf["Ativo"].astype(str).str.upper() == "TRUE"

    # 4. Log de Hábitos (Checks) - Refatorado para garantir estrutura
    cols_esperadas = ["Data", "Habito", "Status"]
    try:
        df_h_check = conexoes.load_gsheet("Habitos_Log", cols_esperadas)
        
        # Se o retorno for None ou não for um DataFrame, força criação
        if not isinstance(df_h_check, pd.DataFrame):
            df_h_check = pd.DataFrame(columns=cols_esperadas)
            
    except Exception:
        df_h_check = pd.DataFrame(columns=cols_esperadas)

    # Garantia extra: Se o DataFrame existe mas as colunas sumiram (planilha limpa)
    for col in cols_esperadas:
        if col not in df_h_check.columns:
            df_h_check[col] = None

    if not df_h_check.empty:
        df_h_check = df_h_check.dropna(subset=['Habito'])
        # Conversão booleana segura
        df_h_check["Status"] = df_h_check["Status"].astype(str).str.upper() == "TRUE"

    return df_t, df_log, df_h_conf, df_h_check

def save_data(df, aba):
    df_save = df.copy()
    # Converte tipos para GSheets (Data e Booleanos para string)
    for col in ["Data", "Status", "Concluido", "Ativo"]:
        if col in df_save.columns:
            df_save[col] = df_save[col].astype(str)
    conexoes.save_gsheet(aba, df_save)

# --- INTEGRAÇÃO ENTRE ABAS NA NUVEM ---
def atualizar_leitura_externa(livro_nome, paginas_lidas_hoje):
    cols = ["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"]
    df = conexoes.load_gsheet("Leituras", cols)
    if df.empty: return
    
    mask = df['Titulo'] == livro_nome
    if mask.any():
        idx = df[mask].index[0]
        pag_atual = pd.to_numeric(df.at[idx, 'Paginas_Lidas'], errors='coerce')
        total = pd.to_numeric(df.at[idx, 'Total_Paginas'], errors='coerce')
        nova_pag = min(pag_atual + paginas_lidas_hoje, total)
        df.at[idx, 'Paginas_Lidas'] = nova_pag
        if nova_pag >= total: df.at[idx, 'Status'] = "Concluído"
        conexoes.save_gsheet("Leituras", df)

def atualizar_curso_externo(curso_nome, aulas_hoje):
    cols = ["Curso", "Plataforma", "Total_Aulas", "Aulas_Feitas", "Link_Certificado", "Status"]
    df = conexoes.load_gsheet("Cursos", cols)
    if df.empty: return
    
    mask = df['Curso'] == curso_nome
    if mask.any():
        idx = df[mask].index[0]
        atual = pd.to_numeric(df.at[idx, 'Aulas_Feitas'], errors='coerce')
        total = pd.to_numeric(df.at[idx, 'Total_Aulas'], errors='coerce')
        novo = min(atual + aulas_hoje, total)
        df.at[idx, 'Aulas_Feitas'] = novo
        if novo >= total: df.at[idx, 'Status'] = "Concluído"
        conexoes.save_gsheet("Cursos", df)

# --- ENGINE DE STREAKS (Sequência) ---
def calcular_streak(df_checks, habito_nome):
    """Calcula dias consecutivos atuais e consistência mensal"""
    if df_checks.empty: return 0, 0
    
    # Filtra só esse hábito e datas únicas
    df_h = df_checks[(df_checks['Habito'] == habito_nome) & (df_checks['Status'] == True)].copy()
    if df_h.empty: return 0, 0
    
    df_h['Data'] = pd.to_datetime(df_h['Data']).dt.date
    dates = sorted(df_h['Data'].unique(), reverse=True)
    
    if not dates: return 0, 0

    hoje = date.today()
    ontem = hoje - timedelta(days=1)
    
    # Se não fez hoje nem ontem, streak quebrou
    if dates[0] != hoje and dates[0] != ontem:
        return 0, 0 # Streak atual é zero (mas vamos calcular consistência)

    streak = 1
    # Começa a contar de trás pra frente
    current_check = dates[0]
    
    for i in range(1, len(dates)):
        expected_prev = current_check - timedelta(days=1)
        if dates[i] == expected_prev:
            streak += 1
            current_check = dates[i]
        else:
            break
            
    # Consistência (Ultimos 30 dias)
    start_date = hoje - timedelta(days=29)
    count_30d = len([d for d in dates if d >= start_date])
    consistencia = (count_30d / 30) * 100
    
    return streak, consistencia

def render_page():
    st.header("🧠 Productive Mind (Hábitos & Foco)")
    
    df_t, df_log, df_h_conf, df_h_check = load_data()
    
    # --- ABAS ---
    tab_habitos, tab_deep, tab_tarefas, tab_analytics = st.tabs([
        "✅ Rotina & Hábitos", 
        "⚡ Sessões de Foco", 
        "📝 To-Do List", 
        "📊 BI Pessoal"
    ])

    # ==============================================================================
    # ABA 1: HABIT TRACKER (O Novo Recurso)
    # ==============================================================================
    with tab_habitos:
        st.subheader("🔥 Streak & Disciplina (Hoje)")
        
        # --- CONFIGURADOR DE HÁBITOS (SIDEBAR DO TAB) ---
        with st.expander("⚙️ Gerenciar Meus Hábitos (Adicionar/Remover)"):
            c_add1, c_add2, c_add3 = st.columns([2, 1, 1])
            novo_h = c_add1.text_input("Nome do Hábito")
            cat_h = c_add2.text_input("Categoria", "Geral")
            if c_add3.button("Criar Hábito"):
                if novo_h:
                    novo_reg = {"Habito": novo_h, "Categoria": cat_h, "Ativo": True}
                    df_h_conf = pd.concat([df_h_conf, pd.DataFrame([novo_reg])], ignore_index=True)
                    save_data(df_h_conf, "Habitos_Config")
                    st.rerun()
            
            # Listar para remover
            st.divider()
            st.caption("Desativar Hábitos:")
            for idx, row in df_h_conf.iterrows():
                if row['Ativo']:
                    cols = st.columns([4, 1])
                    cols[0].write(f"**{row['Habito']}** ({row['Categoria']})")
                    if cols[1].button("🗑️", key=f"del_h_{idx}"):
                        df_h_conf.at[idx, 'Ativo'] = False # Soft delete
                        save_data(df_h_conf, "Habitos_Config")
                        st.rerun()

        # --- O DASHBOARD DE HOJE ---
        habitos_ativos = df_h_conf[df_h_conf['Ativo'] == True]
        
        if habitos_ativos.empty:
            st.info("Cadastre hábitos no menu acima ⚙️")
        else:
            # Grid de Cards
            st.divider()
            
            # Garante formato de data
            df_h_check['Data'] = pd.to_datetime(df_h_check['Data']).dt.date
            hoje = date.today()

            for _, row in habitos_ativos.iterrows():
                habito = row['Habito']
                
                # Verifica se já fez hoje
                feito_hoje = not df_h_check[
                    (df_h_check['Habito'] == habito) & 
                    (df_h_check['Data'] == hoje) & 
                    (df_h_check['Status'] == True)
                ].empty

                # Calcula Streak
                streak, consistencia = calcular_streak(df_h_check, habito)
                
                # Visual do Card
                with st.container(border=True):
                    c_check, c_info, c_stats = st.columns([1, 4, 2])
                    
                    # Coluna 1: Checkbox gigante
                    fazer = c_check.checkbox("Feito", value=feito_hoje, key=f"chk_{habito}", label_visibility="collapsed")
                    
                    # Lógica de salvar/remover check
                    if fazer and not feito_hoje:
                        # Salva
                        new_check = {"Data": hoje, "Habito": habito, "Status": True}
                        df_h_check = pd.concat([df_h_check, pd.DataFrame([new_check])], ignore_index=True)
                        save_data(df_h_check, "Habitos_Log")
                        st.balloons()
                        st.rerun()
                    elif not fazer and feito_hoje:
                        # Remove (Desmarcou)
                        idx_del = df_h_check[
                            (df_h_check['Habito'] == habito) & 
                            (df_h_check['Data'] == hoje)
                        ].index
                        df_h_check = df_h_check.drop(idx_del)
                        save_data(df_h_check, "Habitos_Log")
                        st.rerun()

                    # Coluna 2: Informações e Status
                    with c_info:
                        st.markdown(f"#### {habito}")
                        st.caption(f"Categoria: {row['Categoria']}")
                        
                        # Análise do Segundo Cérebro
                        status_habito = "🌱 Iniciante"
                        cor_status = "grey"
                        if consistencia > 80: 
                            status_habito = "🔥 Hábito Formado"
                            cor_status = "green"
                        elif consistencia > 50:
                            status_habito = "🏗️ Construindo"
                            cor_status = "orange"
                        elif consistencia < 30 and streak == 0:
                            status_habito = "⚠️ Em Risco"
                            cor_status = "red"
                            
                        st.markdown(f"Status: :{cor_status}[**{status_habito}**]")

                    # Coluna 3: Métricas
                    with c_stats:
                        st.metric("Streak", f"{streak} dias", delta="Fogo!" if streak > 5 else None)
                        st.metric("30 Dias", f"{int(consistencia)}%", help="Frequência nos últimos 30 dias")

    # ==============================================================================
    # ABA 2: SESSÕES DE FOCO (Antigo Leitura/Estudo)
    # ==============================================================================
    with tab_deep:
        st.subheader("⏱️ Registrar Deep Work")
        st.caption("Aqui você registra a 'Quantidade' (Páginas, Aulas, Tempo).")
        
        tipo_sessao = st.radio("Atividade", ["📖 Leitura", "🎓 Estudo/Curso", "💼 Projeto/Geral"], horizontal=True)
        
        if tipo_sessao == "📖 Leitura":
            try:
                df_l = conexoes.load_gsheet("Leituras", ["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"])
                livros = df_l[df_l['Status'] == 'Lendo']['Titulo'].tolist()
            except: livros = []
            
            c1, c2 = st.columns(2)
            sel_livro = c1.selectbox("Livro", livros if livros else ["Nenhum"])
            qtd_pag = c2.number_input("Páginas Lidas", min_value=1)
            tempo = st.slider("Tempo (min)", 10, 180, 30, step=5)
            
            if st.button("Registrar Leitura"):
                if sel_livro != "Nenhum":
                    atualizar_leitura_externa(sel_livro, qtd_pag)
                    log = {"Data": date.today(), "Tipo": "Leitura", "Subtipo": sel_livro, "Valor": qtd_pag, "Unidade": "Páginas", "Detalhe": f"{tempo} min"}
                    df_log = pd.concat([df_log, pd.DataFrame([log])], ignore_index=True)
                    # Loga tempo também
                    df_log = pd.concat([df_log, pd.DataFrame([{"Data": date.today(), "Tipo": "Tempo Foco", "Subtipo": "Leitura", "Valor": tempo, "Unidade": "Minutos", "Detalhe": sel_livro}])], ignore_index=True)
                    save_data(df_log, "Habitos_Log")
                    st.success("Progresso registrado!")

        elif tipo_sessao == "🎓 Estudo/Curso":
            # Busca cursos ativos direto da nuvem
            df_c = conexoes.load_gsheet("Cursos", ["Curso", "Status"])
            cursos = df_c[df_c['Status'] == 'Em Andamento']['Curso'].tolist() if not df_c.empty else []
            
            # Busca matérias da faculdade direto da nuvem
            df_f = conexoes.load_gsheet("Fac_Materias", ["Materia", "Status"])
            materias = df_f[df_f['Status'] == 'Cursando']['Materia'].tolist() if not df_f.empty else []
            
            alvo = st.selectbox("O que estudou?", ["Curso Extra"] + cursos + ["Faculdade"] + materias)
            
            c1, c2 = st.columns(2)
            tempo = c1.number_input("Tempo Líquido (min)", 30, step=10)
            
            aulas = 0
            if alvo in cursos:
                aulas = c2.number_input("Aulas Concluídas", 0)
            
            detalhe = st.text_input("Resumo do que foi feito")
            
            if st.button("Registrar Estudo"):
                if alvo in cursos and aulas > 0:
                    atualizar_curso_externo(alvo, aulas)
                
                log = {"Data": str(date.today()), "Tipo": "Estudo", "Subtipo": alvo, "Valor": tempo, "Unidade": "Minutos", "Detalhe": detalhe}
                df_log = pd.concat([df_log, pd.DataFrame([log])], ignore_index=True)
                save_data(df_log, "Log_Produtividade") # <--- Salva na nuvem
                st.success("Foco registrado!")

        elif tipo_sessao == "💼 Projeto/Geral":
            proj = st.text_input("Projeto / Tarefa")
            tempo = st.number_input("Tempo (min)", 10, step=10)
            desc = st.text_area("Detalhes")
            if st.button("Registrar Trabalho"):
                log = {"Data": str(date.today()), "Tipo": "Trabalho", "Subtipo": proj, "Valor": tempo, "Unidade": "Minutos", "Detalhe": desc}
                df_log = pd.concat([df_log, pd.DataFrame([log])], ignore_index=True)
                save_data(df_log, "Log_Produtividade") # <--- Salva na nuvem
                st.success("Deep Work registrado!")

    # ==============================================================================
    # ABA 3: TAREFAS (TO-DO)
    # ==============================================================================
    with tab_tarefas:
        c1, c2 = st.columns([3, 1])
        t_nome = c1.text_input("Nova Tarefa")
        t_prio = c2.selectbox("Prioridade", ["Alta", "Média", "Baixa"])
        if st.button("Adicionar Tarefa"):
            t = {"Tarefa": t_nome, "Data": str(date.today()), "Concluido": "False", "Prioridade": t_prio}
            df_t = pd.concat([df_t, pd.DataFrame([t])], ignore_index=True)
            save_data(df_t, "Tarefas")
            st.rerun()

        if not df_t.empty:
            pend = df_t[df_t['Concluido'] == False]
            if not pend.empty:
                for idx, row in pend.iterrows():
                    c_chk, c_txt, c_del = st.columns([0.5, 4, 0.5])
                    if c_chk.checkbox("", key=f"t_{idx}"):
                        df_t.at[idx, 'Concluido'] = True
                        save_data(df_t, "Tarefas")
                        st.rerun()
                    c_txt.write(f"**{row['Tarefa']}** ({row['Prioridade']})")
                    if c_del.button("x", key=f"dt_{idx}"):
                        df_t = df_t.drop(idx)
                        save_data(df_t, "Tarefas")
                        st.rerun()
            else:
                st.info("Zero pendências! 🏖️")

    # ==============================================================================
    # ABA 4: ANALYTICS (EVOLUÇÃO DOS HÁBITOS)
    # ==============================================================================
    with tab_analytics:
        st.subheader("📊 Raio-X da Disciplina")
        
        if not df_h_check.empty:
            df_h_check['Data'] = pd.to_datetime(df_h_check['Data'])
            
            # Gráfico de Calor (Consistência Diária) - Simplificado em Barras por Dia
            daily_counts = df_h_check.groupby('Data').size().reset_index(name='Hábitos Feitos')
            st.caption("Hábitos Concluídos por Dia (Histórico)")
            st.bar_chart(daily_counts.set_index("Data"))
            
            st.divider()
            
            # Tabela de Performance por Hábito
            data_perf = []
            for _, row in habitos_ativos.iterrows():
                h = row['Habito']
                streak, cons = calcular_streak(df_h_check, h)
                total_checks = len(df_h_check[df_h_check['Habito'] == h])
                data_perf.append({
                    "Hábito": h,
                    "Categoria": row['Categoria'],
                    "Streak Atual": f"{streak} dias",
                    "Consistência (30d)": f"{int(cons)}%",
                    "Total Feito": total_checks
                })
            
            st.dataframe(pd.DataFrame(data_perf).set_index("Hábito"), width='stretch')
            
        else:
            st.warning("Comece a marcar seus hábitos para gerar gráficos!")