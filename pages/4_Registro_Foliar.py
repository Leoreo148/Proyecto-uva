import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registro Fenológico", page_icon="🌱")

# Verificar que se haya seleccionado un sector en la página principal
if 'sector' not in st.session_state:
    st.warning("Por favor, seleccione un sector en la página principal 'app'.")
    st.stop()

st.title(f"🌱 Registro Fenológico para el Sector: {st.session_state.sector}")
st.write("Rellene los datos de observación de la planta para el sector seleccionado.")

# --- FORMULARIO DE INGRESO DE DATOS ---
with st.form("registro_foliar_form", clear_on_submit=True):
    # Campos del formulario
    fecha_registro = st.date_input("Fecha de Registro", datetime.now())
    hojas_extendidas = st.number_input("N° de Hojas Extendidas", min_value=0, step=1)
    longitud_brote = st.number_input("Longitud del Brote (cm)", min_value=0.0, format="%.2f")
    estado_racimo = st.selectbox("Estado del Racimo", ["No visible", "Visible", "Separado"])
    
    # Botón de envío
    submitted = st.form_submit_button("Guardar Registro")

# --- LÓGICA PARA GUARDAR LOS DATOS ---
if submitted:
    archivo_excel = 'Registro_Foliar.xlsx'
    
    # Crear un diccionario con los nuevos datos
    nuevo_registro = {
        "Sector": [st.session_state.sector],
        "Fecha": [fecha_registro.strftime("%Y-%m-%d")],
        "Hojas_Extendidas": [hojas_extendidas],
        "Longitud_Brote_cm": [longitud_brote],
        "Estado_Racimo": [estado_racimo]
    }
    df_nuevo = pd.DataFrame(nuevo_registro)
    
    # Si el archivo ya existe, cargar los datos y añadir el nuevo registro
    if os.path.exists(archivo_excel):
        df_existente = pd.read_excel(archivo_excel)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        # Si el archivo no existe, el nuevo DataFrame es el final
        df_final = df_nuevo
        
    # Guardar el DataFrame actualizado en el archivo Excel
    df_final.to_excel(archivo_excel, index=False)
    
    st.success(f"¡Registro para el sector **{st.session_state.sector}** guardado exitosamente!")
