import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import os

from modules import conexoes

def load_data():
    # 1. Carrega Metas Principais
    cols_metas = ["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Deadline", "Progresso_Manual"]
    df = conexoes.load_gsheet("Metas", cols_metas)
    
    if not df.empty:
        df["ID"] = pd.to_numeric(df["ID"], errors='coerce').fillna(0).astype(int)
        df["Meta_Valor"] = pd.to_numeric(df["Meta_Valor"], errors='coerce').fillna(0.0)
        df["Progresso_Manual"] = pd.to_numeric(df["Progresso_Manual"], errors='coerce').fillna(0.0)

    # 2. Busca Dados Externos na Nuvem para OKRs Automáticos
    dados_externos = {}
    
    # OKR: Financeiro
    df_inv = conexoes.load_gsheet("Investimentos", ["Qtd", "Preco_Unitario"])
    if not df_inv.empty:
        df_inv["Qtd"] = pd.to_numeric(df_inv["Qtd"], errors='coerce').fillna(0)
        df_inv["Preco_Unitario"] = pd.to_numeric(df_inv["Preco_Unitario"], errors='coerce').fillna(0)
        dados_externos['Investimento Total'] = (df_inv['Qtd'] * df_inv['Preco_Unitario']).sum()
    
    # OKR: Leituras
    df_l = conexoes.load_gsheet("Leituras", ["Status"])
    dados_externos['Livros Lidos'] = len(df_l[df_l['Status'] == 'Concluído']) if not df_l.empty else 0

    # OKR: Bio (Saúde)
    df_b = conexoes.load_gsheet("Bio", ["Data", "Peso_kg", "Gordura_Perc"])
    if not df_b.empty:
        df_b['Data'] = pd.to_datetime(df_b['Data'], errors='coerce')
        last_bio = df_b.sort_values("Data").iloc[-1]
        dados_externos['Peso Atual'] = pd.to_numeric(last_bio['Peso_kg'], errors='coerce')
        dados_externos['BF Atual'] = pd.to_numeric(last_bio['Gordura_Perc'], errors='coerce')

    # OKR: DayTrade
    df_dt = conexoes.load_gsheet("DayTrade", ["Lucro"])
    if not df_dt.empty:
        dados_externos['Lucro Trade'] = pd.to_numeric(df_dt['Lucro'], errors='coerce').sum()

    # OKR: CRM (Negócios)
    df_crm = conexoes.load_gsheet("CRM", ["Estagio", "Valor_Est"])
    if not df_crm.empty:
        ganhos = df_crm[df_crm['Estagio'] == "5. Fechado (Ganho)"]
        dados_externos['Faturamento'] = pd.to_numeric(ganhos['Valor_Est'], errors='coerce').sum()

    return df, dados_externos

def save_data(df):
    # Converte datas para string para o GSheets
    df_save = df.copy()
    if "Deadline" in df_save.columns:
        df_save["Deadline"] = df_save["Deadline"].astype(str)
    conexoes.save_gsheet("Metas", df_save)

def calcular_status(tipo, meta, manual, externos):
    atual = 0.0
    
    # Roteamento de Dados
    if tipo == "Manual": atual = manual
    elif tipo == "💰 Investimento Total": atual = externos.get('Investimento Total', 0)
    elif tipo == "📚 Livros Lidos": atual = externos.get('Livros Lidos', 0)
    elif tipo == "⚖️ Peso (Emagrecer)": atual = externos.get('Peso Atual', 0)
    elif tipo == "🧬 Gordura % (Baixar)": atual = externos.get('BF Atual', 0)
    elif tipo == "📈 Lucro DayTrade ($)": atual = externos.get('Lucro Trade', 0)
    elif tipo == "💼 Faturamento CRM": atual = externos.get('Faturamento', 0)
    
    # Lógica de Progresso
    if tipo in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]:
        # Para metas de REDUÇÃO (Peso/Gordura), o cálculo é invertido.
        # Assumimos um "Start" hipotético ou visualizamos apenas o valor absoluto.
        # Simplificação: Progresso visual não se aplica bem a barra 0-100 padrão de subida.
        # Vamos retornar o valor cru e tratar no visual.
        perc = 0 # Trata no render
    else:
        perc = (atual / meta * 100) if meta > 0 else 0
        perc = min(100.0, max(0.0, perc))
        
    return atual, perc

def render_page():
    st.header("🎯 Painel de Metas & OKRs 2026")
    st.caption("Transforme sonhos em dados mensuráveis.")
    
    df, dados_externos = load_data()
    
    # --- SIDEBAR: NOVA META ---
    with st.sidebar:
        st.subheader("➕ Nova Meta")
        tipos_disponiveis = [
            "Manual", 
            "💰 Investimento Total", 
            "📚 Livros Lidos", 
            "⚖️ Peso (Emagrecer)", 
            "🧬 Gordura % (Baixar)",
            "📈 Lucro DayTrade ($)",
            "💼 Faturamento CRM"
        ]
        
        with st.form("nova_meta"):
            m_titulo = st.text_input("Título (Ex: Juntar 100k)")
            m_tipo = st.selectbox("Vincular a:", tipos_disponiveis)
            m_valor = st.number_input("Meta Alvo (Valor Final)", 0.0, 1000000.0, 10.0)
            m_unidade = st.text_input("Unidade (Ex: R$, kg, Livros)", "R$")
            m_prazo = st.date_input("Prazo Final", date.today() + timedelta(days=365))
            
            if st.form_submit_button("Criar Meta"):
                new_id = 1 if df.empty else df['ID'].max() + 1
                novo = {
                    "ID": new_id, "Titulo": m_titulo, "Tipo_Vinculo": m_tipo,
                    "Meta_Valor": m_valor, "Unidade": m_unidade, "Deadline": m_prazo,
                    "Progresso_Manual": 0.0
                }
                df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
                save_data(df)
                st.success("Meta traçada!")
                st.rerun()

    # --- DASHBOARD DE METAS ---
    if df.empty:
        st.info("Cadastre sua primeira meta na barra lateral.")
        return

    # Separa em colunas para visual grade
    col1, col2 = st.columns(2)
    
    for idx, row in df.iterrows():
        # Define em qual coluna o card vai aparecer (intercalado)
        col_atual = col1 if idx % 2 == 0 else col2
        
        with col_atual:
            with st.container(border=True):
                # Cabeçalho
                c_tit, c_del = st.columns([5, 1])
                c_tit.subheader(f"{row['Titulo']}")
                if c_del.button("🗑️", key=f"del_m_{row['ID']}"):
                    df = df[df['ID'] != row['ID']]
                    save_data(df)
                    st.rerun()

                # Cálculos
                atual, perc = calcular_status(row['Tipo_Vinculo'], row['Meta_Valor'], row['Progresso_Manual'], dados_externos)
                
                # Exibição Especial para Perda de Peso/Gordura
                is_reduction = row['Tipo_Vinculo'] in ["⚖️ Peso (Emagrecer)", "🧬 Gordura % (Baixar)"]
                
                if is_reduction:
                    # Se quero chegar em 80kg e estou com 90kg.
                    delta = atual - row['Meta_Valor']
                    if delta <= 0:
                        st.success(f"✅ META BATIDA! ({atual} {row['Unidade']})")
                        st.progress(1.0)
                    else:
                        st.metric("Falta Perder", f"{delta:.1f} {row['Unidade']}", f"Atual: {atual} {row['Unidade']}")
                        # Barra de progresso invertida visualmente é complexa, deixamos sem ou cheia
                        st.caption(f"Alvo: {row['Meta_Valor']} {row['Unidade']}")
                
                else:
                    # Padrão (Crescimento)
                    st.metric("Progresso", f"{atual:,.1f} / {row['Meta_Valor']:,.0f} {row['Unidade']}", f"{perc:.1f}%")
                    st.progress(perc / 100)
                
                # Dados Extras
                days_left = (pd.to_datetime(row['Deadline']).date() - date.today()).days
                st.caption(f"📅 Prazo: {pd.to_datetime(row['Deadline']).strftime('%d/%m/%Y')} ({days_left} dias restantes)")
                
                # Se for Manual, permite update
                if row['Tipo_Vinculo'] == "Manual":
                    new_val = st.number_input("Atualizar Progresso", value=float(row['Progresso_Manual']), key=f"upd_{row['ID']}")
                    if new_val != row['Progresso_Manual']:
                        df.at[idx, 'Progresso_Manual'] = new_val
                        save_data(df)
                        st.rerun()
                else:
                    st.caption(f"🔗 Vinculado a: {row['Tipo_Vinculo']}")