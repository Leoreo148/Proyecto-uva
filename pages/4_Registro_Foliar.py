import streamlit as st
import pandas as pd
import os
from datetime import datetime

st.set_page_config(page_title="Registro Fenológico", page_icon="🌱")

st.title("🌱 Registro Fenológico (Datos Foliares)")

# --- SELECTOR DE SECTOR (PROPIO DE ESTA PÁGINA) ---
sectores_del_fundo = ['W1', 'W2', 'W3', 'K1', 'K2', 'K3', 'General']
sector_seleccionado = st.selectbox(
    'Seleccione el Sector donde está realizando la observación:',
    options=sectores_del_fundo
)

st.divider()

# --- FORMULARIO DE INGRESO DE DATOS ---
st.write(f"Rellenando datos para el sector: **{sector_seleccionado}**")

with st.form("registro_foliar_form", clear_on_submit=True):
    fecha_registro = st.date_input("Fecha de Registro", datetime.now())
    hojas_extendidas = st.number_input("N° de Hojas Extendidas", min_value=0, step=1)
    longitud_brote = st.number_input("Longitud del Brote (cm)", min_value=0.0, format="%.2f")
    estado_racimo = st.selectbox("Estado del Racimo", ["No visible", "Visible", "Separado"])
    
    submitted = st.form_submit_button("Guardar Registro")

# --- LÓGICA PARA GUARDAR LOS DATOS ---
if submitted:
    archivo_excel = 'Registro_Foliar.xlsx'
    
    nuevo_registro = {
        "Sector": [sector_seleccionado], # Usamos la variable de esta página
        "Fecha": [fecha_registro.strftime("%Y-%m-%d")],
        "Hojas_Extendidas": [hojas_extendidas],
        "Longitud_Brote_cm": [longitud_brote],
        "Estado_Racimo": [estado_racimo]
    }
    df_nuevo = pd.DataFrame(nuevo_registro)
    
    if os.path.exists(archivo_excel):
        df_existente = pd.read_excel(archivo_excel)
        df_final = pd.concat([df_existente, df_nuevo], ignore_index=True)
    else:
        df_final = df_nuevo
        
    df_final.to_excel(archivo_excel, index=False)
    
    st.success(f"¡Registro para el sector **{sector_seleccionado}** guardado exitosamente!")
