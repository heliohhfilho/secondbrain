import streamlit as st
import pandas as pd
from datetime import date, datetime
from modules import conexoes

# --- FUNÇÕES DE DADOS ---
def load_data():
    # 1. O Dump (Buffer)
    cols_d = ["ID", "Data", "Conteudo", "Tags", "Processado", "Destino"]
    df_d = conexoes.load_gsheet("Dump_Mental", cols_d)
    if not df_d.empty:
        df_d["ID"] = pd.to_numeric(df_d["ID"], errors='coerce').fillna(0).astype(int)
        df_d["Processado"] = df_d["Processado"].astype(str).str.upper() == "TRUE"
        # Tratamento de Data
        df_d["Data"] = pd.to_datetime(df_d["Data"], format='mixed', dayfirst=False, errors='coerce')

    # 2. Carrega Destinos (Para onde vamos mandar as ideias?)
    # Projetos Criativos
    df_p = conexoes.load_gsheet("Criatividade_Projetos", ["ID", "Titulo", "Tipo", "Genero", "Ano", "Status", "Capa_URL", "ContraCapa_URL", "Resumo_Geral"])
    # Metas Financeiras
    df_m = conexoes.load_gsheet("Metas", ["ID", "Titulo", "Meta_Valor", "Progresso_Manual"])

    return df_d, df_p, df_m

def save_data(df, aba):
    df_s = df.copy()
    if "Data" in df_s.columns: 
        df_s["Data"] = pd.to_datetime(df_s["Data"], errors='coerce').dt.strftime('%Y-%m-%d').fillna(str(date.today()))
    conexoes.save_gsheet(aba, df_s)

# --- ENGINE DO CÉREBRO ---
def render_page():
    st.header("🧠 Brain Dump (Caixa de Entrada)")
    st.caption("Esvazie sua mente. Capture agora, organize depois.")
    
    df_dump, df_proj, df_metas = load_data()
    
    tab_capture, tab_process, tab_history = st.tabs(["⚡ Captura Rápida", "⚙️ Processar Inbox", "📜 Arquivo"])

    # ------------------------------------------------------------------
    # ABA 1: CAPTURA (Foco em Velocidade)
    # ------------------------------------------------------------------
    with tab_capture:
        with st.form("quick_dump", clear_on_submit=True):
            st.markdown("##### O que está na sua cabeça?")
            conteudo = st.text_area("", height=150, placeholder="Ex: Tive uma ideia para um livro sobre engenharia... / Preciso comprar um suporte pro monitor...")
            tags = st.text_input("Tags rápidas (Opcional)", placeholder="#ideia #compras")
            
            c1, c2 = st.columns([1, 5])
            if c1.form_submit_button("📥 Salvar", type="primary"):
                if conteudo:
                    new_id = 1 if df_dump.empty else df_dump['ID'].max() + 1
                    novo = {
                        "ID": new_id,
                        "Data": date.today(),
                        "Conteudo": conteudo,
                        "Tags": tags,
                        "Processado": False,
                        "Destino": ""
                    }
                    df_dump = pd.concat([df_dump, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_dump, "Dump_Mental")
                    st.toast("Pensamento capturado!")
                    st.rerun()
                else:
                    st.warning("Escreva algo primeiro.")

    # ------------------------------------------------------------------
    # ABA 2: PROCESSAMENTO (A Mágica da Engenharia)
    # ------------------------------------------------------------------
    with tab_process:
        # Filtra apenas o que NÃO foi processado
        inbox = df_dump[df_dump['Processado'] == False].sort_values('Data', ascending=False)
        
        if inbox.empty:
            st.success("✨ Sua mente está limpa! Nada na caixa de entrada.")
            st.image("https://media1.giphy.com/media/v1.Y2lkPTc5MGI3NjExM2Q1.../giphy.gif", width=200) # Placeholder mental zen
        else:
            st.write(f"Você tem **{len(inbox)}** itens para processar.")
            
            for idx, row in inbox.iterrows():
                with st.container(border=True):
                    c_txt, c_act = st.columns([3, 2])
                    
                    with c_txt:
                        st.markdown(f"**{row['Conteudo']}**")
                        st.caption(f"📅 {row['Data'].strftime('%d/%m/%Y')} | 🏷️ {row['Tags']}")
                    
                    with c_act:
                        st.markdown("O que fazer com isso?")
                        b1, b2, b3, b4 = st.columns(4)
                        
                        # AÇÃO 1: VIRAR PROJETO CRIATIVO
                        with b1.popover("🎨", help="Transformar em Projeto Criativo"):
                            st.markdown("Criar Projeto")
                            p_tipo = st.selectbox("Tipo", ["Livro", "Álbum Musical", "Série Escrita"], key=f"pt_{row['ID']}")
                            if st.button("Confirmar", key=f"pc_{row['ID']}"):
                                # Cria no DB de Projetos
                                new_pid = 1 if df_proj.empty else df_proj['ID'].max() + 1
                                novo_proj = {
                                    "ID": new_pid, "Titulo": row['Conteudo'][:50], # Pega o inicio como titulo
                                    "Tipo": p_tipo, "Genero": "A definir", "Ano": 2025, "Status": "Ideia",
                                    "Resumo_Geral": row['Conteudo'], "Capa_URL": "", "ContraCapa_URL": ""
                                }
                                df_proj = pd.concat([df_proj, pd.DataFrame([novo_proj])], ignore_index=True)
                                save_data(df_proj, "Criatividade_Projetos")
                                
                                # Marca Dump como processado
                                df_dump.loc[df_dump['ID'] == row['ID'], 'Processado'] = True
                                df_dump.loc[df_dump['ID'] == row['ID'], 'Destino'] = "Projeto Criativo"
                                save_data(df_dump, "Dump_Mental")
                                st.success("Promovido a Projeto!")
                                st.rerun()

                        # AÇÃO 2: VIRAR META FINANCEIRA
                        with b2.popover("💰", help="Transformar em Meta Financeira"):
                            st.markdown("Criar Meta")
                            val_meta = st.number_input("Valor Alvo (R$)", 0.0, key=f"vm_{row['ID']}")
                            if st.button("Criar Meta", key=f"mc_{row['ID']}"):
                                new_mid = 1 if df_metas.empty else df_metas['ID'].max() + 1
                                nova_meta = {"ID": new_mid, "Titulo": row['Conteudo'][:30], "Meta_Valor": val_meta, "Progresso_Manual": 0}
                                df_metas = pd.concat([df_metas, pd.DataFrame([nova_meta])], ignore_index=True)
                                save_data(df_metas, "Metas")
                                
                                df_dump.loc[df_dump['ID'] == row['ID'], 'Processado'] = True
                                df_dump.loc[df_dump['ID'] == row['ID'], 'Destino'] = "Meta Financeira"
                                save_data(df_dump, "Dump_Mental")
                                st.success("Virou Meta!")
                                st.rerun()

                        # AÇÃO 3: SÓ ARQUIVAR (Era só um pensamento)
                        if b3.button("✅", key=f"ok_{row['ID']}", help="Marcar como lido/concluído"):
                            df_dump.loc[df_dump['ID'] == row['ID'], 'Processado'] = True
                            df_dump.loc[df_dump['ID'] == row['ID'], 'Destino'] = "Arquivo"
                            save_data(df_dump, "Dump_Mental")
                            st.rerun()

                        # AÇÃO 4: LIXO
                        if b4.button("🗑️", key=f"del_{row['ID']}", help="Excluir permanentemente"):
                            df_dump = df_dump[df_dump['ID'] != row['ID']]
                            save_data(df_dump, "Dump_Mental")
                            st.rerun()

    # ------------------------------------------------------------------
    # ABA 3: HISTÓRICO
    # ------------------------------------------------------------------
    with tab_history:
        st.subheader("Arquivo Morto")
        processados = df_dump[df_dump['Processado'] == True].sort_values('Data', ascending=False)
        
        if not processados.empty:
            st.dataframe(
                processados[['Data', 'Conteudo', 'Destino', 'Tags']],
                width=True,
                hide_index=True,
                column_config={
                    "Data": st.column_config.DateColumn("Data", format="DD/MM/YYYY")
                }
            )
        else:
            st.info("Nada no arquivo.")