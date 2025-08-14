import streamlit as st
import pandas as pd
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Evaluación Sanitaria", page_icon="🔬", layout="wide")
st.title("🔬 Evaluación Sanitaria de Campo")
st.write("Registre aquí la evaluación completa de plagas y enfermedades para un lote específico.")

st.divider()

# --- SECCIÓN 1: DATOS GENERALES ---
st.header("1. Datos Generales de la Evaluación")

col1, col2, col3 = st.columns(3)

with col1:
    fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())

with col2:
    sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
    sector_evaluado = st.selectbox("Lote / Sector Evaluado", options=sectores_del_fundo)

with col3:
    evaluador = st.text_input("Nombre del Evaluador")

# Por ahora, el resto de la aplicación estará aquí abajo.
# En el siguiente paso, añadiremos las pestañas de Plagas, Enfermedades y Perímetro.
