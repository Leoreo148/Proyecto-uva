import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="Diámetro de Baya", page_icon="🍇", layout="wide")
st.title("🍇 Medición de Diámetro de Baya (Detallado)")
st.write("Registre el diámetro (mm) de 3 bayas (superior, medio, inferior) para 2 racimos por cada una de las 25 plantas.")

localS = LocalStorage()
ARCHIVO_DIAMETRO = 'Registro_Diametro_Baya_Detallado.xlsx'
LOCAL_STORAGE_KEY = 'diametro_baya_offline_v2'

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = None
        if os.path.exists(ARCHIVO_DIAMETRO):
            df_existente = pd.read_excel(ARCHIVO_DIAMETRO)
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_DIAMETRO, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

col1, col2 = st.columns(2)
with col1:
    sectores_baya = ['W1', 'W2', 'W3', 'J1', 'J2', 'J3', 'K1', 'K2', 'K3']
    sector_seleccionado = st.selectbox('Seleccione el Sector de Medición:', options=sectores_baya)
with col2:
    fecha_medicion = st.date_input("Fecha de Medición", datetime.now())
st.divider()
st.subheader("Tabla de Ingreso de Diámetros (mm)")
plant_numbers = [f"Planta {i+1}" for i in range(25)]
columnas_medicion = ["Racimo 1 - Superior", "Racimo 1 - Medio", "Racimo 1 - Inferior", "Racimo 2 - Superior", "Racimo 2 - Medio", "Racimo 2 - Inferior"]
df_plantilla = pd.DataFrame(0.0, index=plant_numbers, columns=columnas_medicion)
df_editada = st.data_editor(df_plantilla, use_container_width=True)
if st.button("💾 Guardar Medición Localmente"):
    valores_medidos = df_editada.to_numpy().flatten()
    valores_no_cero = valores_medidos[valores_medidos > 0]
    if len(valores_no_cero) > 0:
        promedio_general = valores_no_cero.mean()
        st.success(f"Promedio General: **{promedio_general:.2f} mm**")
    df_para_guardar = df_editada.copy()
    df_para_guardar['Sector'] = sector_seleccionado
    df_para_guardar['Fecha'] = fecha_medicion.strftime("%Y-%m-%d")
    registros_json = df_para_guardar.reset_index().rename(columns={'index': 'Planta'}).to_dict('records')
    try:
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        registros_locales.append(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.info(f"¡Medición guardada en el dispositivo! Hay {len(registros_locales)} mediciones pendientes.")
    except Exception as e:
        st.error(f"Error al guardar localmente: {e}")

st.divider()
st.subheader("📡 Sincronización con el Servidor")
try:
    registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
except:
    registros_pendientes = []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones completas guardadas localmente pendientes de sincronizar.")
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
    st.info("✅ Todas las mediciones de diámetro están sincronizadas.")
