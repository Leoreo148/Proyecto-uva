import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- Configuración de la Página ---
st.set_page_config(page_title="Evaluación Cuantitativa", page_icon="🌱", layout="wide")
st.title("🌱 Evaluación Fenológica Cuantitativa")
st.write("Registre las mediciones para un grupo de 25 plantas en un sector específico.")

# --- Columnas para Selección de Sector y Fecha ---
col1, col2 = st.columns(2)
with col1:
    sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
    sector_seleccionado = st.selectbox(
        'Seleccione el Sector de Evaluación:',
        options=sectores_del_fundo,
        key='sector_eval' # Usamos una clave única para esta página
    )
with col2:
    fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())

st.divider()

# --- Formulario para Ingreso de Datos de 25 Plantas ---
st.subheader("Tabla de Ingreso de Datos")

# Creamos un formulario para agrupar todos los inputs
with st.form("evaluacion_cuantitativa_form"):
    
    # --- Encabezados de la Tabla ---
    header_cols = st.columns((1, 2, 2, 2)) # Ajustar anchos de columna
    header_cols[0].write("**Planta #**")
    header_cols[1].write("**N° Hojas Extendidas**")
    header_cols[2].write("**Longitud Brote (cm)**")
    header_cols[3].write("**N° Racimos Visibles**")

    # Lista para guardar todos los datos de las plantas
    datos_plantas = []

    # --- Filas de Inputs para las 25 Plantas ---
    for i in range(25):
        row_cols = st.columns((1, 2, 2, 2))
        
        # Columna para el número de planta (solo texto)
        row_cols[0].write(f"**{i+1}**")
        
        # Inputs numéricos para cada parámetro
        hojas = row_cols[1].number_input("Hojas", min_value=0, step=1, key=f"hojas_{i}", label_visibility="collapsed")
        longitud = row_cols[2].number_input("Longitud", min_value=0.0, step=0.1, format="%.1f", key=f"long_{i}", label_visibility="collapsed")
        racimos = row_cols[3].number_input("Racimos", min_value=0, step=1, key=f"racimos_{i}", label_visibility="collapsed")
        
        datos_plantas.append({
            "Numero_Planta": i + 1,
            "Hojas_Extendidas": hojas,
            "Longitud_Brote_cm": longitud,
            "Racimos_Visibles": racimos
        })

    # Botón de envío del formulario
    submitted = st.form_submit_button("Calcular Promedios y Guardar")

# --- Lógica para Procesar y Guardar los Datos ---
if submitted:
    # 1. Crear el DataFrame con los datos detallados
    df_evaluacion = pd.DataFrame(datos_plantas)
    
    # Añadir el sector y la fecha a cada fila
    df_evaluacion['Sector'] = sector_seleccionado
    df_evaluacion['Fecha'] = fecha_evaluacion.strftime("%Y-%m-%d")
    
    # Reordenar columnas para que Sector y Fecha estén al principio
    df_evaluacion = df_evaluacion[['Sector', 'Fecha', 'Numero_Planta', 'Hojas_Extendidas', 'Longitud_Brote_cm', 'Racimos_Visibles']]
    
    # 2. Guardar los datos detallados en un archivo Excel
    archivo_evaluacion = 'Evaluacion_Foliar_Cuantitativa.xlsx'
    if os.path.exists(archivo_evaluacion):
        df_existente = pd.read_excel(archivo_evaluacion)
        df_final = pd.concat([df_existente, df_evaluacion], ignore_index=True)
    else:
        df_final = df_evaluacion
        
    df_final.to_excel(archivo_evaluacion, index=False)
    st.success(f"¡Evaluación guardada exitosamente en '{archivo_evaluacion}'!")

    # 3. Calcular y mostrar el resumen (Promedios)
    st.subheader(f"Resumen para el Sector: {sector_seleccionado} en la fecha {fecha_evaluacion.strftime('%d/%m/%Y')}")
    
    # Calculamos los promedios de las columnas numéricas
    promedios = df_evaluacion[['Hojas_Extendidas', 'Longitud_Brote_cm', 'Racimos_Visibles']].mean().round(2)
    df_promedios = pd.DataFrame(promedios).transpose()
    df_promedios.index = ['Promedio por Planta']
    
    # Mostrar la tabla de promedios
    st.dataframe(df_promedios, use_container_width=True)

    # Mostrar la tabla con todos los datos ingresados
    with st.expander("Ver datos detallados ingresados"):
        st.dataframe(df_evaluacion, use_container_width=True)
