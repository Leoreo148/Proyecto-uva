mport streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Observaciones de Oídio", page_icon="📋")
st.title("📋 Registro de Observaciones de Oídio")
st.write("Registre la presencia y severidad del oídio en los diferentes sectores del fundo.")

# --- NOMBRE DEL ARCHIVO ---
ARCHIVO_OBSERVACIONES = 'Observaciones_Campo.xlsx'

# --- FUNCIONES PARA CARGAR Y GUARDAR ---
def cargar_datos():
    columnas = ['Sector', 'Fecha', 'Estado_Fenologico', 'Presencia_Oidio', 'Severidad_Oidio', 'Notas']
    if os.path.exists(ARCHIVO_OBSERVACIONES):
        return pd.read_excel(ARCHIVO_OBSERVACIONES)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_datos(df):
    df.to_excel(ARCHIVO_OBSERVACIONES, index=False)

# --- Cargar datos al inicio ---
df_observaciones = cargar_datos()

# --- FORMULARIO DE INGRESO ---
with st.form("observacion_form", clear_on_submit=True):
    
    # Fila 1: Sector y Fecha
    col1, col2 = st.columns(2)
    with col1:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector = st.selectbox("Seleccione el Sector", options=sectores_del_fundo)
    with col2:
        fecha = st.date_input("Fecha de Observación", datetime.now())

    # Fila 2: Datos de la Observación
    estado_fenologico = st.selectbox(
        "Estado Fenológico Principal",
        options=[1, 2, 3, 4, 5, 6],
        help="1: Brotación, 2: Crec. pámpanos, 3: Floración, 4: Cuajado, 5: Envero, 6: Maduración"
    )
    
    presencia_oidio = st.radio("¿Presencia de Oídio?", ["No", "Sí"], horizontal=True)
    
    severidad_oidio = st.slider(
        "Nivel de Severidad (0=Nulo, 4=Muy Severo)",
        min_value=0, max_value=4, value=0, step=1
    )
    
    notas = st.text_area("Notas Adicionales")

    submitted = st.form_submit_button("Guardar Observación")

# --- LÓGICA DE GUARDADO ---
if submitted:
    nuevo_registro = pd.DataFrame([{
        'Sector': sector,
        'Fecha': fecha.strftime("%Y-%m-%d"),
        'Estado_Fenologico': estado_fenologico,
        'Presencia_Oidio': presencia_oidio,
        'Severidad_Oidio': severidad_oidio,
        'Notas': notas
    }])
    
    df_final = pd.concat([df_observaciones, nuevo_registro], ignore_index=True)
    guardar_datos(df_final)
    
    st.success(f"¡Observación para el sector '{sector}' guardada exitosamente!")

# --- VISUALIZACIÓN DEL HISTORIAL ---
st.divider()
st.subheader("Historial de Observaciones Recientes")
if not df_observaciones.empty:
    st.dataframe(df_observaciones.tail(10).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no se han guardado observaciones.")

