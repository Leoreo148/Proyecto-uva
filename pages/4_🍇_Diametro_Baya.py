import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO

# --- Configuración de la Página ---
st.set_page_config(page_title="Diámetro de Baya", page_icon="🍇", layout="wide")
st.title("🍇 Medición de Diámetro de Baya")
st.write("Registre el diámetro (mm) de 3 bayas (superior, medio, inferior) para 2 racimos por cada una de las 25 plantas.")

# --- Inicialización y Constantes ---
localS = LocalStorage()
ARCHIVO_DIAMETRO = 'Registro_Diametro_Baya_Detallado.xlsx'
LOCAL_STORAGE_KEY = 'diametro_baya_offline_v2'
columnas_medicion = ["Racimo 1 - Superior", "Racimo 1 - Medio", "Racimo 1 - Inferior", "Racimo 2 - Superior", "Racimo 2 - Medio", "Racimo 2 - Inferior"]

# --- Funciones ---
def guardar_datos_excel(df_nuevos):
    try:
        if os.path.exists(ARCHIVO_DIAMETRO):
            df_existente = pd.read_excel(ARCHIVO_DIAMETRO)
            df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        else:
            df_final = df_nuevos
        df_final.to_excel(ARCHIVO_DIAMETRO, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Diametro')
    return output.getvalue()

# --- Interfaz de Registro ---
with st.expander("➕ Registrar Nueva Medición"):
    col1, col2 = st.columns(2)
    with col1:
        sectores_baya = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Medición:', options=sectores_baya)
    with col2:
        fecha_medicion = st.date_input("Fecha de Medición", datetime.now())

    st.subheader("Tabla de Ingreso de Diámetros (mm)")
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(0.0, index=plant_numbers, columns=columnas_medicion)
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key="editor_baya")

    if st.button("💾 Guardar Medición en Dispositivo"):
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_medicion.strftime("%Y-%m-%d")
        registros_json = df_para_guardar.reset_index().rename(columns={'index': 'Planta'}).to_dict('records')
        
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        # --- !! AJUSTE CLAVE 1: Usar extend en lugar de append !! ---
        registros_locales.extend(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.success(f"¡Medición guardada! Hay {len(registros_locales)} registros de plantas pendientes.")
        st.rerun()

# --- Sección de Sincronización (Lógica Mejorada) ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")

registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones de plantas guardadas localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            # --- !! AJUSTE CLAVE 2: No se necesita aplanar la lista !! ---
            df_pendientes = pd.DataFrame(registros_pendientes)
            exito, mensaje = guardar_datos_excel(df_pendientes)
            
            if exito:
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                st.success("¡Sincronización completada!")
                # Usamos una clave única para este módulo en el session_state
                st.session_state['sync_success_baya'] = True
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}. Sus datos locales están a salvo.")
else:
    st.info("✅ Todas las mediciones de diámetro están sincronizadas.")

# Forzamos el refresco final si la sincronización fue exitosa
if 'sync_success_baya' in st.session_state and st.session_state['sync_success_baya']:
    del st.session_state['sync_success_baya']
    st.rerun()

st.divider()

# --- Historial y Descarga ---
st.subheader("📚 Historial de Mediciones de Diámetro")
if os.path.exists(ARCHIVO_DIAMETRO):
    df_historial = pd.read_excel(ARCHIVO_DIAMETRO)
    if not df_historial.empty and 'Fecha' in df_historial.columns and 'Sector' in df_historial.columns:
        sesiones = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
        st.write("A continuación se muestra un resumen de las últimas mediciones realizadas.")
        
        for index, sesion in sesiones.sort_values(by='Fecha', ascending=False).head(10).iterrows():
            with st.container(border=True):
                df_sesion_actual = df_historial[(df_historial['Fecha'] == sesion['Fecha']) & (df_historial['Sector'] == sesion['Sector'])]
                
                valores_medidos = df_sesion_actual[columnas_medicion].to_numpy().flatten()
                valores_no_cero = valores_medidos[valores_medidos > 0]
                promedio_sesion = valores_no_cero.mean() if len(valores_no_cero) > 0 else 0
                
                col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
                col1.metric("Fecha", pd.to_datetime(sesion['Fecha']).strftime('%d/%m/%Y'))
                col2.metric("Sector", sesion['Sector'])
                col3.metric("Promedio General (mm)", f"{promedio_sesion:.2f}")

                with col4:
                    st.write("")
                    reporte_individual = to_excel(df_sesion_actual)
                    st.download_button(
                        label="📥 Descargar Detalle",
                        data=reporte_individual,
                        file_name=f"Reporte_Diametro_{sesion['Sector']}_{pd.to_datetime(sesion['Fecha']).strftime('%Y%m%d')}.xlsx",
                        key=f"download_diametro_{sesion['Fecha']}_{sesion['Sector']}"
                    )
else:
    st.info("Aún no se ha sincronizado ninguna medición de diámetro de baya.")
