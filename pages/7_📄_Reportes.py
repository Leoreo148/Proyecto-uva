import streamlit as st
import pandas as pd
import os
from io import BytesIO
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Archivo Digital y Reportes", page_icon="🗂️", layout="wide")
st.title("🗂️ Archivo Digital y Reportes")
st.write("Consulte, filtre y descargue todos los registros históricos del fundo.")

# --- Diccionario con los nombres de los archivos y sus descripciones ---
ARCHIVOS_DE_DATOS = {
    "Órdenes de Aplicación": "Tareas_Aplicacion.xlsx",
    "Inventario de Productos": "Inventario_Productos.xlsx",
    "Evaluación Fenológica": "Evaluacion_Fenologica_Detallada.xlsx",
    "Monitoreo de Plagas": "Monitoreo_Plagas_Detallado.xlsx",
    "Observaciones de Oídio": "Observaciones_Campo.xlsx",
    "Diámetro de Baya": "Registro_Diametro_Baya_Detallado.xlsx"
}

# --- Función para Cargar Datos ---
@st.cache_data
def cargar_datos(nombre_archivo):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    return None

# --- Función para convertir DataFrame a Excel en memoria ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    processed_data = output.getvalue()
    return processed_data

# --- Interfaz Principal ---

# 1. Selección del tipo de reporte
st.sidebar.header("Selección de Reporte")
tipo_reporte = st.sidebar.selectbox(
    "¿Qué historial desea consultar?",
    options=list(ARCHIVOS_DE_DATOS.keys())
)

st.header(f"Historial de: {tipo_reporte}")

# 2. Cargar el DataFrame seleccionado
nombre_archivo_seleccionado = ARCHIVOS_DE_DATOS[tipo_reporte]
df = cargar_datos(nombre_archivo_seleccionado)

# 3. Mostrar filtros y datos si el archivo existe
if df is not None:
    # --- Filtros dinámicos ---
    st.sidebar.divider()
    st.sidebar.header("Filtros")
    
    df_filtrado = df.copy()

    if 'Sector' in df_filtrado.columns:
        sectores_unicos = ['Todos'] + sorted(df_filtrado['Sector'].unique().tolist())
        sector_filtro = st.sidebar.selectbox("Filtrar por Sector:", sectores_unicos)
        if sector_filtro != 'Todos':
            df_filtrado = df_filtrado[df_filtrado['Sector'] == sector_filtro]

    if 'Fecha' in df_filtrado.columns and not df_filtrado.empty:
        df_filtrado['Fecha'] = pd.to_datetime(df_filtrado['Fecha'])
        fecha_min = df_filtrado['Fecha'].min().date()
        fecha_max = df_filtrado['Fecha'].max().date()
        
        try:
            rango_fechas = st.sidebar.date_input(
                "Filtrar por Rango de Fechas:",
                value=(fecha_min, fecha_max),
                min_value=fecha_min,
                max_value=fecha_max
            )
            if len(rango_fechas) == 2:
                df_filtrado = df_filtrado[(df_filtrado['Fecha'].dt.date >= rango_fechas[0]) & (df_filtrado['Fecha'].dt.date <= rango_fechas[1])]
        except Exception:
            st.sidebar.warning("No hay suficientes datos de fecha para crear un rango.")

    # --- Mostrar la tabla con los datos filtrados ---
    st.dataframe(df_filtrado, use_container_width=True)

    # --- Botón de Descarga ---
    st.sidebar.divider()
    st.sidebar.header("Exportación")
    
    if not df_filtrado.empty:
        df_para_descargar = to_excel(df_filtrado)
        st.sidebar.download_button(
            label=f"📥 Descargar Reporte Filtrado",
            data=df_para_descargar,
            file_name=f"Reporte_{tipo_reporte.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.sidebar.info("No hay datos filtrados para descargar.")

else:
    st.info(f"Aún no se han generado datos para '{tipo_reporte}'.")
