import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os
from modules import conexoes # <--- Conexão Nuvem

def load_data():
    cols = ["Curso", "Plataforma", "Total_Aulas", "Aulas_Feitas", "Link_Certificado", "Status"]
    df = conexoes.load_gsheet("Cursos", cols)
    
    if not df.empty:
        # Saneamento de tipos para garantir cálculos de progresso
        df["Total_Aulas"] = pd.to_numeric(df["Total_Aulas"], errors='coerce').fillna(1).astype(int)
        df["Aulas_Feitas"] = pd.to_numeric(df["Aulas_Feitas"], errors='coerce').fillna(0).astype(int)
        df["Link_Certificado"] = df["Link_Certificado"].fillna("")
        
    return df

def save_data(df):
    conexoes.save_gsheet("Cursos", df)

def determine_status(feitas, total):
    if feitas > total: feitas = total
    if feitas == 0: return "Na Fila"
    elif feitas >= total: return "Concluído"
    else: return "Em Andamento"

def render_page():
    st.header("🎓 Meus Cursos e Certificações")
    
    df = load_data()

    # --- SIDEBAR: CADASTRO ---
    with st.sidebar:
        st.subheader("➕ Novo Curso")
        nome = st.text_input("Nome do Curso")
        plataforma = st.text_input("Plataforma")
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
                st.success("Curso cadastrado na nuvem!")
                st.rerun()

        st.divider()
        ritmo = st.slider("Aulas por semana?", 1, 50, 5)

    # --- KPIs GERAIS ---
    if not df.empty:
        # Atualização dinâmica de status
        df['Status'] = df.apply(lambda x: determine_status(x['Aulas_Feitas'], x['Total_Aulas']), axis=1)
        
        k1, k2, k3 = st.columns(3)
        k1.metric("Em Andamento", len(df[df['Status'] == "Em Andamento"]))
        k2.metric("Concluídos", len(df[df['Status'] == "Concluído"]))
        
        ativos = df[df['Status'] == "Em Andamento"]
        if not ativos.empty:
            prog_geral = ativos['Aulas_Feitas'].sum() / ativos['Total_Aulas'].sum()
            k3.metric("Progresso Global", f"{prog_geral:.1%}")
        else:
            k3.metric("Progresso Global", "0%")
            
        st.divider()

    # --- FUNÇÃO DE EDIÇÃO (CRUD) ---
    def render_edit_controls(idx, row):
        with st.expander("⚙️ Opções", expanded=False):
            with st.form(key=f"form_curso_{idx}"):
                c1, c2 = st.columns(2)
                n_nome = c1.text_input("Curso", row['Curso'])
                n_plat = c2.text_input("Plataforma", row['Plataforma'])
                n_link = st.text_input("Link Certificado", row['Link_Certificado'])
                
                if st.form_submit_button("Salvar"):
                    df.at[idx, 'Curso'] = n_nome
                    df.at[idx, 'Plataforma'] = n_plat
                    df.at[idx, 'Link_Certificado'] = n_link
                    save_data(df)
                    st.rerun()

            if st.button("🗑️ Excluir", key=f"del_c_{idx}"):
                save_data(df.drop(idx))
                st.rerun()

    # --- ABAS ---
    tab_andamento, tab_fila, tab_concluidos = st.tabs(["💻 Em Andamento", "⏳ Fila", "🏆 Certificados"])

    with tab_andamento:
        df_active = df[df['Status'] == "Em Andamento"]
        if df_active.empty: st.info("Nenhum curso ativo.")
        
        for idx, row in df_active.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 2])
                with c1:
                    st.subheader(row['Curso'])
                    prog = row['Aulas_Feitas'] / row['Total_Aulas']
                    st.progress(min(prog, 1.0))
                    st.write(f"**{int(prog*100)}%** ({row['Aulas_Feitas']}/{row['Total_Aulas']})")

                with c2:
                    novas_aulas = st.number_input("Concluídas", 0, int(row['Total_Aulas']), int(row['Aulas_Feitas']), key=f"aula_{idx}")
                    if novas_aulas != row['Aulas_Feitas']:
                        df.at[idx, 'Aulas_Feitas'] = novas_aulas
                        save_data(df)
                        st.rerun()

                # Previsão Matemática (Engenharia de Cronograma)
                restam = row['Total_Aulas'] - row['Aulas_Feitas']
                dias = (restam / ritmo) * 7
                data_fim = datetime.now() + timedelta(days=dias)
                st.caption(f"📅 Previsão de Conclusão: {data_fim.strftime('%d/%m/%Y')} (Ritmo: {ritmo}/sem)")
                render_edit_controls(idx, row)

    with tab_fila:
        df_fila = df[df['Status'] == "Na Fila"]
        for idx, row in df_fila.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{row['Curso']}** ({row['Total_Aulas']} aulas)")
                if c2.button("▶️ Iniciar", key=f"start_{idx}"):
                    df.at[idx, 'Aulas_Feitas'] = 1
                    save_data(df)
                    st.rerun()
                render_edit_controls(idx, row)

    with tab_concluidos:
        df_done = df[df['Status'] == "Concluído"]
        for idx, row in df_done.iterrows():
            with st.container(border=True):
                st.markdown(f"### 🎖️ {row['Curso']}")
                if row['Link_Certificado']:
                    st.link_button("🔗 Ver Certificado", row['Link_Certificado'])
                render_edit_controls(idx, row)