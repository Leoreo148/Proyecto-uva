import streamlit as st
import pandas as pd
from datetime import datetime
import json
from io import BytesIO
import plotly.express as px

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client
# NOTA: La librería streamlit_local_storage es un componente personalizado.
from streamlit_local_storage import LocalStorage

# --- Configuración de la Página ---
st.set_page_config(page_title="Diámetro de Baya", page_icon="🍇", layout="wide")
st.title("🍇 Medición de Diámetro de Baya")
st.write("Registre el diámetro (mm) de 3 bayas (superior, medio, inferior) para 2 racimos por cada una de las 25 plantas.")

# --- Inicialización y Constantes ---
localS = LocalStorage()
LOCAL_STORAGE_KEY = 'diametro_baya_offline_v2'
# Nombres de columna para la interfaz de usuario
columnas_display = ["Racimo 1 - Superior", "Racimo 1 - Medio", "Racimo 1 - Inferior", "Racimo 2 - Superior", "Racimo 2 - Medio", "Racimo 2 - Inferior"]
# Nombres de columna para la base de datos (sin espacios ni guiones)
columnas_db = ["Racimo_1_Superior", "Racimo_1_Medio", "Racimo_1_Inferior", "Racimo_2_Superior", "Racimo_2_Medio", "Racimo_2_Inferior"]

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
def cargar_diametro_supabase():
    """Carga el historial de mediciones desde la tabla de Supabase."""
    if supabase:
        try:
            response = supabase.table('Diametro_Baya').select("*").execute()
            df = pd.DataFrame(response.data)
            return df
        except Exception as e:
            st.error(f"Error al cargar el historial de Supabase: {e}")
    return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Diametro')
    return output.getvalue()

# --- Interfaz de Registro ---
with st.expander("➕ Registrar Nueva Medición", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        sectores_baya = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Medición:', options=sectores_baya)
    with col2:
        fecha_medicion = st.date_input("Fecha de Medición", datetime.now())
    
    st.subheader("Tabla de Ingreso de Diámetros (mm)")
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(0.0, index=plant_numbers, columns=columnas_display)
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key="editor_baya")
    
    if st.button("💾 Guardar Medición en Dispositivo"):
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_medicion.strftime("%Y-%m-%d")
        
        # Preparamos los registros para guardar, usando los nombres de columna de la DB
        df_para_guardar = df_para_guardar.reset_index().rename(columns={'index': 'Planta'})
        df_para_guardar.columns = ['Planta'] + columnas_db + ['Sector', 'Fecha']
        
        registros_json = df_para_guardar.to_dict('records')
        
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        registros_locales.extend(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.success(f"¡Medición guardada! Hay {len(registros_locales)} registros de plantas pendientes.")
        st.rerun()

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con la Base de Datos")
registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones de plantas guardadas localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora con Supabase"):
        if supabase:
            with st.spinner("Sincronizando..."):
                try:
                    # Insertamos los registros pendientes en la tabla de Supabase
                    supabase.table('Diametro_Baya').insert(registros_pendientes).execute()
                    localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                    st.success("¡Sincronización completada!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}. Sus datos locales están a salvo.")
        else:
            st.error("No se pudo sincronizar. La conexión con Supabase no está disponible.")
else:
    st.info("✅ Todas las mediciones de diámetro están sincronizadas.")

st.divider()

# --- HISTORIAL Y GRÁFICOS ---
st.header("📊 Historial y Análisis de Tendencia")
df_historial = cargar_diametro_supabase()

if df_historial is None or df_historial.empty:
    st.info("Aún no hay datos históricos para mostrar. Por favor, registre y sincronice algunas mediciones.")
else:
    st.subheader("📚 Historial de Mediciones")
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    sesiones = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
    
    for index, sesion in sesiones.sort_values(by='Fecha', ascending=False).head(5).iterrows():
        with st.container(border=True):
            df_sesion_actual = df_historial[(df_historial['Fecha'] == sesion['Fecha']) & (df_historial['Sector'] == sesion['Sector'])]
            valores_medidos = df_sesion_actual[columnas_db].to_numpy().flatten()
            promedio_sesion = valores_medidos[valores_medidos > 0].mean() if len(valores_medidos[valores_medidos > 0]) > 0 else 0
            
            col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
            col1.metric("Fecha", pd.to_datetime(sesion['Fecha']).strftime('%d/%m/%Y'))
            col2.metric("Sector", sesion['Sector'])
            col3.metric("Promedio General (mm)", f"{promedio_sesion:.2f}")
            with col4:
                st.write("")
                reporte_individual = to_excel(df_sesion_actual)
                st.download_button(
                    label="📥 Descargar",
                    data=reporte_individual,
                    file_name=f"Reporte_Diametro_{sesion['Sector']}_{pd.to_datetime(sesion['Fecha']).strftime('%Y%m%d')}.xlsx",
                    key=f"download_diametro_{sesion['Fecha']}_{sesion['Sector']}"
                )

    st.divider()

    st.subheader("📈 Gráfico de Tendencia")
    todos_los_sectores = sorted(df_historial['Sector'].astype(str).unique())
    sectores_a_graficar = st.multiselect(
        "Seleccione los sectores que desea comparar:",
        options=todos_los_sectores, default=todos_los_sectores
    )
    if sectores_a_graficar:
        df_filtrado = df_historial[df_historial['Sector'].isin(sectores_a_graficar)]
        # Usamos los nombres de columna de la DB para el análisis
        df_melted = df_filtrado.melt(
            id_vars=['Fecha', 'Sector'], value_vars=columnas_db,
            var_name='Posicion_Medicion', value_name='Diametro'
        )
        df_melted = df_melted[df_melted['Diametro'] > 0]
        df_tendencia = df_melted.groupby(['Fecha', 'Sector'])['Diametro'].mean().reset_index()
        
        if not df_tendencia.empty:
            fig = px.line(
                df_tendencia, x='Fecha', y='Diametro', color='Sector',
                title='Evolución del Diámetro Promedio de Baya por Sector', markers=True,
                labels={'Fecha': 'Fecha de Medición', 'Diametro': 'Diámetro Promedio (mm)'}
            )
            st.plotly_chart(fig, use_container_width=True)
