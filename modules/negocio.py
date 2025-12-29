import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta
import os

from modules import conexoes

def load_data():
    # 1. Clientes
    cols_c = ["ID", "Nome", "Empresa", "Cargo", "Email", "Telefone", "Origem", "LinkedIn_Url", "Data_Cadastro"]
    df_c = conexoes.load_gsheet("CRM_Clientes", cols_c)
    
    # 2. Deals
    cols_d = ["ID", "Cliente", "Projeto", "Valor_Est", "Estagio", "Probabilidade", "Data_Inicio", "Previsao_Fechamento", "Obs", "Faturado_Check"]
    df_d = conexoes.load_gsheet("CRM_Deals", cols_d)
    
    # Saneamento de Tipos
    if not df_d.empty:
        df_d["Valor_Est"] = pd.to_numeric(df_d["Valor_Est"], errors='coerce').fillna(0.0)
        df_d["Faturado_Check"] = df_d["Faturado_Check"].astype(str).str.upper() == "TRUE"
    if not df_c.empty:
        df_c["ID"] = pd.to_numeric(df_c["ID"], errors='coerce').fillna(0).astype(int)
        
    return df_c, df_d

def save_data(df, aba):
    # Converte tipos para garantir compatibilidade com GSheets
    df_save = df.copy()
    # Converte colunas de data/bool para string antes do upload
    for col in ["Data_Cadastro", "Data_Inicio", "Previsao_Fechamento"]:
        if col in df_save.columns: df_save[col] = df_save[col].astype(str)
    conexoes.save_gsheet(aba, df_save)

def lancar_no_financeiro(descricao, valor, data_ref):
    # Puxa transações existentes para anexar a nova receita
    cols_f = ["Data", "Tipo", "Categoria", "Descricao", "Valor_Total", "Pagamento"]
    df_fin = conexoes.load_gsheet("Transacoes", cols_f)
    
    nova_transacao = {
        "Data": str(data_ref),
        "Tipo": "Receita",
        "Categoria": "Negócios/Freelance",
        "Descricao": f"Projeto: {descricao}",
        "Valor_Total": float(valor),
        "Pagamento": "Pix/Transf"
    }
    
    df_updated = pd.concat([df_fin, pd.DataFrame([nova_transacao])], ignore_index=True)
    conexoes.save_gsheet("Transacoes", df_updated)
    return True

def render_page():
    st.header("💼 Business Center (CRM)")
    
    df_clientes, df_deals = load_data()
    
    # --- SIDEBAR ---
    with st.sidebar:
        st.subheader("➕ Novo Registro")
        tipo_add = st.radio("Tipo", ["Cliente / Lead", "Oportunidade (Deal)"])
        
        if tipo_add == "Cliente / Lead":
            with st.form("form_cliente"):
                c_nome = st.text_input("Nome")
                c_empresa = st.text_input("Empresa")
                c_cargo = st.text_input("Cargo")
                c_origem = st.selectbox("Origem", ["LinkedIn", "Indicação", "Upwork", "Site", "Outro"])
                if st.form_submit_button("Salvar"):
                    new_id = 1 if df_clientes.empty else df_clientes['ID'].max() + 1
                    novo = {
                        "ID": new_id, "Nome": c_nome, "Empresa": c_empresa, "Cargo": c_cargo,
                        "Origem": c_origem, "Data_Cadastro": date.today()
                    }
                    df_clientes = pd.concat([df_clientes, pd.DataFrame([novo])], ignore_index=True)
                    save_data(df_clientes, "CRM_Clientes")
                    st.success("Cliente salvo!")
                    st.rerun()

        else: # Deal
            if df_clientes.empty:
                st.warning("Cadastre clientes antes.")
            else:
                with st.form("form_deal"):
                    d_cli = st.selectbox("Cliente", df_clientes['Nome'].unique())
                    d_proj = st.text_input("Projeto")
                    d_val = st.number_input("Valor (R$)", 0.0, 1000000.0, 1500.0)
                    d_stg = st.selectbox("Estágio", ["1. Prospecção", "2. Proposta", "3. Negociação", "5. Fechado (Ganho)", "6. Perdido"])
                    if st.form_submit_button("Criar Deal"):
                        new_id = 1 if df_deals.empty else df_deals['ID'].max() + 1
                        novo = {
                            "ID": new_id, "Cliente": d_cli, "Projeto": d_proj, 
                            "Valor_Est": d_val, "Estagio": d_stg, 
                            "Data_Inicio": date.today(), "Previsao_Fechamento": date.today()+timedelta(days=15),
                            "Faturado_Check": False 
                        }
                        df_deals = pd.concat([df_deals, pd.DataFrame([novo])], ignore_index=True)
                        save_data(df_deals, "CRM_Deals")
                        st.success("Deal criado!")
                        st.rerun()

    # --- KPI HEADER ---
    if not df_deals.empty:
        ganhos = df_deals[df_deals['Estagio'] == "5. Fechado (Ganho)"]
        abertos = df_deals[~df_deals['Estagio'].isin(["5. Fechado (Ganho)", "6. Perdido"])]
        
        c1, c2, c3 = st.columns(3)
        c1.metric("💰 Pipeline Aberto", f"R$ {abertos['Valor_Est'].sum():,.2f}")
        c2.metric("🏆 Já Faturado", f"R$ {ganhos['Valor_Est'].sum():,.2f}")
        c3.metric("🎯 Projetos Fechados", len(ganhos))
        st.divider()

    # --- TABS ---
    t1, t2, t3 = st.tabs(["🌪️ Funil", "📝 Gerenciar Deals", "👥 Clientes"])
    
    with t1:
        if not df_deals.empty:
            funnel = df_deals.groupby("Estagio")['Valor_Est'].sum().reset_index()
            st.plotly_chart(px.funnel(funnel, x='Valor_Est', y='Estagio'), use_container_width=True)
        else:
            st.info("Adicione oportunidades para ver o funil.")

    with t2:
        st.subheader("Pipeline & Faturamento Automático")
        st.caption("Edite os campos diretamente na tabela abaixo. Para excluir, use o seletor no final.")
        
        if not df_deals.empty:
            # 1. EDIÇÃO (Data Editor)
            edited_deals = st.data_editor(
                df_deals,
                column_config={
                    "Estagio": st.column_config.SelectboxColumn("Estágio", options=["1. Prospecção", "2. Proposta", "3. Negociação", "5. Fechado (Ganho)", "6. Perdido"], required=True),
                    "Faturado_Check": st.column_config.CheckboxColumn("Já Faturou?", disabled=True),
                    "Valor_Est": st.column_config.NumberColumn("Valor (R$)", format="%.2f")
                },
                use_container_width=True, hide_index=True, key="crm_editor", num_rows="dynamic"
            )
            
            # Lógica de Detecção de Mudança e Faturamento
            if not df_deals.equals(edited_deals):
                for idx, row in edited_deals.iterrows():
                    # Se não existia no original (linha nova criada pelo editor), ignoramos a lógica complexa aqui e só salvamos
                    if idx not in df_deals.index:
                        continue

                    # Se mudou para Ganho E ainda não foi marcado como faturado
                    if row['Estagio'] == "5. Fechado (Ganho)" and row['Faturado_Check'] == False:
                        sucesso = lancar_no_financeiro(
                            descricao=f"{row['Cliente']} - {row['Projeto']}",
                            valor=row['Valor_Est'],
                            data_ref=date.today()
                        )
                        if sucesso:
                            edited_deals.at[idx, 'Faturado_Check'] = True
                            st.toast(f"💸 KA-CHING! R$ {row['Valor_Est']} lançado no Financeiro!", icon="🤑")
                
                save_data(edited_deals, "CRM_Deals")
                st.rerun()

            # 2. EXCLUSÃO (Área Dedicada)
            st.markdown("---")
            with st.expander("🗑️ Zona de Perigo (Excluir Deal)"):
                col_sel_del, col_btn_del = st.columns([3, 1])
                lista_deals_del = df_deals.apply(lambda x: f"ID {x['ID']} | {x['Cliente']} - {x['Projeto']}", axis=1)
                deal_to_delete = col_sel_del.selectbox("Selecione para excluir:", lista_deals_del, key="sel_del_deal")
                
                if col_btn_del.button("Excluir Deal"):
                    id_del = int(deal_to_delete.split("|")[0].replace("ID ", "").strip())
                    df_deals = df_deals[df_deals['ID'] != id_del]
                    save_data(df_deals, "CRM_Deals")
                    st.success("Deal removido.")
                    st.rerun()
        else:
            st.info("Nenhum deal cadastrado.")

    with t3:
        st.subheader("Base de Clientes")
        
        if not df_clientes.empty:
            # 1. EDIÇÃO DIRETA
            edited_clients = st.data_editor(
                df_clientes,
                num_rows="dynamic",
                key="editor_clientes",
                use_container_width=True,
                hide_index=True
            )
            
            if not df_clientes.equals(edited_clients):
                save_data(edited_deals, "CRM_Deals")
                st.toast("Dados do cliente atualizados!")
                st.rerun()
            
            # 2. EXCLUSÃO
            st.markdown("---")
            with st.expander("🗑️ Excluir Cliente"):
                c_del1, c_del2 = st.columns([3, 1])
                cliente_to_del = c_del1.selectbox("Cliente", df_clientes['Nome'].unique(), key="sel_del_cli")
                
                if c_del2.button("Apagar Cliente"):
                    # Verifica se tem deals vinculados
                    deals_vinculados = len(df_deals[df_deals['Cliente'] == cliente_to_del])
                    if deals_vinculados > 0:
                        st.error(f"Não é possível excluir: Existem {deals_vinculados} deals vinculados a este cliente.")
                    else:
                        df_clientes = df_clientes[df_clientes['Nome'] != cliente_to_del]
                        save_data(df_clientes, "CRM_Deals")
                        st.success("Cliente removido da base.")
                        st.rerun()
        else:
            st.info("Nenhum cliente cadastrado.")
            