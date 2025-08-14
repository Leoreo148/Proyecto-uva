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
        # Hoja 1: Resumen
        resumen_df = pd.DataFrame({
            "Fecha": [pd.to_datetime(evaluacion_row['Fecha']).strftime('%d/%m/%Y')],
            "Sector": [evaluacion_row['Sector']],
            "Evaluador": [evaluacion_row['Evaluador']]
        })
        resumen_df.to_excel(writer, index=False, sheet_name='Resumen')
        
        # Hojas de datos
        pd.read_json(evaluacion_row['Datos_Plagas']).to_excel(writer, index=False, sheet_name='Plagas')
        pd.read_json(evaluacion_row['Datos_Enfermedades']).to_excel(writer, index=False, sheet_name='Enfermedades')
        pd.read_json(evaluacion_row['Datos_Perimetro']).to_excel(writer, index=False, sheet_name='Perimetro')
        
    return output.getvalue()

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Evaluación Sanitaria"):
    with st.form("evaluacion_sanitaria_form"):
        st.subheader("1. Datos Generales")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())
        with col2:
            sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
            sector_evaluado = st.selectbox("Lote / Sector Evaluado", options=sectores_del_fundo)
        with col3:
            evaluador = st.text_input("Nombre del Evaluador")

        st.divider()
        
        tab_plagas, tab_enfermedades, tab_perimetro = st.tabs(["PLAGAS", "ENFERMEDADES", "EVALUACIÓN DE PERÍMETRO"])

        with tab_plagas:
            st.subheader("2. Evaluación de Plagas (para 25 plantas)")
            # Plantilla basada en tu cartilla
            plagas_plantilla = {
                'Plaga': ['Trips', 'Mosca Blanca', 'Araña Roja', 'Cochinilla Harinosa', 'Pulgón', 'Empoasca'],
                'N° Indiv/Racimo': [0]*6,
                'N° Indiv/Hoja': [0]*6,
                'N° Indiv/Brot': [0]*6,
                '% Incidencia': [0.0]*6
            }
            df_plagas = st.data_editor(pd.DataFrame(plagas_plantilla), num_rows="dynamic", use_container_width=True, key="editor_plagas")

        with tab_enfermedades:
            st.subheader("3. Evaluación de Enfermedades (para 25 plantas)")
            enfermedades_plantilla = {
                'Enfermedad': ['Oidiosis', 'Mildiu', 'Botrytis', 'Pudrición Ácida'],
                '% Hojas Afectadas': [0.0]*4,
                '% Racimos Afectados': [0.0]*4
            }
            df_enfermedades = st.data_editor(pd.DataFrame(enfermedades_plantilla), num_rows="dynamic", use_container_width=True, key="editor_enfermedades")
        
        with tab_perimetro:
            st.subheader("4. Evaluación de Perímetro")
            perimetro_plantilla = {
                'Plaga/Enfermedad': ['Oidium', 'Mildiu', 'Arañita Roja', 'Cochinilla Harinosa'],
                '1er Perímetro - Hojas (%)': [0.0]*4,
                '1er Perímetro - Racimos (%)': [0.0]*4,
                '2do Perímetro - Hojas (%)': [0.0]*4,
                '2do Perímetro - Racimos (%)': [0.0]*4
            }
            df_perimetro = st.data_editor(pd.DataFrame(perimetro_plantilla), use_container_width=True, key="editor_perimetro")

        submitted = st.form_submit_button("✅ Guardar Evaluación Completa")

        if submitted:
            plagas_json = df_plagas.to_json(orient='records')
            enfermedades_json = df_enfermedades.to_json(orient='records')
            perimetro_json = df_perimetro.to_json(orient='records')
            nueva_evaluacion = pd.DataFrame([{"Fecha": fecha_evaluacion.strftime("%Y-%m-%d"), "Sector": sector_evaluado, "Evaluador": evaluador, "Datos_Plagas": plagas_json, "Datos_Enfermedades": enfermedades_json, "Datos_Perimetro": perimetro_json}])
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

