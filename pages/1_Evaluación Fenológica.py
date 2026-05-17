import streamlit as st
import pandas as pd
from datetime import datetime
import json
from io import BytesIO

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client
# NOTA: La librería streamlit_local_storage es un componente personalizado.
from streamlit_local_storage import LocalStorage

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre los conteos y guárdelos en el dispositivo. Sincronice cuando tenga conexión.")

# --- Inicialización y Constantes ---
localS = LocalStorage()
LOCAL_STORAGE_KEY = 'fenologia_offline'

# Mapeo de nombres de columna para la interfaz y la base de datos
columnas_display = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
columnas_db = ['Punta_algodon', 'Punta_verde', 'Salida_de_hojas', 'Hojas_extendidas', 'Racimos_visibles']
mapeo_columnas = dict(zip(columnas_display, columnas_db))

# --- Conexión a Supabase ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- Nuevas Funciones para Supabase ---
@st.cache_data(ttl=60)
def cargar_fenologia_supabase():
    """Carga el historial de evaluaciones desde la tabla de Supabase."""
    if supabase:
        try:
            response = supabase.table('Evaluaciones_Fenologicas').select("*").execute()
            df = pd.DataFrame(response.data)
            return df
        except Exception as e:
            st.error(f"Error al cargar el historial de Supabase: {e}")
    return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Fenologia')
    return output.getvalue()

# --- Interfaz de Registro ---
with st.expander("➕ Registrar Nueva Evaluación", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Evaluación:', options=sectores_del_fundo, key="fenologia_sector")
    with col2:
        fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now(), key="fenologia_fecha")
    
    st.subheader("Tabla de Ingreso de Datos")
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(0, index=plant_numbers, columns=columnas_display)
    
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key="editor_fenologia")
    
    if st.button("💾 Guardar en Dispositivo"):
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_evaluacion.strftime("%Y-%m-%d")
        
        # Preparamos los registros para guardar, usando los nombres de columna de la DB
        df_para_guardar = df_para_guardar.reset_index().rename(columns={'index': 'Planta'})
        df_para_guardar = df_para_guardar.rename(columns=mapeo_columnas)
        
        registros_json = df_para_guardar.to_dict('records')
        
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        registros_locales.extend(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        
        st.success(f"¡Evaluación guardada! Hay {len(registros_locales)} registros de plantas pendientes.")
        st.rerun()

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con la Base de Datos")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros guardados localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora con Supabase"):
        if supabase:
            with st.spinner("Sincronizando..."):
                try:
                    # Insertamos los registros pendientes en la tabla de Supabase
                    supabase.table('Evaluaciones_Fenologicas').insert(registros_pendientes).execute()
                    localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                    st.success("¡Sincronización completada!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}. Sus datos locales están a salvo.")
        else:
            st.error("No se pudo sincronizar. La conexión con Supabase no está disponible.")
else:
    st.info("✅ Todos los registros de fenología están sincronizados.")

# --- Historial y Descarga ---
st.divider()
st.subheader("📚 Historial de Evaluaciones Fenológicas")
df_historial = cargar_fenologia_supabase()

if df_historial is not None and not df_historial.empty:
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    sesiones = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
    st.write("A continuación se muestra un resumen de las últimas evaluaciones realizadas.")
    
    for index, sesion in sesiones.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            df_sesion_actual = df_historial[(df_historial['Fecha'] == sesion['Fecha']) & (df_historial['Sector'] == sesion['Sector'])]
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.metric("Fecha de Evaluación", pd.to_datetime(sesion['Fecha']).strftime('%d/%m/%Y'))
            with col2:
                st.metric("Sector Evaluado", sesion['Sector'])
            with col3:
                st.write("")
                reporte_individual = to_excel(df_sesion_actual)
                st.download_button(
                    label="📥 Descargar Detalle",
                    data=reporte_individual,
                    file_name=f"Reporte_Fenologia_{sesion['Sector']}_{pd.to_datetime(sesion['Fecha']).strftime('%Y%m%d')}.xlsx",
                    key=f"download_fenologia_{sesion['Fecha']}_{sesion['Sector']}"
                )
else:
    st.info("Aún no se ha sincronizado ninguna evaluación fenológica.")
