import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Monitoreo de Mosca", page_icon="🪰", layout="wide")
st.title("🪰 Monitoreo de Mosca de la Fruta")
st.write("Inicie una sesión de monitoreo para un sector y registre las capturas de múltiples trampas.")

# --- INICIALIZACIÓN Y NOMBRES DE ARCHIVOS ---
localS = LocalStorage()
ARCHIVO_MOSCA = 'Monitoreo_Mosca_Fruta.xlsx'
LOCAL_STORAGE_KEY = 'mosca_fruta_offline'

# --- FUNCIONES ---
def guardar_datos_excel(df_nuevos):
    try:
        df_existente = pd.DataFrame()
        if os.path.exists(ARCHIVO_MOSCA):
            df_existente = pd.read_excel(ARCHIVO_MOSCA)
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        df_final.to_excel(ARCHIVO_MOSCA, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def cargar_datos_excel():
    if os.path.exists(ARCHIVO_MOSCA):
        return pd.read_excel(ARCHIVO_MOSCA)
    return None

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- INICIALIZAR MEMORIA DE SESIÓN ---
if 'sesion_monitoreo' not in st.session_state:
    st.session_state.sesion_monitoreo = []
if 'sector_actual' not in st.session_state:
    st.session_state.sector_actual = ""

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Iniciar y Registrar Sesión de Monitoreo"):
    st.subheader("1. Iniciar Sesión")
    col1, col2 = st.columns(2)
    with col1:
        sector_manual = st.text_input("Escriba el nombre del Sector a monitorear:", placeholder="Ej: Palto, Fundo Aledaño, Cerco 1")
    with col2:
        fecha_conteo = st.date_input("Fecha de Conteo", datetime.now())

    if sector_manual:
        st.session_state.sector_actual = sector_manual

    if st.session_state.sector_actual:
        st.subheader(f"2. Registrar Trampas para el Sector: **{st.session_state.sector_actual}**")
        with st.form("nueva_trampa_form"):
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                numero_trampa = st.text_input("Número o Código de Trampa", placeholder="Ej: T1, 105")
            with col_t2:
                tipo_trampa = st.selectbox("Tipo de Trampa", ["Levadura", "Trimedlure", "Panel"])
            st.write("**Conteo de Capturas por Especie:**")
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                capturas_capitata = st.number_input("Ceratitis capitata", min_value=0, step=1)
            with col_b:
                capturas_fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1)
            with col_c:
                capturas_distinta = st.number_input("Anastrepha distinta", min_value=0, step=1)
            submitted_trampa = st.form_submit_button("➕ Añadir Trampa a la Sesión")
            if submitted_trampa and numero_trampa:
                st.session_state.sesion_monitoreo.append({"Fecha": fecha_conteo.strftime("%Y-%m-%d"), "Sector": st.session_state.sector_actual, "Numero_Trampa": numero_trampa, "Tipo_Trampa": tipo_trampa, "Ceratitis_capitata": capturas_capitata, "Anastrepha_fraterculus": capturas_fraterculus, "Anastrepha_distinta": capturas_distinta})
            elif submitted_trampa:
                st.warning("Por favor, ingrese el número de la trampa.")

# --- RESUMEN DE LA SESIÓN Y GUARDADO ---
if st.session_state.sesion_monitoreo:
    st.divider()
    st.subheader("Resumen de la Sesión Actual")
    st.dataframe(pd.DataFrame(st.session_state.sesion_monitoreo), use_container_width=True)
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if st.button("💾 Guardar Sesión Localmente"):
            try:
                registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
                registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
                registros_locales.extend(st.session_state.sesion_monitoreo)
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
                st.success("¡Sesión guardada en el dispositivo!")
                st.session_state.sesion_monitoreo = []
                st.session_state.sector_actual = ""
            except Exception as e:
                st.error(f"Error al guardar localmente: {e}")
    with col_g2:
        if st.button("❌ Limpiar Sesión Actual"):
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun()

# --- SECCIÓN DE SINCRONIZACIÓN ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")
try:
    registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
except:
    registros_pendientes = []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros de trampas guardados localmente pendientes de sincronizar.")
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
    st.info("✅ Todos los registros de monitoreo están sincronizados.")

st.divider()

# --- NUEVA SECCIÓN: HISTORIAL Y DESCARGA ---
st.subheader("📚 Historial de Sesiones de Monitoreo")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    sesiones = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
    st.write("A continuación se muestra un resumen de las últimas sesiones de monitoreo realizadas.")
    
    for index, sesion in sesiones.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            df_sesion_actual = df_historial[(df_historial['Fecha'] == sesion['Fecha']) & (df_historial['Sector'] == sesion['Sector'])]
            
            col1, col2, col3, col4 = st.columns([2, 2, 1, 1])
            col1.metric("Fecha", pd.to_datetime(sesion['Fecha']).strftime('%d/%m/%Y'))
            col2.metric("Sector", sesion['Sector'])
            col3.metric("N° de Trampas", str(sesion['counts']))

            with col4:
                st.write("")
                reporte_individual = to_excel(df_sesion_actual)
                st.download_button(
                    label="📥 Descargar Detalle",
                    data=reporte_individual,
                    file_name=f"Reporte_Mosca_{sesion['Sector']}_{pd.to_datetime(sesion['Fecha']).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_mosca_{sesion['Fecha']}_{sesion['Sector']}"
                )
else:
    st.info("Aún no se ha sincronizado ninguna sesión de monitoreo.")
