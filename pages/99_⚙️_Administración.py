import streamlit as st
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Administración", page_icon="⚙️", layout="wide")
st.title("⚙️ Panel de Administración de Datos")
st.write("Aquí puedes gestionar los archivos de datos de la aplicación y empezar de cero si es necesario.")

# --- LISTA DE TODOS LOS ARCHIVOS DE DATOS QUE LA APP GENERA ---
# (Asegúrate de que estos nombres coincidan con los usados en tus otras páginas)
DATA_FILES = [
    "kardex_fundo.xlsx",
    "Ordenes_de_Trabajo.xlsx",
    "Registro_Raleo.xlsx",
    "Registro_Horas_Tractor.xlsx",
    "Observaciones_Campo.xlsx",
    "Monitoreo_Mosca_Fruta.xlsx",
    "Evaluacion_Fenologica_Detallada.xlsx",
    "Registro_Diametro_Baya_Detallado.xlsx",
    "Evaluacion_Sanitaria_Completa.xlsx"
]

# --- ESTADO ACTUAL DE LOS ARCHIVOS ---
st.header("Estado de los Archivos de Datos")
st.write("Esta sección te muestra qué archivos de datos existen actualmente en el servidor de la aplicación.")

for file in DATA_FILES:
    if os.path.exists(file):
        st.success(f"✅ **Encontrado:** `{file}`")
    else:
        st.info(f"❌ **No encontrado:** `{file}`")

st.divider()

# --- ZONA DE PELIGRO: BORRADO DE DATOS ---
st.header("Zona de Borrado")
st.warning("⚠️ **¡Atención!** Esta acción es irreversible. Al borrar los archivos, se perderá todo el historial de registros (ingresos de inventario, monitoreos, aplicaciones, etc.). Úsalo solo cuando quieras empezar una simulación desde cero.")

confirmacion = st.checkbox("Sí, estoy seguro de que quiero borrar todos los archivos de datos de la aplicación.")

if st.button("🗑️ Borrar Todos los Datos Ahora", disabled=not confirmacion):
    with st.spinner("Borrando archivos..."):
        for file in DATA_FILES:
            if os.path.exists(file):
                try:
                    os.remove(file)
                    st.success(f"Archivo '{file}' borrado exitosamente.")
                except Exception as e:
                    st.error(f"No se pudo borrar el archivo '{file}'. Error: {e}")
            else:
                st.info(f"Archivo '{file}' no existía, no se necesita borrar.")
    st.info("Proceso de borrado completado. La aplicación se recargará.")
    st.rerun()
