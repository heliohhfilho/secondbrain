import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

FILE_PATH = os.path.join('data', 'cursos.csv')

def load_data():
    # Colunas adaptadas para o contexto de cursos
    cols = ["Curso", "Plataforma", "Total_Aulas", "Aulas_Feitas", "Link_Certificado", "Status"]
    if not os.path.exists(FILE_PATH):
        return pd.DataFrame(columns=cols)
    
    df = pd.read_csv(FILE_PATH)
    
    # Garante que a coluna de link exista (caso adicione manualmente depois)
    if "Link_Certificado" not in df.columns:
        df["Link_Certificado"] = ""
    
    # Trata valores nulos no link para evitar erro visual
    df["Link_Certificado"] = df["Link_Certificado"].fillna("")
    
    return df

def save_data(df):
    df.to_csv(FILE_PATH, index=False)

def determine_status(feitas, total):
    if feitas > total: feitas = total # Trava de segurança
    
    if feitas == 0:
        return "Na Fila"
    elif feitas >= total:
        return "Concluído"
    else:
        return "Em Andamento"

def render_page():
    st.header("🎓 Meus Cursos e Certificações")
    
    df = load_data()

    # --- SIDEBAR: CADASTRO ---
    with st.sidebar:
        st.subheader("➕ Novo Curso")
        nome = st.text_input("Nome do Curso")
        plataforma = st.text_input("Plataforma (Udemy, Coursera...)")
        total_aulas = st.number_input("Total de Aulas", min_value=1, value=50)
        
        if st.button("Matricular"):
            if nome:
                novo = {
                    "Curso": nome, "Plataforma": plataforma, 
                    "Total_Aulas": total_aulas, "Aulas_Feitas": 0, 
                    "Link_Certificado": "", "Status": "Na Fila"
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Curso cadastrado!")
                st.rerun()

        st.divider()
        # Estimativa baseada em aulas por SEMANA (mais comum que por dia)
        ritmo = st.slider("Quantas aulas você faz por semana?", 1, 50, 5)

    # --- KPIs GERAIS ---
    if not df.empty:
        # Atualiza status baseado nas aulas
        df['Status'] = df.apply(lambda x: determine_status(x['Aulas_Feitas'], x['Total_Aulas']), axis=1)
        
        total_concluidos = len(df[df['Status'] == "Concluído"])
        total_andamento = len(df[df['Status'] == "Em Andamento"])
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Em Andamento", total_andamento)
        k2.metric("Concluídos", total_concluidos)
        # Calcula porcentagem global de conclusão de todos os cursos ativos
        ativos = df[df['Status'] == "Em Andamento"]
        if not ativos.empty:
            prog_geral = ativos['Aulas_Feitas'].sum() / ativos['Total_Aulas'].sum()
            k3.metric("Progresso Global (Ativos)", f"{prog_geral:.1%}")
        else:
            k3.metric("Progresso Global", "0%")
            
        st.divider()

    # --- FUNÇÃO DE EDIÇÃO (CRUD) ---
    def render_edit_controls(idx, row):
        with st.expander("⚙️ Editar / Certificado / Excluir", expanded=False):
            with st.form(key=f"form_curso_{idx}"):
                c1, c2 = st.columns(2)
                n_nome = c1.text_input("Curso", row['Curso'])
                n_plat = c2.text_input("Plataforma", row['Plataforma'])
                
                c3, c4 = st.columns(2)
                n_total = c3.number_input("Total Aulas", min_value=1, value=int(row['Total_Aulas']))
                n_link = c4.text_input("Link Certificado", row['Link_Certificado'])
                
                if st.form_submit_button("💾 Salvar Dados"):
                    df.at[idx, 'Curso'] = n_nome
                    df.at[idx, 'Plataforma'] = n_plat
                    df.at[idx, 'Total_Aulas'] = n_total
                    df.at[idx, 'Link_Certificado'] = n_link
                    # Recalcula status
                    df.at[idx, 'Status'] = determine_status(row['Aulas_Feitas'], n_total)
                    save_data(df)
                    st.rerun()

            if st.button("🗑️ Excluir Curso", key=f"del_c_{idx}", type="primary"):
                df.drop(idx, inplace=True)
                save_data(df)
                st.rerun()

    # --- ABAS ---
    tab_andamento, tab_fila, tab_concluidos = st.tabs(["💻 Em Andamento", "⏳ Fila de Espera", "🏆 Certificados"])

    # ==========================
    # ABA: EM ANDAMENTO
    # ==========================
    with tab_andamento:
        df_active = df[df['Status'] == "Em Andamento"]
        if df_active.empty: st.info("Nenhum curso em andamento. Puxe algo da fila!")
        
        for idx, row in df_active.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                
                with c1:
                    st.subheader(row['Curso'])
                    st.caption(f"Plataforma: {row['Plataforma']}")
                    prog = row['Aulas_Feitas'] / row['Total_Aulas']
                    st.progress(min(prog, 1.0))
                    st.write(f"**{int(prog*100)}%** ({int(row['Aulas_Feitas'])}/{int(row['Total_Aulas'])})")

                with c2:
                    # Atualização Rápida
                    novas_aulas = st.number_input(
                        "Aulas Concluídas", 0, int(row['Total_Aulas']), int(row['Aulas_Feitas']), key=f"aula_{idx}"
                    )
                    if novas_aulas != row['Aulas_Feitas']:
                        df.at[idx, 'Aulas_Feitas'] = novas_aulas
                        df.at[idx, 'Status'] = determine_status(novas_aulas, row['Total_Aulas'])
                        save_data(df)
                        st.rerun()

                # Estimativa Temporal
                restam = row['Total_Aulas'] - row['Aulas_Feitas']
                semanas = restam / ritmo
                dias = semanas * 7
                data_fim = datetime.now() + timedelta(days=dias)
                
                st.caption(f"📅 Ritmo: {ritmo} aulas/sem | Faltam {restam} aulas | Previsão: {data_fim.strftime('%d/%m/%Y')}")
                
                render_edit_controls(idx, row)

    # ==========================
    # ABA: FILA
    # ==========================
    with tab_fila:
        df_fila = df[df['Status'] == "Na Fila"]
        if df_fila.empty: st.info("Sua lista de desejos está vazia.")
        
        for idx, row in df_fila.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{row['Curso']}** ({row['Total_Aulas']} aulas)  \n<small>{row['Plataforma']}</small>", unsafe_allow_html=True)
                
                if c2.button("▶️ Iniciar", key=f"start_c_{idx}"):
                    df.at[idx, 'Aulas_Feitas'] = 1
                    save_data(df)
                    st.rerun()
                
                render_edit_controls(idx, row)

    # ==========================
    # ABA: CONCLUÍDOS (CERTIFICADOS)
    # ==========================
    with tab_concluidos:
        df_done = df[df['Status'] == "Concluído"]
        if df_done.empty: st.info("Nenhum curso concluído ainda.")
        
        for idx, row in df_done.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                
                with c1:
                    st.markdown(f"### 🎖️ {row['Curso']}")
                    st.write(f"**Plataforma:** {row['Plataforma']}")
                    
                    # Gestão do Link do Certificado
                    link = row['Link_Certificado']
                    if link and len(str(link)) > 5:
                        st.markdown(f"🔗 [**Abrir Certificado**]({link})", unsafe_allow_html=True)
                    else:
                        st.warning("Certificado não anexado.")
                        new_link = st.text_input("Colar Link do Certificado aqui:", key=f"lnk_in_{idx}")
                        if new_link:
                            df.at[idx, 'Link_Certificado'] = new_link
                            save_data(df)
                            st.rerun()
                            
                with c2:
                    st.write("") # Espaço
                    st.success("✅ Concluído")
                
                render_edit_controls(idx, row)