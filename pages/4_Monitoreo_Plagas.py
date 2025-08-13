import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="Monitoreo de Plagas", page_icon="🪰", layout="wide")
st.title("🪰 Monitoreo de Mosca de la Fruta por Especie")
st.write("Registre las capturas y guárdelas localmente. Sincronice cuando tenga conexión.")

localS = LocalStorage()
ARCHIVO_PLAGAS = 'Monitoreo_Plagas_Detallado.xlsx'
LOCAL_STORAGE_KEY = 'plagas_offline'

def cargar_datos_excel():
    columnas = ["Fecha", "Sector", "Codigo_Trampa", "A_fraterculus", "A_distinta", "C_capitata", "Total_Capturas"]
    if os.path.exists(ARCHIVO_PLAGAS):
        return pd.read_excel(ARCHIVO_PLAGAS)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_datos_excel(df_nuevos):
    df_existente = cargar_datos_excel()
    df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    df_final.to_excel(ARCHIVO_PLAGAS, index=False, engine='openpyxl')

with st.form("monitoreo_plagas_form"):
    st.subheader("Nuevo Registro de Trampa")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_conteo = st.date_input("Fecha de Conteo", datetime.now())
    with col2:
        sectores_trampas = ['Cerco 1', 'Cerco 2', 'Medio 1', 'Medio 2', 'Medio 3', 'Granado', 'Palto', 'Fundo Aledaño 1', 'Fundo Aledaño 2']
        sector_seleccionado = st.selectbox("Sector de la Trampa", options=sectores_trampas)
    with col3:
        codigo_trampa = st.text_input("Código de Trampa", placeholder="Ej: T1, 105...")
    st.subheader("Conteo de Capturas por Especie")
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        capturas_fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1)
    with col_b:
        capturas_distinta = st.number_input("Anastrepha distinta", min_value=0, step=1)
    with col_c:
        capturas_capitata = st.number_input("Ceratitis capitata", min_value=0, step=1)
    submitted = st.form_submit_button("💾 Guardar Localmente")
    if submitted:
        if codigo_trampa:
            total_capturas = capturas_fraterculus + capturas_distinta + capturas_capitata
            nuevo_registro = {"Fecha": fecha_conteo.strftime("%Y-%m-%d"), "Sector": sector_seleccionado, "Codigo_Trampa": codigo_trampa, "A_fraterculus": capturas_fraterculus, "A_distinta": capturas_distinta, "C_capitata": capturas_capitata, "Total_Capturas": total_capturas}
            try:
                registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
                registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
                registros_locales.append(nuevo_registro)
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
                st.success(f"¡Conteo guardado en el dispositivo! Hay {len(registros_locales)} registros pendientes.")
            except Exception as e:
                st.error(f"Error al guardar localmente. Refresque la página. Detalle: {e}")
        else:
            st.warning("Por favor, ingrese un código para la trampa.")

st.divider()
st.subheader("📡 Sincronización con el Servidor")
try:
    registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
    registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
except:
    registros_pendientes = []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** conteos de plagas guardados localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            try:
                df_pendientes = pd.DataFrame(registros_pendientes)
                guardar_datos_excel(df_pendientes)
                if os.path.exists(ARCHIVO_PLAGAS):
                    localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                    st.success("¡Sincronización completada!")
                    st.rerun()
                else:
                    st.error("Error: No se pudo guardar el archivo en el servidor. Sus datos locales están a salvo.")
            except Exception as e:
                st.error(f"Error de conexión o escritura. Sus datos locales están a salvo. Detalles: {e}")
else:
    st.info("✅ Todos los registros de plagas están sincronizados.")
