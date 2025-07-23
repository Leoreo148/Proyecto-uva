import streamlit as st
import pandas as pd
from datetime import datetime

# Nombre del archivo Excel que funciona como base de datos
DB_FILE = "Observaciones_Campo.xlsx"

# --- Función para Cargar o Crear la Base de Datos ---
def cargar_db():
    try:
        # Intenta leer el archivo si ya existe
        df = pd.read_excel(DB_FILE)
    except FileNotFoundError:
        # Si no existe, crea un DataFrame vacío con las columnas correctas
        df = pd.DataFrame(columns=['Fecha', 'Estado_Fenologico_Codigo', 'Presencia_Oidio', 'Severidad_Oidio_Escala', 'Notas_Observacion'])
    return df

# --- Título de la Página ---
st.title("📋 Registro de Observaciones de Campo")

# --- Formulario para Ingresar Datos ---
with st.form("observation_form", clear_on_submit=True):
    fecha = st.date_input("Fecha de Observación", datetime.now())
    estado_fenologico = st.selectbox("Estado Fenológico", [1, 2, 3, 4, 5, 6], help="1: Brotación, 2: Crec. Pámpanos, 3: Floración, 4: Cuajado, 5: Envero, 6: Maduración")
    presencia_oidio = st.radio("¿Presencia de Oídio?", ["No", "Sí"])
    severidad = st.slider("Nivel de Severidad", 0, 4, 0, help="0: Nulo, 1: Inicial, 2: Moderado, 3: Severo, 4: Muy Severo")
    notas = st.text_area("Notas Adicionales")
    
    submitted = st.form_submit_button("Guardar Observación")

# --- Lógica para Guardar los Datos ---
if submitted:
    df = cargar_db()
    
    # Crear un nuevo registro como un DataFrame
    nuevo_registro = pd.DataFrame([{
        'Fecha': fecha,
        'Estado_Fenologico_Codigo': estado_fenologico,
        'Presencia_Oidio': presencia_oidio,
        'Severidad_Oidio_Escala': severidad,
        'Notas_Observacion': notas
    }])
    
    # Concatenar el DataFrame existente con el nuevo registro
    df_actualizado = pd.concat([df, nuevo_registro], ignore_index=True)
    
    # Guardar el DataFrame actualizado de vuelta al archivo Excel
    df_actualizado.to_excel(DB_FILE, index=False)
    
    st.success("✅ ¡Observación guardada correctamente!")


# --- Mostrar el Historial de Observaciones ---
st.header("Historial de Observaciones")
df_historial = cargar_db()
st.dataframe(df_historial)
