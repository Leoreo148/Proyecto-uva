import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre los conteos y guárdelos localmente. Sincronice cuando tenga conexión.")

# --- Inicialización del Almacenamiento Local ---
localS = LocalStorage()

# --- Nombres de Archivos y Claves ---
ARCHIVO_FENOLOGIA = 'Evaluacion_Fenologica_Detallada.xlsx'
LOCAL_STORAGE_KEY = 'fenologia_offline'

# --- Funciones ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_FENOLOGIA):
        return pd.read_excel(ARCHIVO_FENOLOGIA)
    return None

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = cargar_datos_excel()
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_FENOLOGIA, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- Interfaz de Registro (dentro de un expander) ---
with st.expander("➕ Registrar Nueva Evaluación"):
    col1, col2 = st.columns(2)
    with col1:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Evaluación:', options=sectores_del_fundo, key="fenologia_sector")
    with col2:
        fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now(), key="fenologia_fecha")
    st.subheader("Tabla de Ingreso de Datos")
    columnas_fenologicas = ['Punta algodón', 'Punta ve
