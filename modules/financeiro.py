import streamlit as st
import pandas as pd

def render_page():
    
    def criar_linha_gasto(nome_banco):
        c_text, c_input = st.columns([1, 1], vertical_alignment="center")
        
        with c_text:
            st.markdown(f"**{nome_banco}**")
            
        with c_input:
            return st.number_input(
                label=nome_banco, 
                label_visibility="collapsed", 
                step=0.01,
                key=f"input_{nome_banco}" 
            )

    col1, col2, col3 = st.columns([1,2,2])

    with col1:
        col1_1, col1_2 = st.columns([1, 1], vertical_alignment="center")
        with col1_1:
            st.markdown("Salário")
        with col1_2:
            # Adicionado key="salario_principal"
            salario = st.number_input(
                label="Salario", 
                label_visibility="collapsed", 
                key="salario_principal"
            )

        st.markdown("""
            <div style="text-align: center; width: 100%; margin-top: 20px; margin-bottom: 10px;">
                <h5> Gastos Por Cartão </h5>
            </div>
            """, unsafe_allow_html=True)
        
        banco_pan = criar_linha_gasto("Banco Pan")
        itau = criar_linha_gasto("Itaú")
        mercado_pago = criar_linha_gasto("Mercado Pago")
        nubank = criar_linha_gasto("Nubank")

        st.markdown("""
            <div style="text-align: center; width: 100%; margin-top: 20px;">
                <h5> Outros Gastos </h5>
            </div>
            """, unsafe_allow_html=True)
        
        col1_5, col1_6 = st.columns([1, 1], vertical_alignment="center")
        with col1_5:
            # Key adicionada
            outros_gastos_1 = st.text_input(
                label="Desc_Outros", 
                label_visibility="collapsed", 
                placeholder="Descrição",
                key="desc_outros_1"
            )
        with col1_6:
            # Key adicionada
            outros_gastos_1_valor = st.number_input(
                label="Val_Outros", 
                label_visibility="collapsed",
                key="val_outros_1"
            )

        st.markdown("""
            <div style="text-align: center; width: 100%; margin-top: 20px;">
                <h5> Gastos Totais </h5>
            </div>
            """, unsafe_allow_html=True)
        
        col1_7, col1_8 = st.columns([1, 1], vertical_alignment="center")
        with col1_7:
            st.markdown("**Total Cartões**")
            st.markdown("**Total Outros**")
            st.markdown("**Total Geral**")
        with col1_8:
            cartoes = banco_pan + itau + mercado_pago + nubank
            outros = outros_gastos_1_valor

            total_gastos = cartoes + outros

            st.markdown(f"R$ {cartoes:.2f}")
            st.markdown(f"R$ {outros:.2f}")
            st.markdown(f"R$ {total_gastos:.2f}")

        st.markdown("""
            <div style="text-align: center; width: 100%; margin-top: 20px;">
                <h5> Balanço </h5>
            </div>
            """, unsafe_allow_html=True)
        
        col1_9, col1_0 = st.columns(2)
        with col1_9:
            st.markdown("**Entradas**")
            st.markdown("**Gastos**")
            st.markdown("**Investimentos**")
            st.markdown("**Saídas**")
            st.markdown("**Balnaço**")

        with col1_0:
            entradas_totais = salario
            investimentos = 0
            saidas = total_gastos + investimentos
            balanco = entradas_totais - saidas
            st.markdown(f"R$ {entradas_totais:.2f}")
            st.markdown(f"R$ {total_gastos:.2f}")
            st.markdown(f"R$ {investimentos:.2f}")
            st.markdown(f"R$ {saidas:.2f}")
            st.markdown(f"R$ {balanco:.2f}")

        
    with col2:
        
        df = pd.DataFrame(
            [
                {"O Quê": "Lux Tour", "Vezes": "8", "Valor": 66.34, "Pagas": 2, "Restantes":6, "Faltam": 398.04, "Cartão": "Banco Pan"}
            ]
        )

        st.markdown("""
            <div style="text-align: center; width: 100%; margin-top: 20px;">
                <h5> Parcelas </h5>
            </div>
            """, unsafe_allow_html=True)

        df_editado = st.data_editor(
        df, 
        num_rows="dynamic", 
        width='stretch'
    )


if __name__ == "__main__":
    render_page()