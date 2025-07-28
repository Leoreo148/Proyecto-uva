import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Planta")
st.write("Registre el estado fenológico para un grupo de 25 plantas en un sector específico.")

# --- Columnas para Selección de Sector y Fecha ---
col1, col2 = st.columns(2)

with col1:
    sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
    sector_seleccionado = st.selectbox(
        'Seleccione el Sector de Evaluación:',
        options=sectores_del_fundo
    )

with col2:
    fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())

st.divider()

# --- Formulario para Ingreso de Datos de 25 Plantas ---
st.subheader("Registro de las 25 Plantas")

# Opciones de la leyenda
opciones_fenologia = [
    'No Aplica / Otro',
    'Punta algodón',
    'Punta verde',
    'Salida de hojas',
    'Hojas extendidas',
    'Racimos visibles'
]

# Creamos un formulario para agrupar todos los inputs
with st.form("evaluacion_plantas_form"):
    # Creamos una estructura de columnas para que el formulario sea más compacto
    columnas_inputs = st.columns(5)
    
    # Lista para guardar el estado de cada planta
    estados_plantas = []

    # Generamos los inputs para las 25 plantas
    for i in range(25):
        # Distribuimos los inputs en las 5 columnas
        col = columnas_inputs[i % 5]
        # Creamos un selectbox para cada planta
        estado = col.selectbox(
            f"Planta {i+1}",
            options=opciones_fenologia,
            key=f"planta_{i}" # Clave única para cada input
        )
        estados_plantas.append(estado)

    # Botón de envío del formulario
    submitted = st.form_submit_button("Calcular y Guardar Evaluación")

# --- Lógica para Procesar y Guardar los Datos ---
if submitted:
    # 1. Crear el DataFrame con los datos detallados
    datos_detallados = []
    for i, estado in enumerate(estados_plantas):
        datos_detallados.append({
            "Sector": sector_seleccionado,
            "Fecha": fecha_evaluacion.strftime("%Y-%m-%d"),
            "Numero_Planta": i + 1,
            "Estado_Fenologico": estado
        })
    df_detallado = pd.DataFrame(datos_detallados)

    # 2. Guardar los datos detallados en un archivo Excel
    archivo_detallado = 'Registro_Fenologico_Detallado.xlsx'
    if os.path.exists(archivo_detallado):
        df_existente = pd.read_excel(archivo_detallado)
        df_final_detallado = pd.concat([df_existente, df_detallado], ignore_index=True)
    else:
        df_final_detallado = df_detallado
    df_final_detallado.to_excel(archivo_detallado, index=False)
    
    st.success(f"¡Datos de las 25 plantas guardados exitosamente en '{archivo_detallado}'!")

    # 3. Calcular y mostrar el resumen (Totales y Porcentajes)
    st.subheader("Resumen de la Evaluación")
    
    # Contar cuántas plantas hay en cada estado
    resumen_df = df_detallado['Estado_Fenologico'].value_counts().reset_index()
    resumen_df.columns = ['Estado Fenológico', 'Total Plantas']
    
    # Calcular el porcentaje
    total_plantas_evaluadas = len(df_detallado)
    resumen_df['Porcentaje (%)'] = (resumen_df['Total Plantas'] / total_plantas_evaluadas * 100).round(2)
    
    # Mostrar la tabla de resumen
    st.dataframe(resumen_df, use_container_width=True)

    # Mostrar un gráfico de barras
    st.bar_chart(resumen_df.set_index('Estado Fenológico')['Total Plantas'])
