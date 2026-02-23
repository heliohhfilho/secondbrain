import streamlit as st
import pandas as pd
from modules import conexoes
from datetime import date, timedelta

def save_data(df, aba):
    df_save = df.copy()

    for col in ["Data", "Status", "Concluido", "Ativo"]:
        if col in df_save.columns:
            df_save[col] = df_save[col].astype(str)

    conexoes.save_gsheet(aba, df_save)

@st.cache_data(ttl=600)
def load_data():

    cols_log = ["Data", "Tipo", "Subtipo", "Valor", "Unidade", "Detalhe"]
    df_log = conexoes.load_gsheet("Log_Produtividade", cols_log)
    if not df_log.empty:
        df_log["Valor"] = pd.to_numeric(df_log["Valor"], errors='coerce').fillna(0)

    cols_h_conf = ["Habito", "Categoria", "Ativo"]
    df_h_conf = conexoes.load_gsheet("Habitos_Config", cols_h_conf)
    if df_h_conf.empty:
        defaults = [
            {"Habito": "Acordar cedo", "Categoria": "Rotina", "Ativo": "True"},
            {"Habito": "Exercicio Fisico", "Categoria": "Saúde", "Ativo": "True"},
            {"Habito": "Leitura", "Categoria": "Inteligência", "Ativo": "True"}
        ]
        df_h_conf = pd.DataFrame(defaults)
        conexoes.save_gsheet("Habitos_Config", df_h_conf)

    else:
        df_h_conf["Ativo"] = df_h_conf["Ativo"].astype(str).str.upper() == "TRUE"


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
        df_h_check["Status"] = df_h_check["Status"].astype(str).str.upper() == "TRUE"

    return df_log, df_h_conf, df_h_check

def calcular_streak(df_checks, habito_nome):
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

def atualizar_leitura_externa(livro_nome, paginas_lidas_hoje):
    cols = ["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"]
    df = conexoes.load_gsheet("Leituras", cols)
    if df.empty: return False

    mask = df['Titulo'] == livro_nome
    acabou_agora = False # Flag de controle

    if mask.any():
        idx = df[mask].index[0]
        pag_atual = pd.to_numeric(df.at[idx, 'Paginas_Lidas'], errors='coerce')
        total = pd.to_numeric(df.at[idx, 'Total_Paginas'], errors='coerce')
        
        nova_pag = min(pag_atual + paginas_lidas_hoje, total)
        
        if pag_atual < total and nova_pag >= total:
            df.at[idx, 'Status'] = "Concluído"
            acabou_agora = True
            
        df.at[idx, 'Paginas_Lidas'] = nova_pag
        conexoes.save_gsheet("Leituras", df)
        
    return acabou_agora

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

def render_page():
    st.header(" Produtividade ")

    df_log, df_h_conf, df_h_check = load_data()

    tab_habitos, tab_deep_work, tab_tarefas, tab_analytics, tab_admin = st.tabs([
        "✅ Rotina & Hábitos", 
        "⚡ Sessões de Foco", 
        "📝 To-Do List", 
        "📊 BI Pessoal",
        "🛠️ Gerenciar Dados"
    ])

    with tab_habitos:
        st.subheader("🔥 Streak & Disciplina (Hoje)")

        habitos_ativos = df_h_conf[df_h_conf['Ativo'] == True]
 
        with st.expander("⚙️ Gerenciar Meus Hábitos (Adicionar/Remover)"):
            c_add1, c_add2, c_add3 = st.columns([2, 1, 1])
            novo_h = c_add1.text_input("Nome do Hábito")
            cat_h = c_add2.text_input("Categoria", "Geral")
            if c_add3.button("Criar Hábito"):
                if novo_h:
                    novo_reg = {"Habito": novo_h.strip(), "Categoria": cat_h.strip(), "Ativo": True}
                    df_h_conf = pd.concat([df_h_conf, pd.DataFrame([novo_reg])], ignore_index=True)
                    save_data(df_h_conf, "Habitos_Config")
                    st.cache_data.clear()
                    st.rerun()

            st.divider()
            st.caption("Desativar Hábitos:")
            for idx, row in habitos_ativos.iterrows():
                cols = st.columns([4, 1])
                cols[0].write(f"**{row['Habito']}** ({row['Categoria']})")

                if cols[1].button("🗑️", key=f"del_h_{idx}"):
                    df_h_conf.at[idx, 'Ativo'] = False

                    save_data(df_h_conf, "Habitos_Config")
                    st.cache_data.clear()
                    st.rerun()

        habitos_ativos = df_h_conf[df_h_conf['Ativo'] == True]

        if habitos_ativos.empty:
            st.info("Cadastre hábitos no menu acima")
        else:
            st.divider()

            hoje = date.today()

            if not df_h_check.empty:
                df_h_check['Data'] = pd.to_datetime(df_h_check['Data']).dt.date

                habitos_feitos_hoje = df_h_check[
                    (df_h_check['Data'] == hoje) &
                    (df_h_check['Status'] == True)
                ]['Habito'].tolist()
            else:
                habitos_feito_hoje = []

            habitos_pendentes = habitos_ativos[~habitos_ativos['Habito'].isin(habitos_feitos_hoje)]

            st.subheader(" Hábitos de Hoje ")

            if habitos_pendentes.empty:
                st.success("Todos os hábitos concluidos hoje.")
                st.balloons()

            else:
                with st.form("form_habitos_hoje"):
                    st.write("Marca os habitos que concluiste e guarda de uma só vez:")

                    resultados_checkbox = {}

                    for _, row in habitos_pendentes.iterrows():
                        habito = row['Habito']
                        resultados_checkbox[habito] = st.checkbox(f"{habito} ({row['Categoria']})")

                    submitted = st.form_submit_button("Salvar Hábitos Marcados", type="primary")

                    if submitted:
                        novos_registros = []
                        for habito, foi_feito in resultados_checkbox.items():
                            if foi_feito:
                                novos_registros.append({"Data": hoje, "Habito": habito, "Status": True})

                        if novos_registros:
                            df_h_check = pd.concat([df_h_check, pd.DataFrame(novos_registros)], ignore_index=True)
                            save_data(df_h_check, "Habitos_Log")

                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.warning("Não marcaste nenhum hábito. Seleciona pelo menos um para guardar!")

            st.divider()
            st.subheader("📊 O Meu Progresso")
            
            # Aqui mostramos TODOS os hábitos ativos (os feitos hoje e os não feitos)
            for _, row in habitos_ativos.iterrows():
                habito = row['Habito']
                
                # Calcula Streak usando a tua função
                streak, consistencia = calcular_streak(df_h_check, habito)
                
                # Feedback visual extra: Mostra se já está concluído hoje no título do card
                badge_hoje = "✅ Feito hoje" if habito in habitos_feitos_hoje else "⏳ Pendente"
                
                # Visual do Card (sem a checkbox gigante)
                with st.container(border=True):
                    c_info, c_stats = st.columns([3, 2])
                    
                    with c_info:
                        st.markdown(f"#### {habito} `{badge_hoje}`")
                        st.caption(f"Categoria: {row['Categoria']}")
                        
                        # A tua Lógica do Segundo Cérebro
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

                    with c_stats:
                        st.metric("Streak", f"{streak} dias", delta="Fogo!" if streak > 5 else None)
                        st.metric("30 Dias", f"{int(consistencia)}%", help="Frequência nos últimos 30 dias")

    with tab_deep_work:
        st.subheader("Deep Work")

        tipo_sessao = st.radio("Atvidade", ["Leitura", "Cursos", "Faculdade"], horizontal=True)
        
        if tipo_sessao == "Leitura":
            try:
                df_l = conexoes.load_gsheet("Leituras", ["Titulo", "Autor", "Total_Paginas", "Paginas_Lidas", "Nota", "Status"])
                livros = df_l[df_l['Status'] == 'Lendo']['Titulo'].tolist()
            except: livros = []

            c1, c2 = st.columns(2)
            with st.form("registrar_leitura"):
                sel_livro = c1.selectbox("Livro", livros if livros else ["Nenhum"])
                qtd_pag = c2.number_input("Páginas Lidas", min_value=1, step=1)

                submitted = st.form_submit_button("Salvar Leitura", type="primary")

                if submitted:
                    if sel_livro != "Nenhum":
                        livro_finalizado = atualizar_leitura_externa(sel_livro, qtd_pag)
                        log = {"Data": date.today(), "Tipo": "Leitura", "Subtipo": sel_livro, "Valor": qtd_pag, "Unidade": "Paginas"}
                        df_log = pd.concat([df_log, pd.DataFrame([log])], ignore_index=True)

                        save_data(df_log, "Habitos_Log")

                        st.success("Progresso registrado!")

                        for _, row in habitos_ativos.iterrows():
                            habito = row['Habito']

                            if "LEITURA" in habito.upper() or "LER" in habito.upper():
                                novo_check = {"Data": date.today(), "Habito": habito, "Status": True}
                                df_h_check = pd.concat([df_h_check, pd.DataFrame([novo_check])], ignore_index=True)
                                save_data(df_h_check, "Habitos_Log")
                         
                                st.toast(f"✅ Hábito '{habito}' marcado automaticamente!")
                        
                        st.cache_data.clear()
                        st.rerun()

        elif tipo_sessao == "Cursos":
            df_c = conexoes.load_gsheet("Cursos", ["Curso", "Status"])
            cursos = df_c[df_c['Status'] == 'Em Andamento']['Curso'].tolist() if not df_c.empty else []
            
            with st.form("registrar_curso"):
                alvo = st.selectbox("O que estudou?", cursos)
                c1, c2 = st.columns(2)
                
                aulas = 0
                if alvo in cursos:
                    aulas = c2.number_input("Aulas Concluídas", 0, step=1)

                submitted = st.form_submit_button("Registrar Estudo", type="primary")

                if submitted:
                    if alvo in cursos and aulas > 0:
                        atualizar_curso_externo(alvo, aulas)

                    log_qtd = {
                        "Data": str(date.today()),
                        "Tipo": "Cursos",
                        "Subtipo": alvo,
                        "Valor": aulas,
                        "Unidade": "Aulas"
                    }

                    df_log = pd.concat([df_log, pd.DataFrame([log_qtd])], ignore_index=True)
                    save_data(df_log, "Log_Produtividade")
                    st.success("Foco registrado!")

        elif tipo_sessao == "Faculdade":
            df_f = conexoes.load_gsheet("Fac_Materias", ["Materia", "Status"])
            materias = df_f[df_f['Status'] == 'Cursando']['Materia'].tolist() if not df_f.empty else []

            alvo = st.selectbox("O que estudou?", ["Faculdade"] + materias)

            c1, c2 = st.columns(2)
            tempo = c1.number_input("Tempo Líquido (min)", 30, step=1)
        