import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Evaluación Sanitaria", page_icon="🔬", layout="wide")
st.title("🔬 Evaluación Sanitaria de Campo")
st.write("Registre la evaluación completa de plagas y enfermedades para un lote específico.")

# --- INICIALIZACIÓN Y NOMBRES DE ARCHIVOS ---
localS = LocalStorage()
ARCHIVO_EVALUACION = 'Evaluacion_Sanitaria_Completa.xlsx'
LOCAL_STORAGE_KEY = 'evaluacion_sanitaria_offline'

# --- DEFINICIÓN DE PLAGAS Y ENFERMEDADES (BASADO EN TU CARTILLA) ---
EVALUACIONES = {
    "Plagas": {
        "Trips": ["N° Indv/Racimo", "N° Indv/Hoja", "N° Indv/Brote"],
        "Arañita Roja": ["% Adultos/Hoja", "% Adultos/Racimo"],
        "Cochinilla Harinosa": ["% Tercio Medio", "% Tercio Super", "% Hojas", "% Racimo"],
        "Otras Plagas": ["% Incidencia", "Observaciones"]
    },
    "Enfermedades": {
        "Oidiosis": ["% Hojas", "% Racimos"],
        "Mildiu": ["% Hojas", "% Rac. Floral"],
        "Botrytis": ["% Racimos"],
        "Otras Enfermedades": ["% Incidencia", "Observaciones"]
    }
}

# --- FUNCIONES ---
def guardar_datos_excel(df_nuevos):
    try:
        df_existente = pd.DataFrame()
        if os.path.exists(ARCHIVO_EVALUACION):
            df_existente = pd.read_excel(ARCHIVO_EVALUACION)
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def cargar_datos_excel():
    if os.path.exists(ARCHIVO_EVALUACION):
        return pd.read_excel(ARCHIVO_EVALUACION)
    return None

def to_excel_detailed(evaluacion_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        resumen_df = pd.DataFrame([{"Fecha": evaluacion_row['Fecha'], "Sector": evaluacion_row['Sector'], "Evaluador": evaluacion_row['Evaluador']}])
        resumen_df.to_excel(writer, index=False, sheet_name='Resumen')
        pd.read_json(evaluacion_row['Datos_Evaluacion']).to_excel(writer, index=False, sheet_name='Detalle_Evaluacion')
    return output.getvalue()

# --- INICIALIZACIÓN DE MEMORIA DE SESIÓN ---
if 'sesion_evaluacion' not in st.session_state:
    st.session_state.sesion_evaluacion = {}

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Evaluación Sanitaria"):
    st.subheader("1. Datos Generales")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_evaluacion = st.date_input("Fecha", datetime.now())
    with col2:
        sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_evaluado = st.selectbox("Lote / Sector", options=sectores_del_fundo)
    with col3:
        evaluador = st.text_input("Nombre del Evaluador")

    st.subheader("2. Seleccionar y Llenar Evaluación")
    
    # Menú para elegir qué evaluar
    opcion_categoria = st.selectbox("Seleccione categoría:", list(EVALUACIONES.keys()))
    opcion_item = st.selectbox(f"Seleccione {opcion_categoria.rstrip('s')}:", list(EVALUACIONES[opcion_categoria].keys()))

    # Tabla de ingreso para 25 plantas
    st.write(f"**Ingrese los datos para '{opcion_item}' en 25 plantas:**")
    columnas_metricas = EVALUACIONES[opcion_categoria][opcion_item]
    df_plantilla = pd.DataFrame(0.0, index=[f"Planta {i+1}" for i in range(25)], columns=columnas_metricas)
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key=f"editor_{opcion_item}")

    if st.button(f"➕ Añadir '{opcion_item}' a la Evaluación Actual"):
        # Guardar los datos de esta tabla en la memoria de sesión
        st.session_state.sesion_evaluacion[opcion_item] = df_editada.to_json(orient='split')
        st.success(f"Datos de '{opcion_item}' añadidos a la evaluación actual.")

# --- RESUMEN DE LA SESIÓN ACTUAL Y GUARDADO ---
if st.session_state.sesion_evaluacion:
    st.divider()
    st.subheader("Resumen de la Evaluación en Curso")
    for item, data_json in st.session_state.sesion_evaluacion.items():
        st.write(f"**Datos para: {item}**")
        st.dataframe(pd.read_json(data_json, orient='split'), use_container_width=True)
    
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if st.button("💾 Guardar Evaluación Completa Localmente"):
            try:
                registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
                registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
                
                nueva_evaluacion = {
                    "Fecha": fecha_evaluacion.strftime("%Y-%m-%d"),
                    "Sector": sector_evaluado,
                    "Evaluador": evaluador,
                    "Datos_Evaluacion": json.dumps(st.session_state.sesion_evaluacion)
                }
                registros_locales.append(nueva_evaluacion)
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
                st.success("¡Evaluación guardada en el dispositivo!")
                st.session_state.sesion_evaluacion = {}
            except Exception as e:
                st.error(f"Error al guardar localmente: {e}")
    with col_g2:
        if st.button("❌ Limpiar Evaluación Actual"):
            st.session_state.sesion_evaluacion = {}
            st.rerun()

# --- SECCIÓN DE SINCRONIZACIÓN Y HISTORIAL ---
# (Esta parte es similar a los otros módulos y se puede añadir después)
