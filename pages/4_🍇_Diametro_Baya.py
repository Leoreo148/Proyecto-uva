import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage
from io import BytesIO
import plotly.express as px  # <--- Importante: Añadir esta línea

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

# --- Interfaz de Registro (Sin cambios) ---
with st.expander("➕ Registrar Nueva Medición"):
    # (Todo el código de esta sección se mantiene igual)
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
        registros_locales.extend(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.success(f"¡Medición guardada! Hay {len(registros_locales)} registros de plantas pendientes.")
        st.rerun()

# --- Sección de Sincronización (Sin cambios) ---
st.divider()
st.subheader("📡 Sincronización con el Servidor")
# (Todo el código de esta sección se mantiene igual)
registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []
if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones de plantas pendientes de sincronizar.")
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            df_pendientes = pd.DataFrame(registros_pendientes)
            exito, mensaje = guardar_datos_excel(df_pendientes)
            if exito:
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                st.success("¡Sincronización completada!")
                st.session_state['sync_success_baya'] = True
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}.")
if 'sync_success_baya' in st.session_state and st.session_state['sync_success_baya']:
    del st.session_state['sync_success_baya']
    st.rerun()
else:
    st.info("✅ Todas las mediciones de diámetro están sincronizadas.")

st.divider()

# --- Historial y Descarga (Sin cambios) ---
st.subheader("📚 Historial de Mediciones de Diámetro")
df_historial = None
if os.path.exists(ARCHIVO_DIAMETRO):
    df_historial = pd.read_excel(ARCHIVO_DIAMETRO)
    # (El resto del código de esta sección se mantiene igual)
    
# --- !! NUEVA SECCIÓN: GRÁFICO DE TENDENCIA !! ---
st.divider()
st.header("📈 Gráfico de Tendencia de Diámetro de Baya")

if df_historial is not None and not df_historial.empty and 'Fecha' in df_historial.columns:
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    
    # Filtro para seleccionar sectores a comparar
    todos_los_sectores = sorted(df_historial['Sector'].unique())
    sectores_a_graficar = st.multiselect(
        "Seleccione los sectores que desea comparar:",
        options=todos_los_sectores,
        default=todos_los_sectores
    )
    
    if sectores_a_graficar:
        df_filtrado = df_historial[df_historial['Sector'].isin(sectores_a_graficar)]
        
        # Calcular el promedio de diámetro por fecha y sector
        df_melted = df_filtrado.melt(
            id_vars=['Fecha', 'Sector'],
            value_vars=columnas_medicion,
            var_name='Posicion_Medicion',
            value_name='Diametro'
        )
        # Quitar mediciones no realizadas (valor 0)
        df_melted = df_melted[df_melted['Diametro'] > 0]
        
        df_tendencia = df_melted.groupby(['Fecha', 'Sector'])['Diametro'].mean().reset_index()
        
        # Crear el gráfico
        fig = px.line(
            df_tendencia,
            x='Fecha',
            y='Diametro',
            color='Sector',
            title='Evolución del Diámetro Promedio de Baya por Sector',
            markers=True,
            labels={'Fecha': 'Fecha de Medición', 'Diametro': 'Diámetro Promedio (mm)', 'Sector': 'Sector'}
        )
        fig.update_layout(legend_title_text='Sectores')
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Por favor, seleccione al menos un sector para visualizar el gráfico.")

else:
    st.info("Aún no hay datos históricos para generar un gráfico de tendencia. Por favor, registre y sincronice algunas mediciones.")
