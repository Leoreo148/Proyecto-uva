import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Fenológica", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica por Estados")
st.write("Registre el conteo de brotes/yemas en cada estado fenológico para un grupo de 25 plantas.")

# --- Selección de Sector y Fecha ---
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

# --- Creación de la Tabla de Ingreso de Datos ---
# Definimos los estados fenológicos basados en tu leyenda
columnas_fenologicas = [
    'Punta algodón',
    'Punta verde',
    'Salida de hojas',
    'Hojas extendidas',
    'Racimos visibles'
]

# Creamos un DataFrame vacío como plantilla para las 25 plantas
plant_numbers = [f"Planta {i+1}" for i in range(25)]
df_plantilla = pd.DataFrame(0, index=plant_numbers, columns=columnas_fenologicas)

st.subheader("Tabla de Ingreso de Datos")
st.write("Ingrese los conteos en la siguiente tabla:")

# Usamos st.data_editor para crear una tabla editable similar a Excel
# El usuario puede hacer clic en las celdas y escribir los números directamente.
df_editada = st.data_editor(df_plantilla, use_container_width=True)

# --- Botón para Procesar los Datos ---
if st.button("Calcular Totales, Porcentajes y Guardar"):
    
    # 1. Calcular Totales por Estado Fenológico
    totales_por_estado = df_editada.sum()
    
    # 2. Calcular el Gran Total de todos los brotes/yemas contados
    gran_total = totales_por_estado.sum()
    
    if gran_total > 0:
        # 3. Calcular Porcentajes
        porcentajes = (totales_por_estado / gran_total * 100).round(2)
        
        # 4. Crear y Mostrar el DataFrame de Resumen
        st.subheader("Resumen de la Evaluación")
        df_resumen = pd.DataFrame({
            'Total por Estado': totales_por_estado,
            'Porcentaje (%)': porcentajes
        })
        st.dataframe(df_resumen, use_container_width=True)
        
        # 5. Guardar los datos detallados
        archivo_evaluacion = 'Evaluacion_Fenologica_Detallada.xlsx'
        
        # Añadimos el sector y la fecha para el guardado
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_evaluacion.strftime("%Y-%m-%d")
        
        if os.path.exists(archivo_evaluacion):
            df_existente = pd.read_excel(archivo_evaluacion)
            df_final = pd.concat([df_existente, df_para_guardar.reset_index().rename(columns={'index': 'Planta'})], ignore_index=True)
        else:
            df_final = df_para_guardar.reset_index().rename(columns={'index': 'Planta'})
            
        df_final.to_excel(archivo_evaluacion, index=False)
        st.success(f"¡Evaluación guardada exitosamente en '{archivo_evaluacion}'!")

        with st.expander("Ver datos detallados guardados"):
            st.dataframe(df_editada)
            
    else:
        st.warning("No se ingresaron datos. La tabla está vacía.")
