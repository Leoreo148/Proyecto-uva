import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

# --- Configuración de la Página ---
st.set_page_config(page_title="Diámetro de Baya", page_icon="🍇", layout="wide")
st.title("🍇 Medición de Diámetro de Baya")
st.write("Registre el diámetro (en mm) de dos bayas por racimo para 25 racimos.")

# --- Inicialización del Almacenamiento Local ---
localS = LocalStorage()

# --- Nombres de Archivos y Claves ---
ARCHIVO_DIAMETRO = 'Registro_Diametro_Baya.xlsx'
LOCAL_STORAGE_KEY = 'diametro_baya_offline'

# --- Funciones para Cargar y Guardar en Servidor (Excel) ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_DIAMETRO):
        return pd.read_excel(ARCHIVO_DIAMETRO)
    return None

def guardar_datos_excel(df_nuevos):
    df_existente = cargar_datos_excel()
    if df_existente is not None:
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    else:
        df_final = df_nuevos
    df_final.to_excel(ARCHIVO_DIAMETRO, index=False)

# --- Interfaz de Registro ---
col1, col2 = st.columns(2)
with col1:
    # Lista de sectores específica para esta medición
    sectores_baya = ['W1', 'W2', 'W3', 'J1', 'J2', 'J3', 'K1', 'K2', 'K3']
    sector_seleccionado = st.selectbox('Seleccione el Sector de Medición:', options=sectores_baya)
with col2:
    fecha_medicion = st.date_input("Fecha de Medición", datetime.now())

st.divider()

# --- Tabla Editable para Ingreso de Datos ---
st.subheader("Tabla de Ingreso de Diámetros (mm)")

# Creamos una plantilla para las 25 mediciones
racimo_numbers = [f"Racimo {i+1}" for i in range(25)]
df_plantilla = pd.DataFrame(0.0, index=racimo_numbers, columns=["Baya 1 (mm)", "Baya 2 (mm)"])

# Usamos st.data_editor para una interfaz tipo Excel
df_editada = st.data_editor(df_plantilla, use_container_width=True)

if st.button("💾 Guardar Medición Localmente"):
    # 1. Calcular el promedio
    promedio_baya1 = df_editada["Baya 1 (mm)"].mean()
    promedio_baya2 = df_editada["Baya 2 (mm)"].mean()
    promedio_general = (promedio_baya1 + promedio_baya2) / 2
    
    st.success(f"Promedio General de Diámetro: **{promedio_general:.2f} mm**")

    # 2. Preparar los datos para guardarlos
    df_para_guardar = df_editada.copy()
    df_para_guardar['Sector'] = sector_seleccionado
    df_para_guardar['Fecha'] = fecha_medicion.strftime("%Y-%m-%d")
    
    # Convertir a formato JSON para el almacenamiento local
    registros_json = df_para_guardar.reset_index().rename(columns={'index': 'Racimo'}).to_dict('records')

    # 3. Guardar en el almacenamiento local del navegador
    registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
    registros_locales.append(registros_json) # Guardamos el grupo completo de 25 mediciones
    
    localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
    st.info(f"¡Medición guardada en el dispositivo! Hay {len(registros_locales)} mediciones pendientes de sincronizar.")

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones completas guardadas localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        try:
            # Aplanar la lista de listas de diccionarios
            flat_list = [item for sublist in registros_pendientes for item in sublist]
            df_pendientes = pd.DataFrame(flat_list)
            guardar_datos_excel(df_pendientes)
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
            st.success("¡Sincronización completada!")
            st.rerun()
        except Exception as e:
            st.error(f"Error de conexión. Inténtelo más tarde. Detalles: {e}")
else:
    st.info("✅ Todas las mediciones de diámetro están sincronizadas.")

