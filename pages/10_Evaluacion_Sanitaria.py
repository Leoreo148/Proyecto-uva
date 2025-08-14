import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO
import json

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Evaluación Sanitaria", page_icon="🔬", layout="wide")
st.title("🔬 Evaluación Sanitaria de Campo")
st.write("Registre aquí la evaluación completa de plagas y enfermedades para un lote específico.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_EVALUACION = 'Evaluacion_Sanitaria_Completa.xlsx'

# --- FUNCIONES ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_EVALUACION):
        return pd.read_excel(ARCHIVO_EVALUACION)
    return None

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = cargar_datos_excel()
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_EVALUACION, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel_detailed(evaluacion_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        resumen_df = pd.DataFrame([{"Fecha": evaluacion_row['Fecha'], "Sector": evaluacion_row['Sector'], "Evaluador": evaluacion_row['Evaluador']}])
        resumen_df.to_excel(writer, index=False, sheet_name='Resumen')
        
        # Leemos los datos JSON y los convertimos de nuevo a tablas
        datos = json.loads(evaluacion_row['Datos_Completos'])
        for nombre_tabla, tabla_json in datos.items():
            pd.read_json(tabla_json, orient='split').to_excel(writer, index=True, sheet_name=nombre_tabla)
            
    return output.getvalue()

# --- INICIALIZAR MEMORIA DE SESIÓN ---
if 'sesion_actual' not in st.session_state:
    st.session_state.sesion_actual = {}

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Evaluación Sanitaria", expanded=True):
    st.subheader("1. Datos Generales")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_evaluacion = st.date_input("Fecha", datetime.now())
    with col2:
        sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_evaluado = st.selectbox("Lote / Sector", options=sectores_del_fundo)
    with col3:
        evaluador = st.text_input("Nombre del Evaluador")

    st.divider()

    # --- PESTAÑAS PARA CADA SECCIÓN ---
    tab_plagas, tab_enfermedades, tab_perimetro = st.tabs(["PLAGAS", "ENFERMEDADES", "PERÍMETRO"])

    with tab_plagas:
        st.subheader("2. Evaluación de Plagas (para 25 plantas)")
        plagas_plantilla = { 'Planta': [f"Planta {i+1}" for i in range(25)], 'Trips (N° Ind/Hoja)': [0]*25, 'Arañita Roja (% Incid)': [0.0]*25, 'Cochinilla H. (% Incid)': [0.0]*25 }
        df_plagas = st.data_editor(pd.DataFrame(plagas_plantilla).set_index('Planta'), use_container_width=True, key="editor_plagas")

    with tab_enfermedades:
        st.subheader("3. Evaluación de Enfermedades (para 25 plantas)")
        enfermedades_plantilla = { 'Planta': [f"Planta {i+1}" for i in range(25)], 'Oidiosis (% Hojas)': [0.0]*25, 'Oidiosis (% Racimos)': [0.0]*25, 'Mildiu (% Hojas)': [0.0]*25 }
        df_enfermedades = st.data_editor(pd.DataFrame(enfermedades_plantilla).set_index('Planta'), use_container_width=True, key="editor_enfermedades")
    
    with tab_perimetro:
        st.subheader("4. Evaluación de Perímetro")
        perimetro_plantilla = { 'Item': ['Oidium (Hoja)', 'Oidium (Racimo)', 'Mildiu (Hoja)'], '1er Perímetro (%)': [0.0]*3, '2do Perímetro (%)': [0.0]*3 }
        df_perimetro = st.data_editor(pd.DataFrame(perimetro_plantilla).set_index('Item'), use_container_width=True, key="editor_perimetro")
        
    st.divider()

    if st.button("✅ Guardar Evaluación Completa"):
        # Guardar todos los datos en un solo objeto JSON
        datos_completos = {
            "Plagas": df_plagas.to_json(orient='split'),
            "Enfermedades": df_enfermedades.to_json(orient='split'),
            "Perimetro": df_perimetro.to_json(orient='split')
        }
        
        nueva_evaluacion = pd.DataFrame([{
            "Fecha": fecha_evaluacion.strftime("%Y-%m-%d"),
            "Sector": sector_evaluado,
            "Evaluador": evaluador,
            "Datos_Completos": json.dumps(datos_completos)
        }])
        
        exito, mensaje = guardar_datos_excel(nueva_evaluacion)
        if exito:
            st.success("¡Evaluación sanitaria guardada exitosamente!")
        else:
            st.error(f"Error al guardar: {mensaje}")

# --- HISTORIAL Y DESCARGA ---
st.divider()
st.subheader("📚 Historial de Evaluaciones Sanitarias")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    st.write("A continuación se muestra un resumen de las últimas evaluaciones.")
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

