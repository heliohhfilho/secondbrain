####### PROJETO LEGAL MAS BASE DE DADOS MUITO PEQUENO PARA REDE REURAL

import pandas as pd
import numpy as np
from datetime import date
import streamlit as st
import conexoes
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

def load_data():
    cols_log = ["Data", "Tipo", "Subtipo", "Valor", "Unidade", "Detalhe"]
    df_log = conexoes.load_gsheet("Log_Produtividade", cols_log)
    if not df_log.empty:
        df_log["Valor"] = pd.to_numeric(df_log["Valor"], errors='coerce').fillna(0)
        df = df_log
    return df

def fazer_analise_com_rede_neural(df):
    # 1. Garante a conversão da string da planilha para tipo datetime
    df['Data'] = pd.to_datetime(df['Data'], errors='coerce')

    # 2. Isola apenas o bloco lógico desejado
    df_paginas = df[df["Unidade"] == "Páginas"].copy()
    
    if df_paginas.empty:
        print("Erro: Nenhum dado com a unidade 'Páginas'.")
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

    df['eh_dia_mais_leitura'] = df['dia_semana'].apply(lambda x: 1 if x in top_2_dias else 0)
    
    df['leu_ontem'] = df['target'].shift(1).fillna(0)

    df['media_movel_7d'] = df['Valor'].rolling(window=7).mean().fillna(0)

    st.dataframe(df)
    st.markdown(top_2_dias)

    features = ['dia_semana', 'eh_dia_mais_leitura', 'leu_ontem', 'media_movel_7d']

    x = df[features]
    y = df['target']

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(x)

    model = MLPClassifier(
        hidden_layer_sizes=(32, 16),
        activation='relu',
        solver='adam',
        max_iter=500,
        random_state=42,
        early_stopping=True
    )

    model.fit(X_train_scaled, y)
    amanha_features = np.array([[
        7, 1, 0, 2.0
    ]])
    amanha_scaled = scaler.transform(amanha_features)
    probabilidade = model.predict_proba(amanha_scaled)
    st.markdown(f"Chance de ler amanhã: {probabilidade[0][1] * 100:.2f}%")

    # Acurácia global
    acuracia = model.score(X_train_scaled, y)
    st.markdown(f"**Acurácia no Treino:** {acuracia * 100:.2f}%")

    # Relatório completo (Precision, Recall, F1-Score)
    y_pred = model.predict(X_train_scaled)
    relatorio = classification_report(y, y_pred)
    
    st.markdown("**Relatório de Classificação:**")
    st.text(relatorio)

    st.markdown(f"{df.shape}")

df = load_data()
fazer_analise_com_rede_neural(df)