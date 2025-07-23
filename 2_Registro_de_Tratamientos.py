import streamlit as st
import pandas as pd
from datetime import datetime

# Nombre del archivo Excel que funciona como base de datos
DB_FILE = "Registro_Tratamientos.xlsx"

# --- Función para Cargar o Crear la Base de Datos ---
def cargar_db():
    try:
        df = pd.read_excel(DB_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=['Fecha_Aplicacion', 'Producto_Utilizado', 'Tipo_Tratamiento'])
    return df

# --- Título de la Página ---
st.title("💧 Registro de Tratamientos Fitosanitarios")

# --- Formulario para Ingresar Datos ---
with st.form("treatment_form", clear_on_submit=True):
    fecha_aplicacion = st.date_input("Fecha de Aplicación", datetime.now())
    producto = st.text_input("Nombre del Producto Utilizado")
    tipo_tratamiento = st.selectbox("Tipo de Tratamiento", ["Preventivo", "Curativo", "Erradicante"])
    
    submitted = st.form_submit_button("Guardar Tratamiento")

# --- Lógica para Guardar los Datos ---
if submitted and producto: # Asegura que el nombre del producto no esté vacío
    df = cargar_db()
    
    nuevo_registro = pd.DataFrame([{
        'Fecha_Aplicacion': fecha_aplicacion,
        'Producto_Utilizado': producto,
        'Tipo_Tratamiento': tipo_tratamiento
    }])
    
    df_actualizado = pd.concat([df, nuevo_registro], ignore_index=True)
    df_actualizado.to_excel(DB_FILE, index=False)
    
    st.success("✅ ¡Tratamiento guardado correctamente!")
elif submitted:
    st.warning("⚠️ Por favor, ingrese el nombre del producto.")


# --- Mostrar el Historial de Tratamientos ---
st.header("Historial de Aplicaciones")
df_historial = cargar_db()
st.dataframe(df_historial)