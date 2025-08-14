import streamlit as st
import pandas as pd
import joblib

st.set_page_config(page_title="Panel del Fundo", page_icon="🍇", layout="wide")

pwa_code = """
    <link rel="manifest" href="/static/manifest.json">
    <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js').then(function(registration) {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            }).catch(function(err) {
                console.log('ServiceWorker registration failed: ', err);
            });
        }
    </script>
"""
st.html(pwa_code)

# --- FUNCIONES AUXILIARES ---
def cargar_modelo():
    try:
        return joblib.load('modelo_oidio.joblib')
    except FileNotFoundError:
        st.error("Error Crítico: No se encontró 'modelo_oidio.joblib'.")
        st.stop()

def cargar_inventario():
    try:
        return pd.read_excel("Inventario_Productos.xlsx")
    except FileNotFoundError:
        return pd.DataFrame(columns=['Producto', 'Tipo_Accion'])

def obtener_recomendacion(prediccion, inventario_df):
    if prediccion == 0:
        return "🟢 **RIESGO BAJO:** No se requiere acción inmediata."
    elif prediccion == 1:
        recomendacion = "🟡 **RIESGO MEDIO:** Aplicación **Preventiva** sugerida."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Preventivo', 'Curativo'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos:** " + ", ".join(productos_sugeridos['Producto'].tolist())
        return recomendacion
    else:
        recomendacion = "🔴 **RIESGO ALTO:** Aplicación **Curativa** o **Erradicante** sugerida."
        productos_sugeridos = inventario_df[inventario_df['Tipo_Accion'].isin(['Curativo', 'Erradicante'])]
        if not productos_sugeridos.empty:
            recomendacion += "\n\n**Productos:** " + ", ".join(productos_sugeridos['Producto'].tolist())
        return recomendacion

# --- BARRA LATERAL ---
st.sidebar.header('Parámetros del Clima')
temp_max = st.sidebar.number_input('Temp. Máxima (°C)', 10.0, 40.0, 27.0)
temp_min = st.sidebar.number_input('Temp. Mínima (°C)', 0.0, 30.0, 19.0)
temp_prom = st.sidebar.number_input('Temp. Promedio (°C)', 5.0, 35.0, 23.0)
hr_prom = st.sidebar.number_input('Humedad Rel. (%)', 30.0, 100.0, 89.0)
precipitacion = st.sidebar.number_input('Precipitación (mm)', 0.0, 50.0, 0.0)
viento = st.sidebar.number_input('Viento (km/h)', 0.0, 50.0, 14.0)
sol = st.sidebar.number_input('Horas de Sol', 0.0, 14.0, 8.0)

# --- PÁGINA PRINCIPAL ---
st.title('🍇 Predicción de Riesgo de Oídio')
st.write("Esta página predice el riesgo de enfermedad basado en los parámetros del clima.")
modelo = cargar_modelo()
input_data = {
    'Temp_Max_C': temp_max, 'Temp_Min_C': temp_min, 'Temp_Prom_C': temp_prom,
    'HR_Prom_Porc': hr_prom, 'Precipitacion_mm': precipitacion,
    'Vel_Viento_Prom_kmh': viento, 'Horas_Sol': sol
}
input_df = pd.DataFrame(input_data, index=[0])
st.subheader('Parámetros Ingresados:')
st.write(input_df)
if st.button('Predecir Riesgo'):
    inventario_df = cargar_inventario()
    prediction = modelo.predict(input_df)
    recomendacion_texto = obtener_recomendacion(prediction[0], inventario_df)
    st.info(recomendacion_texto)

