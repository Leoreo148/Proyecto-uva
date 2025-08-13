import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Observaciones de Oídio", page_icon="📋")
st.title("📋 Registro de Observaciones de Oídio")
st.write("Registre la presencia y severidad del oídio. Los datos se guardan localmente si no hay conexión.")

# --- INICIALIZACIÓN DEL ALMACENAMIENTO LOCAL ---
localS = LocalStorage()

# --- NOMBRES DE ARCHIVOS Y CLAVES ---
ARCHIVO_OBSERVACIONES = 'Observaciones_Campo.xlsx'
LOCAL_STORAGE_KEY = 'observaciones_offline'

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS EN EL SERVIDOR (EXCEL) ---
def cargar_datos_excel():
    columnas = ['Sector', 'Fecha', 'Estado_Fenologico', 'Presencia_Oidio', 'Severidad_Oidio', 'Notas']
    if os.path.exists(ARCHIVO_OBSERVACIONES):
        return pd.read_excel(ARCHIVO_OBSERVACIONES)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_datos_excel(df_nuevos):
    df_existente = cargar_datos_excel()
    df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
    df_final.to_excel(ARCHIVO_OBSERVACIONES, index=False)

# --- FORMULARIO DE INGRESO ---
with st.form("observacion_form"):
    st.subheader("Nuevo Registro")
    col1, col2 = st.columns(2)
    with col1:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector = st.selectbox("Seleccione el Sector", options=sectores_del_fundo)
    with col2:
        fecha = st.date_input("Fecha de Observación", datetime.now())

    estado_fenologico = st.selectbox("Estado Fenológico Principal", options=[1, 2, 3, 4, 5, 6], help="1: Brotación, 2: Crec. pámpanos, 3: Floración, 4: Cuajado, 5: Envero, 6: Maduración")
    presencia_oidio = st.radio("¿Presencia de Oídio?", ["No", "Sí"], horizontal=True)
    severidad_oidio = st.slider("Nivel de Severidad (0=Nulo, 4=Muy Severo)", min_value=0, max_value=4, value=0, step=1)
    notas = st.text_area("Notas Adicionales")

    submitted = st.form_submit_button("💾 Guardar Localmente")

    if submitted:
        # 1. Obtener registros guardados localmente
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        
        # 2. Crear el nuevo registro
        nuevo_registro = {
            'Sector': sector,
            'Fecha': fecha.strftime("%Y-%m-%d"),
            'Estado_Fenologico': estado_fenologico,
            'Presencia_Oidio': presencia_oidio,
            'Severidad_Oidio': severidad_oidio,
            'Notas': notas
        }
        
        # 3. Añadirlo a la lista y guardarlo de nuevo en el almacenamiento local
        registros_locales.append(nuevo_registro)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        
        st.success(f"¡Registro guardado en el dispositivo! Hay {len(registros_locales)} registros pendientes de sincronizar.")

st.divider()

# --- SECCIÓN DE SINCRONIZACIÓN ---
st.subheader("📡 Sincronización con el Servidor")

# Obtener y mostrar cuántos registros hay pendientes
registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros guardados en este dispositivo que no se han subido al servidor.")
    
    if st.button("Sincronizar Ahora"):
        try:
            # Convertir la lista de registros a un DataFrame
            df_pendientes = pd.DataFrame(registros_pendientes)
            
            # Guardar los datos en el archivo Excel del servidor
            guardar_datos_excel(df_pendientes)
            
            # Si se guardó exitosamente, limpiar el almacenamiento local
            localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
            
            st.success("¡Sincronización completada! Todos los registros han sido subidos.")
            st.rerun()
        except Exception as e:
            st.error(f"Error de conexión. No se pudo sincronizar. Inténtelo más tarde. Detalles: {e}")
            
    with st.expander("Ver registros pendientes"):
        st.dataframe(pd.DataFrame(registros_pendientes))
else:
    st.info("✅ Todos los registros están sincronizados con el servidor.")

