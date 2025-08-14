import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

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

# --- INICIALIZAR MEMORIA DE SESIÓN PARA LA SESIÓN ACTUAL ---
if 'sesion_monitoreo' not in st.session_state:
    st.session_state.sesion_monitoreo = []
if 'sector_actual' not in st.session_state:
    st.session_state.sector_actual = ""

# --- SECCIÓN 1: INICIAR SESIÓN DE MONITOREO ---
st.subheader("1. Iniciar Sesión de Monitoreo")
col1, col2 = st.columns(2)
with col1:
    # El usuario escribe el nombre del sector manualmente
    sector_manual = st.text_input("Escriba el nombre del Sector a monitorear:", placeholder="Ej: Palto, Fundo Aledaño, Cerco 1")
with col2:
    fecha_conteo = st.date_input("Fecha de Conteo", datetime.now())

if sector_manual:
    st.session_state.sector_actual = sector_manual

# --- SECCIÓN 2: REGISTRO DE TRAMPAS ---
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

        # Botón para añadir la trampa a la sesión actual
        submitted_trampa = st.form_submit_button("➕ Añadir Trampa a la Sesión")
        if submitted_trampa and numero_trampa:
            st.session_state.sesion_monitoreo.append({
                "Fecha": fecha_conteo.strftime("%Y-%m-%d"),
                "Sector": st.session_state.sector_actual,
                "Numero_Trampa": numero_trampa,
                "Tipo_Trampa": tipo_trampa,
                "Ceratitis_capitata": capturas_capitata,
                "Anastrepha_fraterculus": capturas_fraterculus,
                "Anastrepha_distinta": capturas_distinta
            })
        elif submitted_trampa:
            st.warning("Por favor, ingrese el número de la trampa.")

# --- SECCIÓN 3: RESUMEN DE LA SESIÓN Y GUARDADO ---
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
                # Añadimos todos los registros de la sesión actual
                registros_locales.extend(st.session_state.sesion_monitoreo)
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
                st.success("¡Sesión guardada en el dispositivo! Puede iniciar una nueva o sincronizar.")
                # Limpiamos la sesión actual para empezar de nuevo
                st.session_state.sesion_monitoreo = []
                st.session_state.sector_actual = ""
            except Exception as e:
                st.error(f"Error al guardar localmente: {e}")
    with col_g2:
        if st.button("❌ Limpiar Sesión Actual"):
            st.session_state.sesion_monitoreo = []
            st.session_state.sector_actual = ""
            st.rerun()

# --- SECCIÓN 4: SINCRONIZACIÓN ---
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
