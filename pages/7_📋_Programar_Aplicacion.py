import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Programar Aplicación", page_icon="🗓️", layout="wide")
st.title("🗓️ Programar Nueva Aplicación")
st.write("Esta sección es para que el ingeniero programe las órdenes de trabajo.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Productos.xlsx'
ARCHIVO_TAREAS = 'Tareas_Aplicacion.xlsx' # Este será nuestro nuevo archivo central

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
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto'])
df_tareas = cargar_datos(ARCHIVO_TAREAS, [])

# --- INICIALIZAR MEZCLA TEMPORAL ---
if 'mezcla_a_programar' not in st.session_state:
    st.session_state.mezcla_a_programar = []

# --- INTERFAZ PARA PROGRAMAR ---

# SECCIÓN 1: CONSTRUIR EL CALDO
st.subheader("1. Construir Caldo de Aplicación")
col_info1, col_info2 = st.columns(2)
with col_info1:
    hectareas = st.number_input("Hectáreas a Tratar", min_value=0.01, value=1.0, format="%.2f")
if not df_inventario.empty:
    productos_disponibles = df_inventario['Producto'].tolist()
    col_prod, col_dosis, col_btn = st.columns([2, 1, 1])
    with col_prod:
        producto_a_anadir = st.selectbox("Seleccione un producto del inventario", options=productos_disponibles)
    with col_dosis:
        dosis_producto = st.number_input("Dosis (cantidad por Hectárea)", min_value=0.0, format="%.3f")
    with col_btn:
        st.write("")
        if st.button("➕ Añadir Producto a la Mezcla"):
            cantidad_total_usada = dosis_producto * hectareas
            st.session_state.mezcla_a_programar.append({
                "Producto": producto_a_anadir,
                "Dosis_por_Ha": dosis_producto,
                "Cantidad_Total_Usada": round(cantidad_total_usada, 2)
            })
            st.rerun()
else:
    st.warning("No hay productos en el inventario. Por favor, añada productos en la página de 'Inventario'.")

# Mostrar la mezcla actual y opción para limpiarla
if st.session_state.mezcla_a_programar:
    st.write("**Mezcla a Programar:**")
    st.dataframe(pd.DataFrame(st.session_state.mezcla_a_programar), use_container_width=True)
    if st.button("Limpiar Mezcla"):
        st.session_state.mezcla_a_programar = []
        st.rerun()

st.divider()

# SECCIÓN 2: COMPLETAR Y GUARDAR LA ORDEN DE TRABAJO
st.subheader("2. Completar y Guardar Orden de Trabajo")
with st.form("programar_form"):
    col_f, col_s = st.columns(2)
    with col_f:
        fecha_aplicacion = st.date_input("Fecha Programada de Aplicación", datetime.now())
    with col_s:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_aplicacion = st.selectbox("Lote / Sector", options=sectores_del_fundo)
    
    objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control curativo oídio y bajada de población de mosca")
    
    submitted_programar = st.form_submit_button("✅ Programar Orden de Trabajo")

    if submitted_programar:
        if not st.session_state.mezcla_a_programar:
            st.error("Error: La mezcla de productos está vacía. Por favor, añada al menos un producto.")
        else:
            # Crear un ID único para la tarea
            id_tarea = datetime.now().strftime("%Y%m%d%H%M%S")
            
            # Convertir la mezcla a un string JSON para guardarla en una sola celda
            mezcla_json = json.dumps(st.session_state.mezcla_a_programar)
            
            # Crear el registro de la nueva tarea
            nueva_tarea = pd.DataFrame([{
                "ID_Tarea": id_tarea,
                "Status": "Pendiente de Mezcla",
                "Fecha_Programada": fecha_aplicacion.strftime("%Y-%m-%d"),
                "Sector": sector_aplicacion,
                "Objetivo": objetivo_tratamiento,
                "Hectareas": hectareas,
                "Mezcla_Productos": mezcla_json,
                # Dejamos las columnas de los otros módulos vacías por ahora
                "Mezcla_Responsable": None,
                "Mezcla_Fecha_Hora": None,
                "Tractor_Responsable": None,
                "Tractor_Utilizado": None,
                "Pulverizador": None,
                "Presion_Bar": None,
                "Boquillas_Info": None,
                "Aplicacion_Hora_Inicio": None,
                "Aplicacion_Hora_Fin": None,
                "Observaciones": None
            }])
            
            df_tareas_final = pd.concat([df_tareas, nueva_tarea], ignore_index=True)
            exito, mensaje = guardar_datos(df_tareas_final, ARCHIVO_TAREAS)
            
            if exito:
                st.success(f"¡Orden de trabajo para el sector '{sector_aplicacion}' programada exitosamente!")
                st.session_state.mezcla_a_programar = []
                # No usamos st.rerun() dentro del form para que el mensaje de éxito se quede visible
            else:
                st.error(f"No se pudo programar la aplicación. Error: {mensaje}")

                else:
                    st.error(f"No se pudo programar la aplicación. Error: {mensaje}")
