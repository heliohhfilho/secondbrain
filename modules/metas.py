import streamlit as st
import pandas as pd
from datetime import date, datetime, timedelta
import os

# --- ARQUIVOS DE DADOS (Conectores) ---
PATH_METAS = os.path.join('data', 'metas_okr.csv')
# Fontes de Dados
PATH_FIN_INVEST = os.path.join('data', 'fin_investimentos.csv')
PATH_LEITURAS = os.path.join('data', 'leituras.csv')
PATH_BIO = os.path.join('data', 'bio_data.csv')
PATH_DAYTRADE = os.path.join('data', 'daytrade.csv')
PATH_CRM = os.path.join('data', 'crm_deals.csv')
PATH_PROD = os.path.join('data', 'log_produtividade.csv')

def load_data():
    # Carrega Metas
    if not os.path.exists(PATH_METAS):
        df = pd.DataFrame(columns=["ID", "Titulo", "Tipo_Vinculo", "Meta_Valor", "Unidade", "Deadline", "Progresso_Manual"])
    else:
        df = pd.read_csv(PATH_METAS)

    # Carrega Dados Externos (Para cálculo automático)
    dados_externos = {}
    
    # 1. Financeiro (Total Investido)
    if os.path.exists(PATH_FIN_INVEST):
        df_inv = pd.read_csv(PATH_FIN_INVEST)
        if "Preco_Medio" in df_inv.columns: df_inv.rename(columns={"Preco_Medio": "Preco_Unitario"}, inplace=True)
        if "Preco_Unitario" not in df_inv.columns: df_inv["Preco_Unitario"] = 0.0
        total_inv = (df_inv['Qtd'] * df_inv['Preco_Unitario']).sum()
        dados_externos['Investimento Total'] = total_inv
    else:
        dados_externos['Investimento Total'] = 0.0

    # 2. Leitura (Livros Lidos)
    if os.path.exists(PATH_LEITURAS):
        df_l = pd.read_csv(PATH_LEITURAS)
        lidos = len(df_l[df_l['Status'] == 'Concluído'])
        dados_externos['Livros Lidos'] = lidos
    else:
        dados_externos['Livros Lidos'] = 0

    # 3. Bio (Peso e Gordura)
    if os.path.exists(PATH_BIO):
        df_b = pd.read_csv(PATH_BIO)
        if not df_b.empty:
            df_b = df_b.sort_values("Data")
            dados_externos['Peso Atual'] = df_b.iloc[-1]['Peso_kg']
            dados_externos['BF Atual'] = df_b.iloc[-1]['Gordura_Perc']
        else:
            dados_externos['Peso Atual'] = 0
            dados_externos['BF Atual'] = 0
    
    # 4. DayTrade (Lucro Acumulado)
    if os.path.exists(PATH_DAYTRADE):
        df_dt = pd.read_csv(PATH_DAYTRADE)
        lucro = df_dt['Lucro'].sum()
        dados_externos['Lucro Trade'] = lucro
    else:
        dados_externos['Lucro Trade'] = 0
        
    # 5. CRM (Faturamento)
    if os.path.exists(PATH_CRM):
        df_crm = pd.read_csv(PATH_CRM)
        fat = df_crm[df_crm['Estagio'] == "5. Fechado (Ganho)"]['Valor_Est'].sum()
        dados_externos['Faturamento'] = fat
    else:
        dados_externos['Faturamento'] = 0

    return df, dados_externos

def save_data(df):
    df.to_csv(PATH_METAS, index=False)

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