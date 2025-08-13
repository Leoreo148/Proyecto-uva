import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Órdenes de Aplicación", page_icon="📋", layout="wide")
st.title("📋 Órdenes de Aplicación")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Productos.xlsx'
ARCHIVO_TAREAS = 'Tareas_Aplicacion.xlsx'

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS ---
def cargar_datos(nombre_archivo, columnas_defecto):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    else:
        return pd.DataFrame(columns=columnas_defecto)

def guardar_datos(df, nombre_archivo):
    df.to_excel(nombre_archivo, index=False, engine='openpyxl')

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto', 'Cantidad_Stock'])
df_tareas = cargar_datos(ARCHIVO_TAREAS, ['ID_Tarea', 'Status'])

# --- SECCIÓN 1: APLICACIONES PENDIENTES ---
st.subheader("📌 Aplicaciones Pendientes")
st.info("ℹ️ Abra esta página con internet para cargar las últimas tareas. Podrá verlas después sin conexión.")

# Filtrar tareas que están "Programada"
tareas_pendientes = df_tareas[df_tareas['Status'] == 'Programada']

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Sector:** {tarea['Sector']} | **Fecha Programada:** {pd.to_datetime(tarea['Fecha']).strftime('%d/%m/%Y')}")
                st.markdown(f"**Objetivo:** {tarea['Objetivo']}")
                mezcla = json.loads(tarea['Mezcla_Productos'])
                st.dataframe(pd.DataFrame(mezcla), use_container_width=True)
            
            with col2:
                st.write("") # Espacio para alinear
                if st.button("✅ Marcar como Terminado", key=f"complete_{tarea['ID_Tarea']}"):
                    try:
                        # --- ESTA PARTE REQUIERE INTERNET ---
                        # 1. Recargar los datos para asegurar que no han cambiado
                        df_tareas_actual = cargar_datos(ARCHIVO_TAREAS, ['ID_Tarea', 'Status'])
                        df_inventario_actual = cargar_datos(ARCHIVO_INVENTARIO, ['Producto', 'Cantidad_Stock'])

                        # 2. Actualizar el estado de la tarea
                        df_tareas_actual.loc[df_tareas_actual['ID_Tarea'] == tarea['ID_Tarea'], 'Status'] = 'Completada'
                        
                        # 3. Descontar del inventario
                        for producto_usado in mezcla:
                            nombre = producto_usado["Producto"]
                            cantidad_usada = producto_usado["Cantidad_Total_Usada"]
                            stock_actual = df_inventario_actual.loc[df_inventario_actual['Producto'] == nombre, 'Cantidad_Stock'].iloc[0]
                            nuevo_stock = stock_actual - cantidad_usada
                            df_inventario_actual.loc[df_inventario_actual['Producto'] == nombre, 'Cantidad_Stock'] = nuevo_stock
                        
                        # 4. Guardar ambos archivos
                        guardar_datos(df_tareas_actual, ARCHIVO_TAREAS)
                        guardar_datos(df_inventario_actual, ARCHIVO_INVENTARIO)
                        
                        st.success(f"¡Aplicación en sector {tarea['Sector']} completada y stock actualizado!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Se necesita conexión a internet para completar la tarea. Inténtelo de nuevo cuando tenga señal.")

else:
    st.info("No hay aplicaciones pendientes programadas.")

st.divider()

# --- SECCIÓN 2: PROGRAMAR NUEVA APLICACIÓN (REQUIERE INTERNET) ---
with st.expander("➕ Programar Nueva Aplicación (Requiere Conexión)"):
    
    if 'mezcla_temporal' not in st.session_state:
        st.session_state.mezcla_temporal = []

    st.markdown("##### 1. Construir Caldo de Aplicación")
    col_info1, col_info2 = st.columns(2)
    with col_info1:
        hectareas = st.number_input("Hectáreas a Tratar", min_value=0.01, value=1.0, format="%.2f", key="hectareas_form")
    
    if not df_inventario.empty:
        productos_disponibles = df_inventario['Producto'].tolist()
        col_prod, col_dosis, col_btn = st.columns([2, 1, 1])
        with col_prod:
            producto_a_anadir = st.selectbox("Seleccione un producto", options=productos_disponibles, key="prod_select")
        with col_dosis:
            dosis_producto = st.number_input("Dosis (cant/Ha)", min_value=0.0, format="%.3f", key="dosis_form")
        with col_btn:
            st.write("")
            if st.button("Añadir Producto a Mezcla"):
                cantidad_total_usada = dosis_producto * hectareas
                st.session_state.mezcla_temporal.append({
                    "Producto": producto_a_anadir,
                    "Dosis_por_Ha": dosis_producto,
                    "Cantidad_Total_Usada": round(cantidad_total_usada, 2)
                })

    if st.session_state.mezcla_temporal:
        st.write("**Mezcla a Programar:**")
        st.dataframe(pd.DataFrame(st.session_state.mezcla_temporal), use_container_width=True)

    with st.form("programar_form"):
        st.markdown("##### 2. Completar y Programar")
        col_f, col_s = st.columns(2)
        with col_f:
            fecha_aplicacion = st.date_input("Fecha de Aplicación", datetime.now())
        with col_s:
            sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
            sector_aplicacion = st.selectbox("Lote / Sector", options=sectores_del_fundo)
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control de Oídio...")
        nombre_operario = st.text_input("Nombre del Aplicador")

        submitted_programar = st.form_submit_button("🗓️ Programar Aplicación")

        if submitted_programar:
            if not st.session_state.mezcla_temporal:
                st.error("Error: La mezcla está vacía.")
            else:
                id_tarea = datetime.now().strftime("%Y%m%d%H%M%S")
                mezcla_json = json.dumps(st.session_state.mezcla_temporal)
                nuevo_registro = pd.DataFrame([{"ID_Tarea": id_tarea, "Status": "Programada", "Fecha": fecha_aplicacion.strftime("%Y-%m-%d"), "Sector": sector_aplicacion, "Objetivo": objetivo_tratamiento, "Operario": nombre_operario, "Mezcla_Productos": mezcla_json}])
                df_tareas_final = pd.concat([df_tareas, nuevo_registro], ignore_index=True)
                guardar_datos(df_tareas_final, ARCHIVO_TAREAS)
                st.success(f"¡Aplicación para el sector '{sector_aplicacion}' programada!")
                st.session_state.mezcla_temporal = []
                st.rerun()



