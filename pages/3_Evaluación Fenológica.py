import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre los conteos y guárdelos localmente. Sincronice cuando tenga conexión.")

localS = LocalStorage()
ARCHIVO_FENOLOGIA = 'Evaluacion_Fenologica_Detallada.xlsx'
LOCAL_STORAGE_KEY = 'fenologia_offline'

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = None
        if os.path.exists(ARCHIVO_FENOLOGIA):
            df_existente = pd.read_excel(ARCHIVO_FENOLOGIA)
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_FENOLOGIA, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

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
        st.error(f"Error al guardar localmente. Refresque la página. Detalle: {e}")

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
