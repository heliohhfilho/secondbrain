import streamlit as st
import pandas as pd
from datetime import date
from modules import conexoes

# --- FUNÇÕES DE DADOS ---
def load_data():
    # 1. Projetos (Master)
    cols_proj = ["ID", "Titulo", "Tipo", "Genero", "Ano", "Status", "Capa_URL", "ContraCapa_URL", "Resumo_Geral"]
    df_p = conexoes.load_gsheet("Criatividade_Projetos", cols_proj)
    if not df_p.empty:
        df_p["ID"] = pd.to_numeric(df_p["ID"], errors='coerce').fillna(0).astype(int)
        df_p["Ano"] = pd.to_numeric(df_p["Ano"], errors='coerce').fillna(2025).astype(int)

    # 2. Músicas (Detalhe Album)
    cols_mus = ["ID_Projeto", "Faixa", "Titulo", "Letra", "Instr_Rec", "Vocal_Rec", "Mix_Master", "Obs"]
    df_m = conexoes.load_gsheet("Criatividade_Musica", cols_mus)
    if not df_m.empty:
        df_m["ID_Projeto"] = pd.to_numeric(df_m["ID_Projeto"], errors='coerce').fillna(0).astype(int)
        df_m["Faixa"] = pd.to_numeric(df_m["Faixa"], errors='coerce').fillna(0).astype(int)
        for c in ["Instr_Rec", "Vocal_Rec", "Mix_Master"]:
            df_m[c] = df_m[c].astype(str).str.upper() == "TRUE"

    # 3. Escrita (Detalhe Série/Livro)
    cols_esc = ["ID_Projeto", "Temporada", "Episodio", "Titulo", "Resumo_Ep", "Link_PDF", "Status_Escrita"]
    df_e = conexoes.load_gsheet("Criatividade_Escrita", cols_esc)
    if not df_e.empty:
        df_e["ID_Projeto"] = pd.to_numeric(df_e["ID_Projeto"], errors='coerce').fillna(0).astype(int)
        df_e["Temporada"] = pd.to_numeric(df_e["Temporada"], errors='coerce').fillna(1).astype(int)
        df_e["Episodio"] = pd.to_numeric(df_e["Episodio"], errors='coerce').fillna(1).astype(int)
    
    return df_p, df_m, df_e

def save_data(df, aba):
    df_s = df.copy()
    conexoes.save_gsheet(aba, df_s)

# --- WORKSPACE: ÁLBUM MUSICAL ---
def render_album_workspace(projeto, df_m):
    st.markdown(f"## 🎚️ Estúdio: {projeto['Titulo']}")
    
    c_vis, c_info = st.columns([1, 3])
    with c_vis:
        tab_frente, tab_verso = st.tabs(["Frente", "Verso"])
        with tab_frente:
            if projeto['Capa_URL']: st.image(projeto['Capa_URL'], use_column_width=True)
            else: st.info("Sem Capa")
        with tab_verso:
            if projeto['ContraCapa_URL']: st.image(projeto['ContraCapa_URL'], use_column_width=True)
            else: st.info("Sem Contra-Capa")
            
    with c_info:
        st.caption(f"{projeto['Genero']} | {projeto['Ano']}")
        st.write(projeto['Resumo_Geral'])
        
        musicas_do_album = df_m[df_m['ID_Projeto'] == projeto['ID']]
        if not musicas_do_album.empty:
            total_steps = len(musicas_do_album) * 3 
            done_steps = musicas_do_album['Instr_Rec'].sum() + musicas_do_album['Vocal_Rec'].sum() + musicas_do_album['Mix_Master'].sum()
            progresso = done_steps / total_steps if total_steps > 0 else 0
            st.progress(progresso, text=f"Progresso da Produção: {int(progresso*100)}%")
    
    st.divider()
    
    st.subheader("🎹 Tracklist & Produção")
    mask = df_m['ID_Projeto'] == projeto['ID']
    df_editor = df_m.loc[mask].sort_values("Faixa")
    
    edited_df = st.data_editor(
        df_editor,
        column_config={
            "ID_Projeto": None, 
            "Faixa": st.column_config.NumberColumn("#", width="small"),
            "Titulo": st.column_config.TextColumn("Nome da Faixa", width="medium"),
            "Instr_Rec": st.column_config.CheckboxColumn("🎹 Instr."),
            "Vocal_Rec": st.column_config.CheckboxColumn("🎤 Vocal"),
            "Mix_Master": st.column_config.CheckboxColumn("🎛️ Master"),
            "Letra": st.column_config.TextColumn("Letra (Pop-up)", disabled=True),
            "Obs": st.column_config.TextColumn("Notas de Eng.")
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=f"editor_album_{projeto['ID']}"
    )
    
    c_save, c_lyrics = st.columns([1, 1])
    
    if c_save.button("💾 Salvar Alterações de Produção", key=f"sv_alb_{projeto['ID']}"):
        df_m = df_m[df_m['ID_Projeto'] != projeto['ID']]
        edited_df['ID_Projeto'] = projeto['ID']
        df_m = pd.concat([df_m, edited_df], ignore_index=True)
        save_data(df_m, "Criatividade_Musica")
        st.success("Tracklist atualizada!")
        st.rerun()

    with c_lyrics.popover("📝 Editar Letras"):
        st.markdown("Selecione a faixa para editar a letra:")
        faixa_sel = st.selectbox("Faixa", edited_df['Titulo'].unique())
        if faixa_sel:
            # Encontra índice real no dataframe editado
            matches = edited_df[edited_df['Titulo'] == faixa_sel]
            if not matches.empty:
                letra_atual = matches.iloc[0]['Letra']
                nova_letra = st.text_area("Composição", value=letra_atual if pd.notna(letra_atual) else "", height=300)
                
                if st.button("Salvar Letra"):
                    # Busca no dataframe original para salvar persistente
                    mask_real = (df_m['ID_Projeto'] == projeto['ID']) & (df_m['Titulo'] == faixa_sel)
                    if not df_m.loc[mask_real].empty:
                        df_m.loc[mask_real, 'Letra'] = nova_letra
                        save_data(df_m, "Criatividade_Musica")
                        st.success("Letra salva!")
                    else:
                        st.warning("Faixa ainda não salva no banco. Salve a produção primeiro.")

# --- WORKSPACE: SÉRIE/LIVRO ---
def render_writer_workspace(projeto, df_e):
    st.markdown(f"## ✍️ Sala de Roteiro: {projeto['Titulo']}")
    
    c_capa, c_plan = st.columns([1, 3])
    with c_capa:
        if projeto['Capa_URL']: st.image(projeto['Capa_URL'])
        else: st.write("📓")
        
    with c_plan:
        st.caption(f"Tipo: {projeto['Tipo']} | Gênero: {projeto['Genero']}")
        with st.expander("🧠 Planejamento da História", expanded=False):
            st.text_area("Resumo Geral", value=projeto['Resumo_Geral'], height=150, disabled=True)

    st.divider()
    st.subheader("📑 Capítulos & Episódios")
    
    mask = df_e['ID_Projeto'] == projeto['ID']
    df_episodes = df_e.loc[mask].sort_values(["Temporada", "Episodio"])
    
    temps = sorted(df_episodes['Temporada'].unique()) if not df_episodes.empty else [1]
    if not df_episodes.empty:
        temp_sel = st.selectbox("Temporada / Livro", temps)
        df_view = df_episodes[df_episodes['Temporada'] == temp_sel]
    else:
        temp_sel = 1
        df_view = pd.DataFrame(columns=df_episodes.columns)

    edited_eps = st.data_editor(
        df_view,
        column_config={
            "ID_Projeto": None,
            "Temporada": None,
            "Episodio": st.column_config.NumberColumn("Ep.", width="small"),
            "Titulo": st.column_config.TextColumn("Título", width="medium"),
            "Resumo_Ep": st.column_config.TextColumn("Sinopse Curta"),
            "Link_PDF": st.column_config.LinkColumn("📄 Link PDF/Doc"),
            "Status_Escrita": st.column_config.SelectboxColumn("Status", options=["Ideia", "Roteiro", "Revisão", "Finalizado"])
        },
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic",
        key=f"ed_writ_{projeto['ID']}_{temp_sel}"
    )
    
    if st.button("💾 Salvar Episódios", key=f"sv_writ_{projeto['ID']}"):
        mask_remove = (df_e['ID_Projeto'] == projeto['ID']) & (df_e['Temporada'] == temp_sel)
        df_e = df_e[~mask_remove]
        edited_eps['ID_Projeto'] = projeto['ID']
        edited_eps['Temporada'] = temp_sel
        df_e = pd.concat([df_e, edited_eps], ignore_index=True)
        save_data(df_e, "Criatividade_Escrita")
        st.success("Roteiro atualizado!")
        st.rerun()

# --- MAIN PAGE ---
def render_page():
    st.header("🎨 Creative Studio")
    df_p, df_m, df_e = load_data()
    
    tab_galeria, tab_novo = st.tabs(["🖼️ Galeria de Projetos", "➕ Novo Projeto"])
    
    with tab_galeria:
        if df_p.empty:
            st.info("Nenhum projeto criativo iniciado.")
        else:
            tipos = st.multiselect("Filtrar Tipo", df_p['Tipo'].unique())
            df_show = df_p[df_p['Tipo'].isin(tipos)] if tipos else df_p
            
            cols = st.columns(3)
            for idx, (i, row) in enumerate(df_show.iterrows()):
                with cols[idx % 3]:
                    with st.container(border=True):
                        if row['Capa_URL']: st.image(row['Capa_URL'], use_column_width=True)
                        st.markdown(f"### {row['Titulo']}")
                        st.caption(f"{row['Tipo']} • {row['Genero']}")
                        
                        # --- BOTOES DE AÇÃO (ABRIR E DELETAR) ---
                        c_open, c_del = st.columns([4, 1])
                        
                        if c_open.button("Abrir Projeto", key=f"open_{row['ID']}"):
                            st.session_state['proj_ativo'] = row.to_dict()
                            st.rerun()
                        
                        # --- BOTÃO DE DELETAR (Cascading Delete) ---
                        if c_del.button("🗑️", key=f"del_proj_{row['ID']}", help="Excluir Projeto e Todo Conteúdo"):
                            id_del = row['ID']
                            # 1. Deleta Filhos (Músicas e Episódios)
                            df_m = df_m[df_m['ID_Projeto'] != id_del]
                            df_e = df_e[df_e['ID_Projeto'] != id_del]
                            # 2. Deleta Pai (Projeto)
                            df_p = df_p[df_p['ID'] != id_del]
                            
                            # Salva tudo
                            save_data(df_m, "Criatividade_Musica")
                            save_data(df_e, "Criatividade_Escrita")
                            save_data(df_p, "Criatividade_Projetos")
                            
                            st.toast("Projeto e arquivos deletados.")
                            st.rerun()
            
            if 'proj_ativo' in st.session_state:
                st.markdown("---")
                proj = st.session_state['proj_ativo']
                if st.button("❌ Fechar Workspace", type="secondary"):
                    del st.session_state['proj_ativo']
                    st.rerun()
                    
                if proj['Tipo'] in ['Álbum Musical', 'EP', 'Single']:
                    render_album_workspace(proj, df_m)
                else:
                    render_writer_workspace(proj, df_e)

    with tab_novo:
        st.subheader("Tirar a ideia do papel")
        with st.form("new_creative"):
            c1, c2 = st.columns(2)
            titulo = c1.text_input("Título do Projeto")
            tipo = c2.selectbox("Tipo", ["Álbum Musical", "Série Escrita", "Livro", "Coletânea Poesia", "EP"])
            
            c3, c4 = st.columns(2)
            genero = c3.text_input("Gênero", "Experimental")
            ano = c4.number_input("Ano Lançamento", 2024, 2030, 2025)
            
            st.markdown("---")
            capa = st.text_input("URL da Capa")
            contra = st.text_input("URL da Contra-Capa (Opcional)")
            resumo = st.text_area("Resumo / Conceito / Sinopse")
            
            if st.form_submit_button("Criar Projeto"):
                new_id = 1 if df_p.empty else df_p['ID'].max() + 1
                novo = {
                    "ID": new_id, "Titulo": titulo, "Tipo": tipo, "Genero": genero, "Ano": ano,
                    "Status": "Ideia", "Capa_URL": capa, "ContraCapa_URL": contra, "Resumo_Geral": resumo
                }
                df_p = pd.concat([df_p, pd.DataFrame([novo])], ignore_index=True)
                save_data(df_p, "Criatividade_Projetos")
                st.success(f"Projeto '{titulo}' criado!")
                st.rerun()