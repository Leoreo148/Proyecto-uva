import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre los conteos y guárdelos localmente. Sincronice cuando tenga conexión.")

# --- Inicialización del Almacenamiento Local ---
localS = LocalStorage()

# --- Nombres de Archivos y Claves ---
ARCHIVO_FENOLOGIA = 'Evaluacion_Fenologica_Detallada.xlsx'
LOCAL_STORAGE_KEY = 'fenologia_offline'

# --- Funciones para Cargar y Guardar en Servidor (Excel) ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_FENOLOGIA):
        return pd.read_excel(ARCHIVO_FENOLOGIA)
    return None

def guardar_datos_excel(df_nuevos):
    df_existente = cargar_datos_excel()
    if df_existente is not None:
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    else:
        df_final = df_nuevos
    df_final.to_excel(ARCHIVO_FENOLOGIA, index=False)

# --- Interfaz de Registro ---
col1, col2 = st.columns(2)
with col1:
    sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
    sector_seleccionado = st.selectbox('Seleccione el Sector de Evaluación:', options=sectores_del_fundo)
with col2:
    fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())

st.divider()

columnas_fenologicas = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
plant_numbers = [f"Planta {i+1}" for i in range(25)]
df_plantilla = pd.DataFrame(0, index=plant_numbers, columns=columnas_fenologicas)

st.subheader("Tabla de Ingreso de Datos")
df_editada = st.data_editor(df_plantilla, use_container_width=True)

if st.button("💾 Guardar Localmente"):
    registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
    
    # Convertir el DataFrame editado a un diccionario para guardarlo en JSON
    df_para_guardar = df_editada.copy()
    df_para_guardar['Sector'] = sector_seleccionado
    df_para_guardar['Fecha'] = fecha_evaluacion.strftime("%Y-%m-%d")
    
    registros_locales.append(df_para_guardar.reset_index().rename(columns={'index': 'Planta'}).to_dict('records'))
    
    localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
    st.success(f"¡Evaluación guardada en el dispositivo! Hay {len(registros_locales)} evaluaciones pendientes.")

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** evaluaciones guardadas localmente pendientes de sincronizar.")
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
    st.info("✅ Todos los registros de fenología están sincronizados.")

