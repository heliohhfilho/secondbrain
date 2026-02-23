from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

import pandas as pd
import numpy as np
from datetime import date, timedelta
import streamlit as st
from modules import conexoes

def load_data():
    cols_log = ["Data", "Tipo", "Subtipo", "Valor", "Unidade", "Detalhe"]
    df_log = conexoes.load_gsheet("Log_Produtividade", cols_log)
    if not df_log.empty:
        df_log["Valor"] = pd.to_numeric(df_log["Valor"], errors='coerce').fillna(0)
        df = df_log
    return df

def fazer_analise_com_modelo_linear():

    df = load_data()

    # 1. Garante a conversão da string da planilha para tipo datetime
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

    # 2. Isola apenas o bloco lógico desejado
    df_paginas = df[df["Unidade"] == "Páginas"].copy()
    
    if df_paginas.empty:
        st.error("Erro: Nenhum dado com a unidade 'Páginas'.")
        return

    # 3. Agrega os dados: Soma todas as páginas lidas em um único dia
    df_agrupado = df_paginas.groupby('Data')['Valor'].sum().reset_index()
    
    # 4. Transforma a coluna Data no índice oficial do DataFrame
    df_agrupado.set_index('Data', inplace=True)
    
    # 5. Cria o vetor de tempo contínuo e interpola dias faltantes com 0
    idx = pd.date_range(start=df_agrupado.index.min(), end=pd.to_datetime(date.today()))
    df = df_agrupado.reindex(idx, fill_value=0)
    
    # 6. Engenharia das features da Rede Neural
    df['target'] = (df['Valor'] > 0).astype(int)
    df['dia_semana'] = df.index.dayofweek

    # Retorna uma lista com os 2 inteiros representando os dias da semana (0=Seg, 6=Dom)
    top_2_dias = df.groupby('dia_semana')['Valor'].sum().nlargest(2).index.tolist()

    df['eh_dia_mais_aulas'] = df['dia_semana'].apply(lambda x: 1 if x in top_2_dias else 0)
    
    df['aula_ontem'] = df['target'].shift(1).fillna(0)

    df['media_movel_7d'] = df['Valor'].rolling(window=7).mean().fillna(0)

    features = ['dia_semana', 'eh_dia_mais_aulas', 'aula_ontem', 'media_movel_7d']

    x = df[features]
    y = df['target']

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(x)

    # Replace the MLPClassifier with this:
    model = LogisticRegression(
        penalty='l2',      # L2 Regularization prevents overfitting on small data
        C=1.0,             # Inverse of regularization strength (lower = more regularized)
        random_state=42,
        solver='lbfgs'
    )
    model.fit(X_train_scaled, y)

    # 1. Identify today's exact state from the last row
    hoje_leu = df['target'].iloc[-1]

    if hoje_leu == 0:
        # --- INFERENCE HORIZON: TODAY ---
        alvo_data = date.today()
        alvo_dia_semana = alvo_data.weekday()
        
        # Lag features must shift back one more day
        aula_ontem_lag = df['target'].iloc[-2] if len(df) > 1 else 0
        media_lag = df['media_movel_7d'].iloc[-2] if len(df) > 1 else 0
        
        horizonte_texto = "Hoje"

    else:
        # --- INFERENCE HORIZON: TOMORROW ---
        alvo_data = date.today() + timedelta(days=1)
        alvo_dia_semana = alvo_data.weekday()
        
        # Lag features represent today's completed state
        aula_ontem_lag = 1 # We already know you read today
        media_lag = df['media_movel_7d'].iloc[-1]
        
        horizonte_texto = "Amanhã"

    # Common evaluation logic
    alvo_eh_top = 1 if alvo_dia_semana in top_2_dias else 0

    features_predicao = np.array([[
        alvo_dia_semana, 
        alvo_eh_top, 
        aula_ontem_lag, 
        media_lag
    ]])

    features_scaled = scaler.transform(features_predicao)
    probabilidade = model.predict_proba(features_scaled)[0][1]

    acuracia = model.score(X_train_scaled, y)

    return probabilidade, acuracia


def fazer_analise_curso():
    df = load_data()

    # 1. Garante a conversão da string da planilha para tipo datetime
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

    # 2. Isola apenas o bloco lógico desejado
    df_paginas = df[df["Unidade"] == "Aulas"].copy()
    
    if df_paginas.empty:
        st.error("Erro: Nenhum dado com a unidade 'Aulas'.")
        return

    # 3. Agrega os dados: Soma todas as páginas lidas em um único dia
    df_agrupado = df_paginas.groupby('Data')['Valor'].sum().reset_index()
    
    # 4. Transforma a coluna Data no índice oficial do DataFrame
    df_agrupado.set_index('Data', inplace=True)
    
    # 5. Cria o vetor de tempo contínuo e interpola dias faltantes com 0
    idx = pd.date_range(start=df_agrupado.index.min(), end=pd.to_datetime(date.today()))
    df = df_agrupado.reindex(idx, fill_value=0)
    
    # 6. Engenharia das features da Rede Neural
    df['target'] = (df['Valor'] > 0).astype(int)
    df['dia_semana'] = df.index.dayofweek

    # Retorna uma lista com os 2 inteiros representando os dias da semana (0=Seg, 6=Dom)
    top_2_dias = df.groupby('dia_semana')['Valor'].sum().nlargest(2).index.tolist()

    df['eh_dia_mais_aulas'] = df['dia_semana'].apply(lambda x: 1 if x in top_2_dias else 0)
    
    df['aula_ontem'] = df['target'].shift(1).fillna(0)

    df['media_movel_7d'] = df['Valor'].rolling(window=7).mean().fillna(0)

    features = ['dia_semana', 'eh_dia_mais_aulas', 'aula_ontem', 'media_movel_7d']

    x = df[features]
    y = df['target']

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(x)

    # Replace the MLPClassifier with this:
    model = LogisticRegression(
        penalty='l2',      # L2 Regularization prevents overfitting on small data
        C=1.0,             # Inverse of regularization strength (lower = more regularized)
        random_state=42,
        solver='lbfgs'
    )
    model.fit(X_train_scaled, y)

    # 1. Identify today's exact state from the last row
    hoje_leu = df['target'].iloc[-1]

    if hoje_leu == 0:
        # --- INFERENCE HORIZON: TODAY ---
        alvo_data = date.today()
        alvo_dia_semana = alvo_data.weekday()
        
        # Lag features must shift back one more day
        aula_ontem_lag = df['target'].iloc[-2] if len(df) > 1 else 0
        media_lag = df['media_movel_7d'].iloc[-2] if len(df) > 1 else 0
        
        horizonte_texto = "Hoje"

    else:
        # --- INFERENCE HORIZON: TOMORROW ---
        alvo_data = date.today() + timedelta(days=1)
        alvo_dia_semana = alvo_data.weekday()
        
        # Lag features represent today's completed state
        aula_ontem_lag = 1 # We already know you read today
        media_lag = df['media_movel_7d'].iloc[-1]
        
        horizonte_texto = "Amanhã"

    # Common evaluation logic
    alvo_eh_top = 1 if alvo_dia_semana in top_2_dias else 0

    features_predicao = np.array([[
        alvo_dia_semana, 
        alvo_eh_top, 
        aula_ontem_lag, 
        media_lag
    ]])

    features_scaled = scaler.transform(features_predicao)
    probabilidade = model.predict_proba(features_scaled)[0][1]

    acuracia = model.score(X_train_scaled, y)

    return horizonte_texto, probabilidade, acuracia
