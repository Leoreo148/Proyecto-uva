import streamlit as st
import pandas as pd
import joblib

# --- 1. CONFIGURACIÓN Y MEMORIA DE SESIÓN ---
st.set_page_config(
    page_title="Panel del Fundo",
    page_icon="🍇",
    layout="wide"
)

# Se inicializa la memoria de sesión UNA SOLA VEZ, al principio de todo.
# Si el usuario no ha seleccionado nada, el valor por defecto será 'General'.
if 'sector' not in st.session_state:
    st.session_state.sector = 'General'

# --- 2. FUNCIONES AUXILIARES ---
# (Estas funciones no necesitan cambios)
def cargar_modelo():
    """Carga el modelo de Machine Learning desde el archivo."""
    try:
        return joblib.load('modelo_oidio.joblib')
    except FileNotFoundError:
        st.error("Error Crítico: No se encontró el archivo del modelo 'modelo_oidio.joblib'.")
        st.stop()

def cargar_inventario():
    """Carga el inventario de productos desde el archivo Excel."""
    try:
        return pd.read_excel("Inventario_Productos.xlsx")
    except FileNotFoundError:
        return pd.DataFrame(columns=['Producto', 'Tipo_Accion', 'Modo_Accion'])

def obtener_recomendacion(prediccion, inventario_df):
    """Genera una recomendación textual basada en la predicción."""
    if prediccion == 0:
        return "🟢 **RIESGO BAJO:** No se requiere acción inmediata. Continuar con el monitoreo regular del campo."
    elif prediccion == 1:
        recomendacion = "🟡 **RIESGO MEDIO:** Condiciones favorables para una infección inicial.\n\n**Acción Sugerida:** Aplicación **Preventiva**."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Preventivo', 'Curativo'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos de tu inventario:**\n- " + "\n- ".join(productos_sugeridos['Producto'].tolist())
        return recomendacion
    else: # prediccion >= 2
        recomendacion = "🔴 **RIESGO ALTO:** Condiciones óptimas para la propagación.\n\n**Acción Sugerida:** Aplicación **Curativa** o **Erradicante**."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Curativo', 'Erradicante'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos de tu inventario:**\n- " + "\n- ".join(productos_sugeridos['Producto'].tolist())
        else:
            recomendacion += "\n\n*No se encontraron productos curativos/erradicantes en tu inventario.*"
        return recomendacion

# --- 3. BARRA LATERAL (SIDEBAR) ---
st.sidebar.header('Configuración de Predicción')

# Lista de sectores
sectores_del_fundo = ['W1', 'W2', 'W3', 'K1', 'K2', 'K3', 'General']

# Este selectbox actualiza st.session_state.sector automáticamente gracias a la 'key'
st.sidebar.selectbox(
    'Seleccione el Sector de Trabajo:',
    options=sectores_del_fundo,
    key='sector'
)
st.sidebar.success(f"Sector en memoria: **{st.session_state.sector}**")

# Inputs para los parámetros del clima
st.sidebar.divider()
st.sidebar.subheader('Parámetros del Clima')
temp_max = st.sidebar.number_input('Temperatura Máxima (°C)', 10.0, 40.0, 27.0)
temp_min = st.sidebar.number_input('Temperatura Mínima (°C)', 0.0, 30.0, 19.0)
temp_prom = st.sidebar.number_input('Temperatura Promedio (°C)', 5.0, 35.0, 23.0)
hr_prom = st.sidebar.number_input('Humedad Relativa Promedio (%)', 30.0, 100.0, 89.0)
precipitacion = st.sidebar.number_input('Precipitación (mm)', 0.0, 50.0, 0.0)
viento = st.sidebar.number_input('Velocidad del Viento (km/h)', 0.0, 50.0, 14.0)
sol = st.sidebar.number_input('Horas de Sol', 0.0, 14.0, 8.0)


# --- 4. PÁGINA PRINCIPAL ---
st.title('🍇 Panel de Control del Fundo')
# El header ahora lee directamente de la memoria de sesión, que ya está actualizada
st.header(f"Predicción de Riesgo para el Sector: {st.session_state.sector}")

# Cargar el modelo
modelo = cargar_modelo()

# Crear el DataFrame de entrada
input_data = {
    'Temp_Max_C': temp_max, 'Temp_Min_C': temp_min, 'Temp_Prom_C': temp_prom,
    'HR_Prom_Porc': hr_prom, 'Precipitacion_mm': precipitacion,
    'Vel_Viento_Prom_kmh': viento, 'Horas_Sol': sol
}
input_df = pd.DataFrame(input_data, index=[0])

st.subheader('Parámetros Ingresados:')
st.write(input_df)

if st.button('Predecir Riesgo y Obtener Recomendación'):
    inventario_df = cargar_inventario()
    if inventario_df.empty:
        st.warning("⚠️ Tu inventario de productos está vacío. Las recomendaciones serán genéricas.")

    prediction = modelo.predict(input_df)
    recomendacion_texto = obtener_recomendacion(prediction[0], inventario_df)

    st.subheader('Diagnóstico y Recomendación')
    st.info(recomendacion_texto)
