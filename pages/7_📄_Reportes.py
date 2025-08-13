import streamlit as st
import pandas as pd
import os
from io import BytesIO

# --- Configuración de la Página ---
st.set_page_config(page_title="Reportes y Exportación", page_icon="📄", layout="wide")
st.title("📄 Reportes y Exportación de Datos")
st.write("Descargue los datos completos de cada módulo en formato Excel.")

# --- Diccionario con los nombres de los archivos y sus descripciones ---
ARCHIVOS_DE_DATOS = {
    "Inventario de Productos": "Inventario_Productos.xlsx",
    "Registro de Aplicaciones": "Registro_Aplicaciones.xlsx",
    "Evaluación Fenológica Detallada": "Evaluacion_Fenologica_Detallada.xlsx",
    "Monitoreo de Plagas Detallado": "Monitoreo_Plagas_Detallado.xlsx"
}

# --- Función para crear un botón de descarga ---
def generar_boton_descarga(descripcion, nombre_archivo):
    """
    Verifica si un archivo existe y, si es así, muestra un botón para descargarlo.
    """
    st.subheader(f"Descargar: {descripcion}")
    
    if os.path.exists(nombre_archivo):
        # Leer el archivo en memoria
        with open(nombre_archivo, "rb") as file:
            # Usamos BytesIO para manejar el archivo en memoria, necesario para Streamlit
            buffer = BytesIO(file.read())
        
        # Crear el botón de descarga
        st.download_button(
            label=f"📥 Descargar {nombre_archivo}",
            data=buffer,
            file_name=nombre_archivo, # El nombre que tendrá el archivo al descargarse
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        # Mensaje si el archivo aún no ha sido creado
        st.info(f"Aún no se han generado datos para '{descripcion}'. El archivo se creará cuando guarde el primer registro en el módulo correspondiente.")
    
    st.divider()

# --- Generar un botón de descarga para cada archivo en el diccionario ---
for descripcion, nombre_archivo in ARCHIVOS_DE_DATOS.items():
    generar_boton_descarga(descripcion, nombre_archivo)

