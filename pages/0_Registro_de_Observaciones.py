import streamlit as st
import pandas as pd
import os
from datetime import datetime
import json
from streamlit_local_storage import LocalStorage

st.set_page_config(page_title="Observaciones de Oídio", page_icon="📋")
st.title("📋 Registro de Observaciones de Oídio")
st.write("Registre la presencia y severidad del oídio. Los datos se guardan localmente si no hay conexión.")

# --- INICIALIZACIÓN Y CONSTANTES ---
localS = LocalStorage()
ARCHIVO_OBSERVACIONES = 'Observaciones_Campo.xlsx'
LOCAL_STORAGE_KEY = 'observaciones_offline'

# --- FUNCIONES ---
def guardar_datos_excel(df_nuevos):
    try:
        # Define las columnas para asegurar consistencia
        columnas_esperadas = ['Sector', 'Fecha', 'Estado_Fenologico', 'Presencia_Oidio', 'Severidad_Oidio', 'Notas']
        
        if os.path.exists(ARCHIVO_OBSERVACIONES):
            df_existente = pd.read_excel(ARCHIVO_OBSERVACIONES)
        else:
            df_existente = pd.DataFrame(columns=columnas_esperadas)
            
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True)
        df_final.to_excel(ARCHIVO_OBSERVACIONES, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

# --- FORMULARIO DE REGISTRO ---
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
    
    submitted = st.form_submit_button("💾 Guardar en Dispositivo")
    if submitted:
        nuevo_registro = {
            'Sector': sector, 
            'Fecha': fecha.strftime("%Y-%m-%d"), 
            'Estado_Fenologico': estado_fenologico, 
            'Presencia_Oidio': presencia_oidio, 
            'Severidad_Oidio': severidad_oidio, 
            'Notas': notas
        }
        
        # Obtenemos los registros existentes, los actualizamos y los guardamos
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        registros_locales.append(nuevo_registro)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.success(f"¡Registro guardado en el dispositivo! Hay {len(registros_locales)} registros pendientes.")
        # Pequeño hack para forzar un refresco de la UI
        st.rerun()

st.divider()

# --- SECCIÓN DE SINCRONIZACIÓN (LÓGICA CORREGIDA) ---
st.subheader("📡 Sincronización con el Servidor")

# Leemos los datos pendientes desde el almacenamiento local
registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** registros guardados localmente pendientes de sincronizar.")
    
    if st.button("Sincronizar Ahora"):
        with st.spinner("Sincronizando..."):
            df_pendientes = pd.DataFrame(registros_pendientes)
            
            # Asegurarse que las columnas estén en el orden correcto
            columnas_esperadas = ['Sector', 'Fecha', 'Estado_Fenologico', 'Presencia_Oidio', 'Severidad_Oidio', 'Notas']
            df_pendientes = df_pendientes.reindex(columns=columnas_esperadas)

            exito, mensaje = guardar_datos_excel(df_pendientes)
            
            if exito:
                # --- !! AJUSTE CLAVE !! ---
                # 1. Limpiamos el almacenamiento local del navegador
                localS.setItem(LOCAL_STORAGE_KEY, json.dumps([])) 
                
                # 2. Mostramos el mensaje de éxito
                st.success("¡Sincronización completada!")
                
                # 3. Pequeño truco para asegurar que el estado se refresque
                st.session_state['sync_success'] = True
            else:
                st.error(f"Error al guardar en el servidor: {mensaje}. Sus datos locales están a salvo.")
else:
    st.info("✅ Todos los registros están sincronizados.")

# Forzamos el refresco final si la sincronización fue exitosa
if 'sync_success' in st.session_state and st.session_state['sync_success']:
    del st.session_state['sync_success'] # Limpiamos la bandera
    st.rerun()
