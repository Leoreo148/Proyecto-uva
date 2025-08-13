import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre los conteos y guárdelos localmente. Sincronice cuando tenga conexión.")

# --- Inicialización del Almacenamiento Local ---
localS = LocalStorage()

# --- Nombres de Archivos y Claves ---
ARCHIVO_FENOLOGIA = 'Evaluacion_Fenologica_Detallada.xlsx'
LOCAL_STORAGE_KEY = 'fenologia_offline'

# --- Funciones ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_FENOLOGIA):
        return pd.read_excel(ARCHIVO_FENOLOGIA)
    return None

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = cargar_datos_excel()
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_FENOLOGIA, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- Interfaz de Registro (dentro de un expander) ---
with st.expander("➕ Registrar Nueva Evaluación"):
    col1, col2 = st.columns(2)
    with col1:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Evaluación:', options=sectores_del_fundo)
    with col2:
        fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())
    st.subheader("Tabla de Ingreso de Datos")
    columnas_fenologicas = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(0, index=plant_numbers, columns=columnas_fenologicas)
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key="editor_fenologia")
    if st.button("💾 Guardar Localmente"):
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_evaluacion.strftime("%Y-%m-%d")
        registros_json = df_para_guardar.reset_index().rename(columns={'index': 'Planta'}).to_dict('records')
        try:
            registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
            registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
            registros_locales.append(registros_json)
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
            st.success(f"¡Evaluación guardada en el dispositivo! Hay {len(registros_locales)} evaluaciones pendientes.")
        except Exception as e:
            st.error(f"Error al guardar localmente: {e}")

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")
try:
    registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
except:
    registros_pendientes = []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** evaluaciones guardadas localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            flat_list = [item for sublist in registros_pendientes for item in sublist]
            df_pendientes = pd.DataFrame(flat_list)
            exito, mensaje = guardar_datos_excel(df_pendientes)
            if exito:
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                st.success("¡Sincronización completada!")
                st.rerun()
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}. Sus datos locales están a salvo.")
else:
    st.info("✅ Todos los registros de fenología están sincronizados.")

st.divider()

# --- NUEVA SECCIÓN: HISTORIAL Y DESCARGA INDIVIDUAL ---
st.subheader("📚 Historial de Evaluaciones Fenológicas")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    # Agrupar por fecha y sector para identificar cada sesión de evaluación
    sesiones = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
    st.write("A continuación se muestra un resumen de las últimas evaluaciones realizadas.")
    
    # Mostrar un resumen de cada sesión con su botón de descarga
    for index, sesion in sesiones.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            df_sesion_actual = df_historial[(df_historial['Fecha'] == sesion['Fecha']) & (df_historial['Sector'] == sesion['Sector'])]
            
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.metric("Fecha de Evaluación", pd.to_datetime(sesion['Fecha']).strftime('%d/%m/%Y'))
            with col2:
                st.metric("Sector Evaluado", sesion['Sector'])
            with col3:
                st.write("") # Espacio para alinear el botón
                reporte_individual = to_excel(df_sesion_actual)
                st.downlo
