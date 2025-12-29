import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os

from modules import conexoes

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

    return df_conf, df_h, df_m, df_a, df_t

def save_data(df, aba):
    # Converte tudo para string antes de subir para evitar erros de serialização
    df_save = df.copy()
    if "Data" in df_save.columns: df_save["Data"] = df_save["Data"].astype(str)
    conexoes.save_gsheet(aba, df_save)

def render_page():
    st.header("🎓 Engenharia Acadêmica")
    df_conf, df_hor, df_mat, df_aval, df_top = load_data()
    
    # --- DETECTOR DE FÉRIAS ---
    hoje = date.today()
    inicio_sem = pd.to_datetime(df_conf.iloc[0]['Inicio']).date()
    fim_sem = pd.to_datetime(df_conf.iloc[0]['Fim']).date()
    em_ferias = not (inicio_sem <= hoje <= fim_sem)

    # --- SIDEBAR & NAVEGAÇÃO ---
    with st.sidebar:
        st.subheader("📅 Calendário")
        c1, c2 = st.columns(2)
        ini = c1.date_input("Início", inicio_sem)
        fim = c2.date_input("Fim", fim_sem)
        
        if ini != inicio_sem or fim != fim_sem:
            df_conf.at[0, 'Inicio'] = str(ini)
            df_conf.at[0, 'Fim'] = str(fim)
            save_data(df_conf, "Fac_Config")
            st.rerun()
            
        st.divider()
        cursando = df_mat[df_mat['Status'] == 'Cursando']['Materia'].tolist()
        view_mode = st.radio("Visão", ["Dashboard & Horários"] + cursando + ["Grade Curricular (CRUD)"])

    # ==============================================================================
    # MODO 1: DASHBOARD
    # ==============================================================================
    if view_mode == "Dashboard & Horários":
        
        # --- BLOCO SUPERIOR (Contexto) ---
        if em_ferias:
            st.balloons()
            st.markdown("### 🏖️ Status: Férias / Pré-Matrícula")
            st.info("Aproveite para organizar a grade do próximo semestre abaixo. A ansiedade agradece! 😉")
        else:
            # Progresso Semestre (Só aparece se estiver rolando)
            total = (fim_sem - inicio_sem).days
            passados = (hoje - inicio_sem).days
            restantes = (fim_sem - hoje).days
            perc = max(0.0, min(1.0, passados / total)) if total > 0 else 0
            
            st.progress(perc)
            c1, c2 = st.columns([3, 1])
            c1.caption(f"Semestre: {perc*100:.1f}% concluído")
            c2.metric("Faltam", f"{restantes}d")
            
            # Aulas de Hoje
            st.subheader("📅 Aulas de Hoje")
            dias_map = {0:"Segunda", 1:"Terça", 2:"Quarta", 3:"Quinta", 4:"Sexta", 5:"Sábado", 6:"Domingo"}
            hoje_str = dias_map[hoje.weekday()]
            
            aulas = df_hor[df_hor['Dia_Semana'] == hoje_str].sort_values("Hora_Inicio")
            if not aulas.empty:
                for _, row in aulas.iterrows():
                    with st.container(border=True):
                        c_t, c_m, c_s = st.columns([1, 3, 1])
                        c_t.write(f"**{row['Hora_Inicio']}**")
                        c_m.write(row['Materia'])
                        c_s.write(f"📍 {row['Sala']}")
            else:
                st.info(f"Sem aulas nesta {hoje_str}.")

        st.divider()
        
        # --- EDITOR DE HORÁRIOS (AGORA SEMPRE VISÍVEL) ---
        # Assim você pode planejar nas férias!
        
        msg_expander = "✏️ Planejar Grade Horária (Próximo Semestre)" if em_ferias else "✏️ Editar Grade Horária Atual"
        with st.expander(msg_expander, expanded=em_ferias): # Já vem aberto nas férias pra facilitar
            st.caption("Monte sua grade semanal aqui.")
            
            # Prepara lista de dias
            dias_semana_list = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"]
            
            edited = st.data_editor(
                df_hor,
                column_config={
                    "Dia_Semana": st.column_config.SelectboxColumn("Dia", options=dias_semana_list, required=True),
                    "Hora_Inicio": st.column_config.TimeColumn("Início", format="HH:mm", step=1800),
                    "Materia": st.column_config.SelectboxColumn("Matéria", options=cursando, required=True),
                    "Sala": st.column_config.TextColumn("Sala/Bloco"),
                },
                use_container_width=True, num_rows="dynamic", key="h_editor"
            )
            
            if not df_hor.equals(edited):
                save_csv(edited, PATH_HORARIOS)
                st.rerun()

        # Próximas Provas (Só faz sentido mostrar se não estiver de férias ou se tiver algo agendado)
        if not em_ferias or not df_aval.empty:
            st.subheader("🔥 Próximas Avaliações")
            if not df_aval.empty:
                df_aval['Data'] = pd.to_datetime(df_aval['Data']).dt.date
                prox = df_aval[
                    (df_aval['Data'] >= hoje) & 
                    (df_aval['Concluido'] == False)
                ].sort_values("Data").head(5)
                
                if not prox.empty:
                    for _, row in prox.iterrows():
                        dias_para = (row['Data'] - hoje).days
                        msg = "É HOJE!" if dias_para == 0 else f"Faltam {dias_para} dias"
                        st.write(f"**{row['Materia']}** - {row['Nome']} ({row['Data'].strftime('%d/%m')}) | {msg}")
                elif not em_ferias:
                    st.success("Sem provas próximas.")

    # ==============================================================================
    # MODO 2: GRADE (CRUD COMPLETO)
    # ==============================================================================
    elif view_mode == "Grade Curricular (CRUD)":
        st.subheader("🗺️ Gestão de Matérias")
        
        tab_list, tab_add, tab_del = st.tabs(["📋 Lista & Status", "➕ Nova Matéria", "🗑️ Excluir"])
        
        with tab_list:
            st.data_editor(
                df_mat,
                column_config={
                    "Status": st.column_config.SelectboxColumn(options=["Futuro", "Cursando", "Concluído"]),
                },
                use_container_width=True, num_rows="dynamic", key="grade_vis"
            )
            st.caption("Para salvar edições de status, o Streamlit atualiza automaticamente ao interagir.")

        with tab_add:
            c1, c2, c3 = st.columns([2, 1, 1])
            nm = c1.text_input("Nome")
            req = c2.text_input("Pré-req")
            stt = c3.selectbox("Status", ["Futuro", "Cursando", "Concluído"])
            if st.button("Cadastrar"):
                if nm:
                    n = {"Materia": nm, "Semestre_Ref": "-", "Status": stt, "Pre_Requisito": req, "Professor": "-"}
                    df_mat = pd.concat([df_mat, pd.DataFrame([n])], ignore_index=True)
                    save_csv(df_mat, PATH_MATERIAS)
                    st.success("Cadastrado!")
                    st.rerun()

        with tab_del:
            st.warning("⚠️ Atenção: Excluir uma matéria apagará todas as provas, horários e tópicos vinculados a ela.")
            
            for idx, row in df_mat.iterrows():
                col_nome, col_status, col_btn = st.columns([3, 1, 1])
                col_nome.write(f"**{row['Materia']}**")
                col_status.write(f"_{row['Status']}_")
                
                if col_btn.button("Excluir Permanente", key=f"del_m_{idx}"):
                    target = row['Materia']
                    
                    # Cascade Delete
                    df_mat = df_mat.drop(idx)
                    save_csv(df_mat, PATH_MATERIAS)
                    
                    df_aval = df_aval[df_aval['Materia'] != target]
                    save_csv(df_aval, PATH_AVALIACOES)
                    
                    df_top = df_top[df_top['Materia'] != target]
                    save_csv(df_top, PATH_TOPICOS)
                    
                    df_hor = df_hor[df_hor['Materia'] != target]
                    save_csv(df_hor, PATH_HORARIOS)
                    
                    st.toast(f"Matéria '{target}' e dados vinculados apagados.")
                    st.rerun()
                st.markdown("---")

    # ==============================================================================
    # MODO 3: LMS DA MATÉRIA
    # ==============================================================================
    else:
        materia_atual = view_mode
        st.title(f"📘 {materia_atual}")
        
        if not em_ferias:
            dia_str = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"][hoje.weekday()]
            aulas_hj = df_hor[(df_hor['Materia'] == materia_atual) & (df_hor['Dia_Semana'] == dia_str)]
            if not aulas_hj.empty:
                infos = [f"{r['Hora_Inicio']} ({r['Sala']})" for _, r in aulas_hj.iterrows()]
                st.info(f"📍 **Aula Hoje:** {' | '.join(infos)}")

        t_provas, t_cont, t_resumo = st.tabs(["📝 Avaliações", "🧠 Conteúdo", "📊 Notas"])
        
        with t_provas:
            with st.expander("Nova Prova/Trabalho"):
                c1, c2, c3 = st.columns(3)
                pn = c1.text_input("Nome")
                pd_ = c2.date_input("Data")
                pp = c3.number_input("Peso", 0.1, 10.0, 1.0)
                if st.button("Agendar"):
                    n = {"Materia": materia_atual, "Nome": pn, "Data": pd_, "Peso": pp, "Nota": 0.0, "Concluido": False}
                    df_aval = pd.concat([df_aval, pd.DataFrame([n])], ignore_index=True)
                    save_csv(df_aval, PATH_AVALIACOES)
                    st.rerun()
            
            provas_mat = df_aval[df_aval['Materia'] == materia_atual].copy()
            if not provas_mat.empty:
                provas_mat['Data'] = pd.to_datetime(provas_mat['Data']).dt.date
                edited_p = st.data_editor(
                    provas_mat,
                    column_config={
                        "Materia": None,
                        "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                        "Nota": st.column_config.NumberColumn(min_value=0.0, max_value=10.0)
                    },
                    use_container_width=True, hide_index=True
                )
                if not edited_p.equals(provas_mat):
                    for i, r in edited_p.iterrows():
                        mask = (df_aval['Materia'] == materia_atual) & (df_aval['Nome'] == r['Nome'])
                        if mask.any():
                            df_aval.loc[mask, 'Nota'] = r['Nota']
                            df_aval.loc[mask, 'Concluido'] = r['Concluido']
                    save_csv(df_aval, PATH_AVALIACOES)
                    st.rerun()
        
        with t_cont:
            c1, c2 = st.columns([3, 1])
            nt = c1.text_input("Tópico")
            if c2.button("Add"):
                t = {"Materia": materia_atual, "Topico": nt, "Prova_Ref": "Geral", "Teoria_Ok": False, "Exercicio_Ok": False, "Revisao_Ok": False}
                df_top = pd.concat([df_top, pd.DataFrame([t])], ignore_index=True)
                save_csv(df_top, PATH_TOPICOS)
                st.rerun()
            
            tops = df_top[df_top['Materia'] == materia_atual]
            if not tops.empty:
                st.write("---")
                for idx, row in tops.iterrows():
                    c_txt, c_t, c_e, c_r, c_del = st.columns([3, 1, 1, 1, 0.5])
                    c_txt.markdown(f"**{row['Topico']}**")
                    t_ok = c_t.checkbox("Teoria", row['Teoria_Ok'], key=f"t{idx}")
                    e_ok = c_e.checkbox("Exerc.", row['Exercicio_Ok'], key=f"e{idx}")
                    r_ok = c_r.checkbox("Rev.", row['Revisao_Ok'], key=f"r{idx}")
                    
                    if (t_ok!=row['Teoria_Ok']) or (e_ok!=row['Exercicio_Ok']) or (r_ok!=row['Revisao_Ok']):
                        df_top.at[idx, 'Teoria_Ok'] = t_ok
                        df_top.at[idx, 'Exercicio_Ok'] = e_ok
                        df_top.at[idx, 'Revisao_Ok'] = r_ok
                        save_csv(df_top, PATH_TOPICOS)
                        st.rerun()
                    
                    if c_del.button("x", key=f"d{idx}"):
                        df_top = df_top.drop(idx)
                        save_csv(df_top, PATH_TOPICOS)
                        st.rerun()

        with t_resumo:
            notas = provas_mat[provas_mat['Concluido'] == True]
            if not notas.empty:
                pond = (notas['Nota'] * notas['Peso']).sum()
                ptot = notas['Peso'].sum()
                media = pond/ptot if ptot > 0 else 0
                st.metric("Média", f"{media:.2f}", delta="Aprovado" if media>=6 else "Reprovado", delta_color="normal" if media>=6 else "inverse")