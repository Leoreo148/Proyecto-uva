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

st.divider()

# --- SECCIÓN 2: PESTAÑAS DE EVALUACIÓN ---
st.header("2. Evaluación Detallada por Planta")

# Creamos la estructura de las pestañas
tab_plagas, tab_enfermedades = st.tabs(["PLAGAS", "ENFERMEDADES"])

# Contenido de la Pestaña de Plagas
with tab_plagas:
    st.subheader("Evaluación de Plagas")
    st.write("Ingrese los datos para cada una de las 25 plantas evaluadas.")
    
    # Creamos una plantilla con las columnas exactas de tu cartilla
    plagas_plantilla = {
        'Planta': [f"Planta {i+1}" for i in range(25)],
        'TRIPS - N° Ind/Racimo': [0]*25,
        'TRIPS - N° Ind/Hoja': [0]*25,
        'MOSCA BLANCA - % Adulto/Hoja': [0.0]*25,
        'ARAÑITA ROJA - % Adulto/Hoja': [0.0]*25,
        'ARAÑITA ROJA - % Adulto/Racimo': [0.0]*25,
        'COCHINILLA H. - % Hojas': [0.0]*25,
        'COCHINILLA H. - % Racimo': [0.0]*25,
        'PULGÓN - % Hojas': [0.0]*25,
        'PULGÓN - % Racimo': [0.0]*25,
        'EMPOASCA - N° Ind/Hoja': [0]*25
    }
    
    # Usamos st.data_editor para crear la tabla interactiva
    df_plagas = st.data_editor(
        pd.DataFrame(plagas_plantilla).set_index('Planta'),
        use_container_width=True,
        key="editor_plagas"
    )

with tab_enfermedades:
    st.subheader("Evaluación de Enfermedades")
    st.write("Ingrese los datos para cada una de las 25 plantas evaluadas.")
    
    # Creamos la plantilla para enfermedades
    enfermedades_plantilla = {
        'Planta': [f"Planta {i+1}" for i in range(25)],
        'OIDIOSIS - % Hojas': [0.0]*25,
        'OIDIOSIS - % Racimos': [0.0]*25,
        'MILDIU - % Hojas': [0.0]*25,
        'MILDIU - % Rac. Floral': [0.0]*25,
        'BOTRYTIS - % Racimos': [0.0]*25,
        'PUD. ACIDA - % Racimos': [0.0]*25,
        'PENICILLIUM - % Racimos': [0.0]*25,
        'HONG. VASC - % Plantas': [0.0]*25
    }
    
    df_enfermedades = st.data_editor(
        pd.DataFrame(enfermedades_plantilla).set_index('Planta'),
        use_container_width=True,
        key="editor_enfermedades"
    )

# En el siguiente paso, añadiremos aquí la pestaña de Perímetro y el botón de Guardar.
# --- HISTORIAL Y DESCARGA ---
st.divider()
st.header("📚 Historial de Evaluaciones Sanitarias")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    st.write("A continuación se muestra un resumen de las últimas evaluaciones realizadas.")
    for index, evaluacion in df_historial.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.metric("Fecha", pd.to_datetime(evaluacion['Fecha']).strftime('%d/%m/%Y'))
            col2.metric("Sector", evaluacion['Sector'])
            col3.metric("Evaluador", evaluacion['Evaluador'])
            with col4:
                st.write("")
                reporte_individual = to_excel_detailed(evaluacion)
                st.download_button(
                    label="📥 Reporte",
                    data=reporte_individual,
                    file_name=f"Reporte_Sanitario_{evaluacion['Sector']}_{pd.to_datetime(evaluacion['Fecha']).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_sanitario_{index}"
                )
else:
    st.info("Aún no se ha registrado ninguna evaluación sanitaria.")

