import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import os
import plotly.graph_objects as go

from modules import conexoes

def load_data():
    cols = ["Data", "Banca_Inicial", "Banca_Final", "Lucro", "Perc_Dia", "Risco_USD", "Saque_USD", "Aportes_USD"]
    df = conexoes.load_gsheet("DayTrade", cols)
    
    if not df.empty:
        # Saneamento para cálculos (converte tudo que é valor para float)
        numeric_cols = ["Banca_Inicial", "Banca_Final", "Lucro", "Perc_Dia", "Risco_USD", "Saque_USD", "Aportes_USD"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0.0)
    return df

def save_data(df):
    # Converte a coluna de Data para string antes de salvar para evitar erro de JSON no GSheets
    df_save = df.copy()
    df_save['Data'] = df_save['Data'].astype(str)
    conexoes.save_gsheet("DayTrade", df_save)

def render_page():
    st.header("📈 Day Trade (Gestão & Performance)")
    
    df = load_data()
    
    # --- SIDEBAR ---
    with st.sidebar:
        with st.expander("⚙️ Configurações de Risco", expanded=True):
            cotacao_dolar = st.number_input("Cotação Dólar (R$)", value=5.80, step=0.01)
            meta_diaria = st.slider("Meta de Gain (%)", 0.1, 10.0, 3.0, step=0.1)
            stop_loss_pct = st.slider("Max Stop Loss (%)", 0.5, 20.0, 5.0, step=0.5)
            
        st.subheader("📝 Fechamento do Dia")
        dt_trade = st.date_input("Data do Pregão", value=date.today())
        
        banca_sugerida = 100.0
        if not df.empty:
            df_sorted = df.sort_values("Data")
            banca_sugerida = df_sorted.iloc[-1]['Banca_Final']
            
        banca_ini = st.number_input("Banca Inicial", min_value=0.0, value=float(banca_sugerida))
        
        risco_max_usd = banca_ini * (stop_loss_pct / 100)
        st.caption(f"🛑 Stop Loss Técnico: **$ {risco_max_usd:.2f}**")
        
        aportes = st.number_input("Aportes Extras", min_value=0.0)
        banca_fim = st.number_input("Banca Final", min_value=0.0, value=float(banca_sugerida))
        
        total_investido = banca_ini + aportes
        lucro_prev = banca_fim - total_investido
        perc_prev = (lucro_prev / total_investido * 100) if total_investido > 0 else 0
        
        st.markdown("---")
        if lucro_prev > 0: 
            st.success(f"Gain: +${lucro_prev:.2f} (+{perc_prev:.2f}%)")
        elif lucro_prev < 0: 
            st.error(f"Loss: -${abs(lucro_prev):.2f} ({perc_prev:.2f}%)")
            if abs(lucro_prev) > risco_max_usd:
                st.warning(f"⚠️ STOP LOSS ESTOURADO!")
        else: 
            st.info("0x0 (Breakeven)")
            
        saque = st.number_input("Saque ($)", min_value=0.0)
        
        if st.button("Salvar Diário"):
            novo = {
                "Data": dt_trade, "Banca_Inicial": banca_ini, "Banca_Final": banca_fim,
                "Lucro": lucro_prev, "Perc_Dia": perc_prev, 
                "Risco_USD": risco_max_usd, "Saque_USD": saque, "Aportes_USD": aportes
            }
            df = df[df['Data'] != str(dt_trade)]
            df = pd.concat([df, pd.DataFrame([novo])], ignore_index=True)
            save_data(df)
            st.success("Salvo!")
            st.rerun()

    # --- DASHBOARD ---
    if df.empty:
        st.info("Cadastre seu primeiro trade na barra lateral.")
        return

    df['Data'] = pd.to_datetime(df['Data'])
    df = df.sort_values("Data")
    
    lucro_total = df['Lucro'].sum()
    aportes_total = df['Aportes_USD'].sum()
    win_rate = (len(df[df['Lucro'] > 0]) / len(df) * 100) if len(df) > 0 else 0
    media_retorno = df['Perc_Dia'].mean()
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lucro Líquido", f"$ {lucro_total:,.2f}", delta=f"R$ {lucro_total*cotacao_dolar:,.2f}")
    c2.metric("Win Rate", f"{win_rate:.1f}%")
    cor_media = "normal" if media_retorno >= 0 else "inverse"
    c3.metric("Retorno Médio", f"{media_retorno:.2f}%", delta_color=cor_media)
    
    hoje = date.today()
    df_mes = df[(df['Data'].dt.month == hoje.month) & (df['Data'].dt.year == hoje.year)]
    caixa_mes = max(0, df_mes['Lucro'].sum())
    status_saque = "Disponível" if hoje.day >= 5 else "Libera dia 05"
    c4.metric("Caixa Mês", f"$ {caixa_mes:,.2f}", delta=status_saque)

    st.divider()
    t1, t2, t3 = st.tabs(["📉 Histórico", "🔮 Projeção Detalhada", "🧮 Calc Reversa"])

    # --- ABA 1: HISTÓRICO ---
    with t1:
        c_g1, c_g2 = st.columns([2, 1])
        with c_g1: st.line_chart(df.set_index("Data")["Banca_Final"], color="#00FF00")
        with c_g2: 
            df['Color'] = df['Lucro'].apply(lambda x: '#00FF00' if x>=0 else '#FF0000')
            st.bar_chart(df.set_index("Data")["Lucro"])
        
        st.subheader("Extrato / CRUD")
        df_edit = df.sort_values("Data", ascending=False).reset_index(drop=True)
        edited_df = st.data_editor(
            df_edit,
            column_config={
                "Data": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Banca_Inicial": st.column_config.NumberColumn("Início", format="$ %.2f"),
                "Banca_Final": st.column_config.NumberColumn("Fim", format="$ %.2f"),
                "Lucro": st.column_config.NumberColumn("Lucro", format="$ %.2f", disabled=True),
                "Perc_Dia": st.column_config.NumberColumn("%", format="%.2f %%", disabled=True),
            },
            use_container_width=True, num_rows="dynamic", key="dt_editor"
        )
        if not edited_df.equals(df_edit):
            edited_df['Lucro'] = edited_df['Banca_Final'] - (edited_df['Banca_Inicial'] + edited_df['Aportes_USD'])
            edited_df['Perc_Dia'] = edited_df.apply(lambda x: (x['Lucro']/(x['Banca_Inicial']+x['Aportes_USD'])*100) if (x['Banca_Inicial']+x['Aportes_USD'])>0 else 0, axis=1)
            edited_df = edited_df.sort_values("Data")
            save_data(edited_df)
            st.rerun()
            
        with st.expander("🗑️ Excluir Dias"):
             df_del = df.sort_values("Data", ascending=False)
             for idx, row in df_del.iterrows():
                c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
                c1.write(row['Data'].strftime('%d/%m/%Y'))
                c2.write(f"$ {row['Lucro']:,.2f}")
                if c4.button("🗑️", key=f"d_{idx}"):
                    df = df.drop(idx)
                    save_data(df)
                    st.rerun()

    # --- ABA 2: PROJEÇÃO DETALHADA ---
    with t2:
        st.subheader("Futuro (3 Meses)")
        if not df.empty:
            banca_now = df.iloc[-1]['Banca_Final']
            
            # Trava de segurança para média negativa
            taxa_real = max(-2.0, media_retorno)
            taxa_meta = meta_diaria
            
            proj = []
            saldo_real = banca_now
            saldo_meta = banca_now
            
            # Gera 66 dias (3 meses de 22 dias uteis)
            for i in range(1, 67):
                # Guarda inicio
                ini_real = saldo_real
                ini_meta = saldo_meta
                
                # Aplica juros
                saldo_real = saldo_real * (1 + (taxa_real/100))
                saldo_meta = saldo_meta * (1 + (taxa_meta/100))
                
                # Lucro do dia
                lucro_real_dia = saldo_real - ini_real
                lucro_meta_dia = saldo_meta - ini_meta
                
                proj.append({
                    "Dia": i,
                    "Ini_Real": ini_real, "Lucro_Real": lucro_real_dia, "Fim_Real": saldo_real,
                    "Ini_Meta": ini_meta, "Lucro_Meta": lucro_meta_dia, "Fim_Meta": saldo_meta
                })
            
            df_p = pd.DataFrame(proj)
            
            # Cards Resumo
            c1, c2 = st.columns(2)
            c1.metric("Cenário Realista (Final)", f"$ {df_p.iloc[-1]['Fim_Real']:,.2f}", f"{taxa_real:.2f}% média/dia")
            c2.metric("Cenário Meta (Final)", f"$ {df_p.iloc[-1]['Fim_Meta']:,.2f}", f"{taxa_meta:.2f}% meta/dia")
            
            st.line_chart(df_p.set_index("Dia")[["Fim_Real", "Fim_Meta"]])
            
            st.divider()
            
            # TABELAS MENSAIS
            # Divide o DataFrame em 3 pedaços de 22 dias
            df_m1 = df_p.iloc[0:22]
            df_m2 = df_p.iloc[22:44]
            df_m3 = df_p.iloc[44:66]
            
            # Configuração de Colunas para exibição
            cols_cfg = {
                "Dia": st.column_config.NumberColumn("Dia", format="%d"),
                "Ini_Real": st.column_config.NumberColumn("Início ($)", format="$ %.2f"),
                "Lucro_Real": st.column_config.NumberColumn("Lucro Real ($)", format="$ %.2f"),
                "Fim_Real": st.column_config.NumberColumn("Fim Real ($)", format="$ %.2f"),
                "Fim_Meta": st.column_config.NumberColumn("Meta Alvo ($)", format="$ %.2f"),
            }
            
            # Renderiza as 3 tabelas
            c_m1, c_m2, c_m3 = st.columns(3)
            
            with c_m1:
                st.markdown("### 📅 Mês 1")
                st.dataframe(
                    df_m1[["Dia", "Ini_Real", "Lucro_Real", "Fim_Real", "Fim_Meta"]],
                    use_container_width=True, hide_index=True, column_config=cols_cfg
                )
            
            with c_m2:
                st.markdown("### 📅 Mês 2")
                st.dataframe(
                    df_m2[["Dia", "Ini_Real", "Lucro_Real", "Fim_Real", "Fim_Meta"]],
                    use_container_width=True, hide_index=True, column_config=cols_cfg
                )
                
            with c_m3:
                st.markdown("### 📅 Mês 3")
                st.dataframe(
                    df_m3[["Dia", "Ini_Real", "Lucro_Real", "Fim_Real", "Fim_Meta"]],
                    use_container_width=True, hide_index=True, column_config=cols_cfg
                )

    # --- ABA 3: CALC REVERSA ---
    with t3:
        st.subheader("Calculadora de Metas")
        c1, c2 = st.columns(2)
        target_brl = c1.number_input("Renda Mensal (R$)", 5000.0, step=500.0)
        days = c2.slider("Dias Operados", 10, 22, 20)
        
        banca = df.iloc[-1]['Banca_Final'] if not df.empty else 1000.0
        target_usd = target_brl / cotacao_dolar
        req_usd = target_usd / days
        req_perc = (req_usd / banca) * 100
        
        st.metric("Meta Diária ($)", f"$ {req_usd:.2f}")
        cor_r = "inverse" if req_perc > 3 else "normal"
        st.metric("Meta Diária (%)", f"{req_perc:.2f}%", delta="Risco Alto" if req_perc > 3 else "Viável", delta_color=cor_r)