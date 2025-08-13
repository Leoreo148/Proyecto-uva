import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Programar Aplicación", page_icon="🗓️", layout="wide")
st.title("🗓️ Programar Aplicación Foliar")
st.write("El ingeniero programa la orden de trabajo con todos los detalles de la aplicación.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Productos.xlsx'
ARCHIVO_ORDENES = 'Ordenes_de_Trabajo.xlsx'

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS ---
def cargar_datos(nombre_archivo, columnas_defecto):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    else:
        return pd.DataFrame(columns=columnas_defecto)

def guardar_datos(df, nombre_archivo):
    try:
        df.to_excel(nombre_archivo, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto', 'Unidad'])
df_ordenes = cargar_datos(ARCHIVO_ORDENES, [])

# --- INICIALIZAR MEZCLA TEMPORAL ---
if 'mezcla_a_programar' not in st.session_state:
    st.session_state.mezcla_a_programar = []

# --- INTERFAZ PARA PROGRAMAR ---

with st.form("programar_form"):
    st.subheader("1. Datos Generales de la Aplicación")
    
    # Fila 1: Fecha, Lote, Hectáreas
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_aplicacion = st.date_input("Fecha Programada")
    with col2:
        sectores_del_fundo = ['W3', 'J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_aplicacion = st.selectbox("Lote / Sector", options=sectores_del_fundo)
    with col3:
        hectareas = st.number_input("Hectáreas", min_value=0.01, value=1.0, format="%.2f")

    # Fila 2: Objetivo y Turno
    col4, col5 = st.columns(2)
    with col4:
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", "Trips - araña roja")
    with col5:
        turno = st.selectbox("Turno", ["Día", "Noche"])

    st.divider()
    
    # SECCIÓN 2: CONSTRUIR LA RECETA
    st.subheader("2. Receta de Mezcla")
    
    # Interfaz para añadir productos a la mezcla (dentro del formulario)
    if not df_inventario.empty:
        productos_disponibles = df_inventario['Producto'].tolist()
        
        # Usamos un "editor de datos" para añadir múltiples productos de forma dinámica
        productos_para_mezcla = st.data_editor(
            pd.DataFrame([{"Producto": productos_disponibles[0], "Dosis por Ha": 1.0}]),
            num_rows="dynamic",
            column_config={
                "Producto": st.column_config.SelectboxColumn("Producto", options=productos_disponibles, required=True),
                "Dosis por Ha": st.column_config.NumberColumn("Dosis (cant/Ha)", min_value=0.0, format="%.3f")
            },
            key="editor_mezcla"
        )
    else:
        st.warning("No hay productos en el inventario para crear una receta.")
        productos_para_mezcla = pd.DataFrame() # DataFrame vacío si no hay inventario

    # Botón de envío final del formulario
    submitted_programar = st.form_submit_button("✅ Programar Orden de Trabajo")

    if submitted_programar:
        if productos_para_mezcla.empty or productos_para_mezcla["Producto"].isnull().any():
            st.error("Error: La receta está vacía o incompleta. Por favor, añada al menos un producto.")
        else:
            # Calcular la cantidad total de cada producto
            productos_para_mezcla['Cantidad_Total'] = (productos_para_mezcla['Dosis por Ha'] * hectareas).round(2)
            
            # Añadir la unidad desde el inventario
            productos_para_mezcla = pd.merge(productos_para_mezcla, df_inventario[['Producto', 'Unidad']], on='Producto', how='left')
            
            id_orden = datetime.now().strftime("%Y%m%d%H%M%S")
            receta_json = productos_para_mezcla.to_json(orient='records')
            
            nueva_orden = pd.DataFrame([{
                "ID_Orden": id_orden,
                "Status": "Pendiente de Mezcla",
                "Fecha_Programada": fecha_aplicacion.strftime("%Y-%m-%d"),
                "Sector_Aplicacion": sector_aplicacion,
                "Objetivo": objetivo_tratamiento,
                "Hectareas": hectareas,
                "Turno": turno,
                "Receta_Mezcla": receta_json,
                # Dejamos las columnas de los otros módulos vacías por ahora
                "Mezcla_Responsable": None,
                "Mezcla_Confirmada": None,
                "Tractor_Responsable": None,
                "Tractor_Info": None,
                "Aplicacion_Completada": None
            }])
            
            df_ordenes_final = pd.concat([df_ordenes, nueva_orden], ignore_index=True)
            exito, mensaje = guardar_datos(df_ordenes_final, ARCHIVO_ORDENES)
            
            if exito:
                st.success(f"¡Orden de mezcla para el sector '{sector_aplicacion}' programada exitosamente!")
            else:
                st.error(f"No se pudo programar la orden. Error: {mensaje}")
