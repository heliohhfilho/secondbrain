import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date
import os

# --- ARQUIVOS ---
PATH_DECISOES = os.path.join('data', 'decisoes_matrix.csv')

def load_data():
    # Estrutura Normalizada: Cada linha é um voto num critério
    if not os.path.exists(PATH_DECISOES):
        return pd.DataFrame(columns=["Decisao_ID", "Titulo", "Opcao", "Criterio", "Peso", "Nota"])
    return pd.read_csv(PATH_DECISOES)

def save_data(df):
    df.to_csv(PATH_DECISOES, index=False)

def render_page():
    st.header("🧠 Decision Lab (Matriz Ponderada)")
    st.caption("Quando a dúvida bater, deixe a matemática decidir.")
    
    df = load_data()
    
    # --- NOVA DECISÃO (WIZARD) ---
    with st.expander("➕ Nova Decisão (Configurar Matriz)"):
        with st.form("form_setup"):
            d_titulo = st.text_input("Qual é a dúvida? (Ex: Qual carro comprar?)")
            
            c1, c2 = st.columns(2)
            # Opções (separadas por vírgula)
            d_opcoes = c1.text_area("Opções (Separadas por vírgula)", "Civic Si, Golf GTI, Jetta GLI")
            
            # Critérios e Pesos (Mini sintaxe: Criterio=Peso)
            d_criterios = c2.text_area("Critérios=Peso (1 a 5)", "Preço=5\nEmoção=4\nRevenda=3\nManutenção=3")
            
            if st.form_submit_button("Criar Matriz"):
                if d_titulo and d_opcoes and d_criterios:
                    # Gera ID
                    new_id = 1 if df.empty else df['Decisao_ID'].max() + 1
                    
                    # Processa Opções e Critérios
                    lista_opcoes = [x.strip() for x in d_opcoes.split(',') if x.strip()]
                    lista_criterios = []
                    
                    for linha in d_criterios.split('\n'):
                        if '=' in linha:
                            crit, peso = linha.split('=')
                            lista_criterios.append((crit.strip(), int(peso.strip())))
                    
                    # Cria as linhas no DF (Produto Cartesiano: Opcao x Criterio)
                    novas_linhas = []
                    for op in lista_opcoes:
                        for crit, peso in lista_criterios:
                            novas_linhas.append({
                                "Decisao_ID": new_id,
                                "Titulo": d_titulo,
                                "Opcao": op,
                                "Criterio": crit,
                                "Peso": peso,
                                "Nota": 0 # Nota inicial
                            })
                    
                    df = pd.concat([df, pd.DataFrame(novas_linhas)], ignore_index=True)
                    save_data(df)
                    st.success("Matriz Criada! Agora avalie as opções abaixo.")
                    st.rerun()

    # --- SELETOR DE DECISÃO ---
    if df.empty:
        st.info("Nenhuma decisão cadastrada.")
        return

    decisoes_unicas = df[['Decisao_ID', 'Titulo']].drop_duplicates().sort_values('Decisao_ID', ascending=False)
    
    col_sel, col_del = st.columns([4, 1])
    opcao_selecionada = col_sel.selectbox("Selecione a Decisão para Avaliar:", decisoes_unicas['Titulo'].tolist())
    
    # Pega ID da selecionada
    id_selecionado = decisoes_unicas[decisoes_unicas['Titulo'] == opcao_selecionada]['Decisao_ID'].values[0]
    
    if col_del.button("🗑️ Apagar Decisão"):
        df = df[df['Decisao_ID'] != id_selecionado]
        save_data(df)
        st.rerun()

    st.divider()
    
    # --- ÁREA DE VOTAÇÃO ---
    df_atual = df[df['Decisao_ID'] == id_selecionado].copy()
    
    # Pivotar para edição fácil (Linhas=Opções, Colunas=Critérios)
    # Mas o Streamlit data_editor não edita pivot facilmente. Vamos iterar por critério.
    
    criterios_unicos = df_atual[['Criterio', 'Peso']].drop_duplicates()
    
    st.subheader(f"Avaliação: {opcao_selecionada}")
    st.caption("Dê notas de 0 a 10 para cada opção em cada critério.")
    
    # Form para salvar notas
    with st.form("form_notas"):
        cols = st.columns(len(criterios_unicos))
        
        # Para cada critério, uma coluna
        for idx, (i, row_crit) in enumerate(criterios_unicos.iterrows()):
            crit_nome = row_crit['Criterio']
            crit_peso = row_crit['Peso']
            
            with cols[idx]:
                st.markdown(f"**{crit_nome}** (Peso {crit_peso})")
                
                # Filtra as linhas desse critério
                subset = df_atual[df_atual['Criterio'] == crit_nome]
                
                for j, row_nota in subset.iterrows():
                    # Input de nota
                    val = st.number_input(
                        f"{row_nota['Opcao']}", 
                        0, 10, int(row_nota['Nota']), 
                        key=f"n_{row_nota['Decisao_ID']}_{row_nota['Opcao']}_{crit_nome}"
                    )
                    # Atualiza no DF principal (na memória por enquanto)
                    # Precisamos de um jeito de salvar isso no submit
                    # Truque: Usar session state ou atualizar direto no DF global no submit
                    df.loc[
                        (df['Decisao_ID'] == id_selecionado) & 
                        (df['Opcao'] == row_nota['Opcao']) & 
                        (df['Criterio'] == crit_nome), 
                        'Nota'
                    ] = val

        if st.form_submit_button("💾 Calcular Resultado"):
            save_data(df)
            st.success("Notas salvas!")
            st.rerun()

    # --- RESULTADO FINAL ---
    st.divider()
    
    # Cálculo da Pontuação Ponderada
    # Score = Nota * Peso
    df_atual['Pontuacao'] = df_atual['Nota'] * df_atual['Peso']
    
    # Agrupa por Opção
    resultado = df_atual.groupby('Opcao')['Pontuacao'].sum().reset_index().sort_values('Pontuacao', ascending=False)
    
    # O Vencedor
    vencedor = resultado.iloc[0]
    
    c_res1, c_res2 = st.columns([1, 2])
    
    with c_res1:
        st.markdown("### 🏆 Vencedor")
        st.metric(label="Melhor Escolha", value=vencedor['Opcao'], delta=f"{vencedor['Pontuacao']} pontos")
        
        # Pódio
        st.write("**Ranking:**")
        for i, r in resultado.iterrows():
            st.write(f"{i+1}. **{r['Opcao']}**: {r['Pontuacao']}")

    with c_res2:
        st.markdown("### 📊 Raio-X da Decisão")
        # Gráfico de Barras Empilhadas (Mostra onde cada um ganhou ponto)
        fig = px.bar(
            df_atual, 
            x='Opcao', 
            y='Pontuacao', 
            color='Criterio', 
            title="Detalhamento por Critério (Nota x Peso)",
            text='Nota'
        )
        st.plotly_chart(fig, use_container_width=True)