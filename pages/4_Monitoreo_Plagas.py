import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Monitoreo de Plagas", page_icon="🪰", layout="wide")
st.title("🪰 Monitoreo de Mosca de la Fruta por Especie")
st.write("Registre el número de capturas para cada especie en las trampas de monitoreo.")

# --- Formulario de Ingreso de Datos ---
with st.form("monitoreo_plagas_form", clear_on_submit=True):
    st.subheader("Nuevo Registro de Trampa")
    
    # Fila 1: Información general de la trampa
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_conteo = st.date_input("Fecha de Conteo", datetime.now())
    with col2:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_seleccionado = st.selectbox("Sector", options=sectores_del_fundo)
    with col3:
        codigo_trampa = st.text_input("Código de Trampa", placeholder="Ej: T1, 105...")

    st.divider()
    
    # Fila 2: Conteo por especie
    st.subheader("Conteo de Capturas por Especie")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        capturas_fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1)
    with col_b:
        capturas_distinta = st.number_input("Anastrepha distinta", min_value=0, step=1)
    with col_c:
        capturas_capitata = st.number_input("Ceratitis capitata", min_value=0, step=1)

    # Botón de envío del formulario
    submitted = st.form_submit_button("Guardar Conteo de Trampa")

# --- Lógica para Guardar los Datos ---
if submitted:
    if codigo_trampa:
        archivo_excel = 'Monitoreo_Plagas_Detallado.xlsx'
        
        # Calculamos el total de capturas para este registro
        total_capturas = capturas_fraterculus + capturas_distinta + capturas_capitata
        
        nuevo_registro = {
            "Fecha": [fecha_conteo.strftime("%Y-%m-%d")],
            "Sector": [sector_seleccionado],
            "Codigo_Trampa": [codigo_trampa],
            "A_fraterculus": [capturas_fraterculus],
            "A_distinta": [capturas_distinta],
            "C_capitata": [capturas_capitata],
            "Total_Capturas": [total_capturas]
        }
        df_nuevo = pd.DataFrame(nuevo_registro)
        
        if os.path.exists(archivo_excel):
            df_existente = pd.read_excel(archivo_excel)
            df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
        else:
            df_final = df_nuevo
            
        df_final.to_excel(archivo_excel, index=False)
        st.success(f"¡Conteo de la trampa '{codigo_trampa}' guardado exitosamente!")
    else:
        st.warning("Por favor, ingrese un código para la trampa.")

st.divider()

# --- Visualización del Historial de Registros ---
st.subheader("Historial de Conteos Recientes")
archivo_historial = 'Monitoreo_Plagas_Detallado.xlsx'

if os.path.exists(archivo_historial):
    df_historial = pd.read_excel(archivo_historial)
    st.dataframe(df_historial.tail(15).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no se han guardado registros de monitoreo de plagas.")
