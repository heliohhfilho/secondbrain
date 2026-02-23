import pandas as pd
from modules import conexoes

def preencher_dias_vazios():
    print("Iniciando rotina de preenchimento (Forward Fill)...")
    
    expected_cols = [
        "Data", "Peso_kg", "Altura_m", "Idade", "Gordura_Perc", 
        "Pescoco_cm", "Cintura_cm", "Quadril_cm",
        "Biceps_cm", "Peito_cm", "Coxa_cm",
        "Sono_hrs", "Humor_0_10", "Treino_Tipo", "Obs",
        "Agua_L", "Calorias_Ingeridas", "Objetivo_Tipo",
        "Meta_Peso_kg", "Meta_BF_perc", 
        "Prot_g", "Carb_g", "Gord_g"
    ]
    
    # 1. Carrega os dados brutos
    df = conexoes.load_gsheet("Bio", expected_cols)
    if df.empty:
        print("Dataset vazio. Nada a fazer.")
        return

    # 2. Converte Data e ordena cronologicamente
    df['Data'] = pd.to_datetime(df['Data'])
    df = df.sort_values('Data')
    df.set_index('Data', inplace=True)

    # 3. Cria um range contínuo de datas (do primeiro ao último dia registrado)
    vetor_tempo_completo = pd.date_range(start=df.index.min(), end=df.index.max())

    # 4. Reindexa e aplica o Forward Fill (ffill)
    # Reindex coloca NaN nos dias que não existiam. ffill copia o valor da linha anterior.
    df_tratado = df.reindex(vetor_tempo_completo).ffill()

    # 5. Formata de volta para o padrão esperado pelo seu sistema
    df_tratado.index.name = 'Data'
    df_tratado.reset_index(inplace=True)
    df_tratado['Data'] = df_tratado['Data'].dt.strftime('%Y-%m-%d')

    # (Opcional) Cast de tipos para garantir integridade após o ffill
    df_tratado["Idade"] = df_tratado["Idade"].astype(int)
    df_tratado["Calorias_Ingeridas"] = df_tratado["Calorias_Ingeridas"].astype(int)

    # 6. Salva de volta na planilha
    conexoes.save_gsheet("Bio", df_tratado)
    print(f"Sucesso! Dataset reindexado. Total de linhas agora: {len(df_tratado)}")

if __name__ == "__main__":
    preencher_dias_vazios()