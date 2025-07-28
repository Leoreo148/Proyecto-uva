import streamlit as st
import pandas as pd
import joblib

# --- 1. INICIALIZACIÓN Y CONFIGURACIÓN ---

# Inicializamos la memoria de sesión para que 'sector' siempre tenga un valor
if 'sector' not in st.session_state:
    st.session_state.sector = 'General' # Le damos un valor por defecto

# --- 2. DEFINICIÓN DE FUNCIONES ---

def cargar_modelo():
    """Carga el modelo de Machine Learning desde el archivo."""
    try:
        modelo = joblib.load('modelo_oidio.joblib')
        return modelo
    except FileNotFoundError:
        st.error("Error Crítico: No se encontró el archivo del modelo 'modelo_oidio.joblib'. La aplicación no puede funcionar.")
        st.stop()

def cargar_inventario():
    """Carga el inventario de productos desde el archivo Excel."""
    try:
        return pd.read_excel("Inventario_Productos.xlsx")
    except FileNotFoundError:
        return pd.DataFrame(columns=['Producto', 'Tipo_Accion', 'Modo_Accion'])

def obtener_recomendacion(prediccion, inventario_df):
    """Genera una recomendación basada en la predicción y el inventario."""
    if prediccion == 0:
        return "🟢 **RIESGO BAJO:** No se requiere acción inmediata. Continuar con el monitoreo regular del campo."

    elif prediccion == 1:
        recomendacion = "🟡 **RIESGO MEDIO:** Condiciones favorables para una infección inicial.\n\n**Acción Sugerida:** Aplicación **Preventiva**."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Preventivo', 'Curativo'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos de tu inventario:**\n- " + "\n- ".join(productos_sugeridos['Producto'].tolist())
        return recomendacion

    elif prediccion >= 2:
        recomendacion = "🔴 **RIESGO ALTO:** Condiciones óptimas para la propagación de la enfermedad.\n\n**Acción Sugerida:** Aplicación **Curativa** o **Erradicante**."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Curativo', 'Erradicante'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos de tu inventario:**\n- " + "\n- ".join(productos_sugeridos['Producto'].tolist())
        else:
            recomendacion += "\n\n*No se encontraron productos curativos/erradicantes en tu inventario.*"
        return recomendacion

def construir_sidebar():
    """Crea y gestiona todos los elementos de la barra lateral."""
    st.sidebar.header('Selección de Sector')
    sectores_del_fundo = ['W1', 'W2', 'W3', 'K1', 'K2', 'K3', 'General']
    
    # Usamos st.session_state.sector para que la selección se recuerde entre páginas
    st.sidebar.selectbox(
        'Seleccione el Sector de Trabajo:',
        options=sectores_del_fundo,
        key='sector' # La clave 'sector' es la que guarda el valor en la memoria
    )
    st.sidebar.success(f"Sector seleccionado: **{st.session_state.sector}**")
    
    st.sidebar.header('Parámetros del Clima para Mañana')
    temp_max = st.sidebar.number_input('Temperatura Máxima (°C)', 10.0, 40.0, 27.0)
    temp_min = st.sidebar.number_input('Temperatura Mínima (°C)', 0.0, 30.0, 19.0)
    temp_prom = st.sidebar.number_input('Temperatura Promedio (°C)', 5.0, 35.0, 23.0)
    hr_prom = st.sidebar.number_input('Humedad Relativa Promedio (%)', 30.0, 100.0, 89.0)
    precipitacion = st.sidebar.number_input('Precipitación (mm)', 0.0, 50.0, 0.0)
    viento = st.sidebar.number_input('Velocidad del Viento (km/h)', 0.0, 50.0, 14.0)
    sol = st.sidebar.number_input('Horas de Sol', 0.0, 14.0, 8.0)
    
    data = {
        'Temp_Max_C': temp_max, 'Temp_Min_C': temp_min, 'Temp_Prom_C': temp_prom,
        'HR_Prom_Porc': hr_prom, 'Precipitacion_mm': precipitacion,
        'Vel_Viento_Prom_kmh': viento, 'Horas_Sol': sol
    }
    features = pd.DataFrame(data, index=[0])
    return features

# --- 3. CONSTRUCCIÓN DE LA APLICACIÓN ---

# Cargar el modelo una sola vez al inicio
modelo = cargar_modelo()

# Construir la barra lateral y obtener los inputs del usuario
input_df = construir_sidebar()

# --- Página Principal ---
st.title('🍇 Panel de Control del Fundo')
st.header(f"Predicción de Riesgo para el Sector: {st.session_state.sector}")

st.subheader('Parámetros Ingresados:')
st.write(input_df)

if st.button('Predecir Riesgo y Obtener Recomendación'):
    # Cargar el inventario actualizado
    inventario_df = cargar_inventario()
    
    if inventario_df.empty:
        st.warning("⚠️ Tu inventario de productos está vacío. Las recomendaciones serán genéricas. Ve a la página de 'Inventario' para añadir productos.")
    
    # Hacer la predicción
    prediction = modelo.predict(input_df)
    
    # Obtener y mostrar la recomendación
    recomendacion_texto = obtener_recomendacion(prediction[0], inventario_df)
    
    st.subheader('Diagnóstico y Recomendación')
    st.info(recomendacion_texto)
