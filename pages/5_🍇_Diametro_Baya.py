import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Observaciones de Oídio", page_icon="📋")
st.title("📋 Registro de Observaciones de Oídio")
st.write("Registre la presencia y severidad del oídio. Los datos se guardan localmente si no hay conexión.")

# --- INICIALIZACIÓN Y NOMBRES DE ARCHIVOS ---
localS = LocalStorage()
ARCHIVO_OBSERVACIONES = 'Observaciones_Campo.xlsx'
LOCAL_STORAGE_KEY = 'observaciones_offline'

# --- FUNCIONES ---
def cargar_datos_excel():
    columnas = ['Sector', 'Fecha', 'Estado_Fenologico', 'Presencia_Oidio', 'Severidad_Oidio', 'Notas']
    if os.path.exists(ARCHIVO_OBSERVACIONES):
        return pd.read_excel(ARCHIVO_OBSERVACIONES)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = cargar_datos_excel()
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        df_final.to_excel(ARCHIVO_OBSERVACIONES, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

# --- Función para convertir un DataFrame a un archivo Excel en memoria ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    processed_data = output.getvalue()
    return processed_data

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Observación"):
    with st.form("observacion_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
            sector = st.selectbox("Seleccione el Sector", options=sectores_del_fundo)
        with col2:
            fecha = st.date_input("Fecha de Observación", datetime.now())
        estado_fenologico = st.selectbox("Estado Fenológico Principal", options=[1, 2, 3, 4, 5, 6], help="1: Brotación, 2: Crec. pámpanos, 3: Floración, 4: Cuajado, 5: Envero, 6: Maduración")
        presencia_oidio = st.radio("¿Presencia de Oídio?", ["No", "Sí"], horizontal=True)
        severidad_oidio = st.slider("Nivel de Severidad (0=Nulo, 4=Muy Severo)", 0, 4, 0)
        notas = st.text_area("Notas Adicionales")
        submitted = st.form_submit_button("💾 Guardar Localmente")
        if submitted:
            nuevo_registro = {'Sector': sector, 'Fecha': fecha.strftime("%Y-%m-%d"), 'Estado_Fenologico': estado_fenologico, 'Presencia_Oidio': presencia_oidio, 'Severidad_Oidio': severidad_oidio, 'Notas': notas}
            try:
                registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
                registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
                registros_locales.append(nuevo_registro)
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
                st.success(f"¡Registro guardado en el dispositivo! Hay {len(registros_locales)} registros pendientes.")
            except Exception as e:
                st.error(f"Error al guardar localmente: {e}")

# --- SECCIÓN DE SINCRONIZACIÓN ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")
try:
    registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
except:
    registros_pendientes = []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros guardados localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            df_pendientes = pd.DataFrame(registros_pendientes)
            exito, mensaje = guardar_datos_excel(df_pendientes)
            if exito:
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                st.success("¡Sincronización completada!")
                st.rerun()
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}. Sus datos locales están a salvo.")
else:
    st.info("✅ Todos los registros de oídio están sincronizados.")

st.divider()

# --- NUEVA SECCIÓN: HISTORIAL Y DESCARGA INDIVIDUAL ---
st.subheader("📚 Historial de Observaciones")
df_historial = cargar_datos_excel()

if not df_historial.empty:
    st.write("A continuación se muestran las últimas observaciones registradas.")
    # Mostramos un resumen de cada observación con su botón de descarga
    for index, observacion in df_historial.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.metric("Fecha", pd.to_datetime(observacion['Fecha']).strftime('%d/%m/%Y'))
            with col2:
                st.metric("Sector", observacion['Sector'])
            with col3:
                # Botón de descarga para cada observación individual
                reporte_individual = to_excel(pd.DataFrame([observacion]))
                st.download_button(
                    label="📥 Reporte",
                    data=reporte_individual,
                    file_name=f"Reporte_Oidio_{observacion['Sector']}_{pd.to_datetime(observacion['Fecha']).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{index}"
                )
else:
    st.info("Aún no se ha sincronizado ninguna observación.")

