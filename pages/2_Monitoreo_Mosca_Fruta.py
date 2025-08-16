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
        if os.path.exists(ARCHIVO_MOSCA):
            df_existente = pd.read_excel(ARCHIVO_MOSCA)
            df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        else:
            df_final = df_nuevos
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
    # (Esta sección no cambia)
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
        with st.form("nueva_trampa_form", clear_on_submit=True):
            # ... (resto del formulario no cambia)
            numero_trampa = st.text_input("Número o Código de Trampa", placeholder="Ej: T1, 105")
            capturas_capitata = st.number_input("Ceratitis capitata", min_value=0, step=1, key='c1')
            capturas_fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1, key='c2')
            capturas_distinta = st.number_input("Anastrepha distinta", min_value=0, step=1, key='c3')
            
            submitted_trampa = st.form_submit_button("➕ Añadir Trampa a la Sesión")
            if submitted_trampa and numero_trampa:
                st.session_state.sesion_monitoreo.append({
                    "Fecha": fecha_conteo.strftime("%Y-%m-%d"), 
                    "Sector": st.session_state.sector_actual, 
                    "Numero_Trampa": numero_trampa, 
                    "Tipo_Trampa": "N/A", # Asumiendo que tipo_trampa se define en el form
                    "Ceratitis_capitata": capturas_capitata, 
                    "Anastrepha_fraterculus": capturas_fraterculus, 
                    "Anastrepha_distinta": capturas_distinta
                })
            elif submitted_trampa:
                st.warning("Por favor, ingrese el número de la trampa.")


# --- RESUMEN DE LA SESIÓN Y GUARDADO ---
if st.session_state.sesion_monitoreo:
    st.divider()
    st.subheader("Resumen de la Sesión Actual")
    st.dataframe(pd.DataFrame(st.session_state.sesion_monitoreo), use_container_width=True)
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        if st.button("💾 Guardar Sesión en Dispositivo"):
            registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
            registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
            registros_locales.extend(st.session_state.sesion_monitoreo)
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
            st.success(f"¡Sesión con {len(st.session_state.sesion_monitoreo)} registros guardada en el dispositivo!")
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun() # Refrescar para limpiar la sesión
    with col_g2:
        if st.button("❌ Limpiar Sesión Actual"):
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun()

# --- SECCIÓN DE SINCRONIZACIÓN (LÓGICA CORREGIDA) ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros de trampas guardados localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            df_pendientes = pd.DataFrame(registros_pendientes)
            exito, mensaje = guardar_datos_excel(df_pendientes)
            
            if exito:
                # --- !! AJUSTE CLAVE !! ---
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                st.success("¡Sincronización completada!")
                st.session_state['sync_success_mosca'] = True
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}. Sus datos locales están a salvo.")
else:
    st.info("✅ Todos los registros de monitoreo están sincronizados.")

if 'sync_success_mosca' in st.session_state and st.session_state['sync_success_mosca']:
    del st.session_state['sync_success_mosca']
    st.rerun()

# --- HISTORIAL Y DESCARGA ---
# (Esta sección no cambia)
st.divider()
st.subheader("📚 Historial de Sesiones de Monitoreo")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    # (Lógica de visualización del historial)
    pass
else:
    st.info("Aún no se ha sincronizado ninguna sesión de monitoreo.")
