import streamlit as st
import pandas as pd
import os
from datetime import datetime, time

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registro de Aplicación", page_icon="📋", layout="wide")
st.title("📋 Registro de Aplicación de Fitosanitarios")

# --- NOMBRES DE ARCHIVOS (BASES DE DATOS) ---
ARCHIVO_INVENTARIO = 'Inventario_Productos.xlsx'
ARCHIVO_APLICACIONES = 'Registro_Aplicaciones.xlsx'

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS ---
def cargar_datos(nombre_archivo, columnas_defecto):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    else:
        return pd.DataFrame(columns=columnas_defecto)

def guardar_datos(df, nombre_archivo):
    df.to_excel(nombre_archivo, index=False)

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto'])
df_aplicaciones = cargar_datos(ARCHIVO_APLICACIONES, [])

# --- INICIALIZAR MEMORIA DE SESIÓN PARA LA MEZCLA DE PRODUCTOS ---
if 'mezcla_productos' not in st.session_state:
    st.session_state.mezcla_productos = []

# --- FORMULARIO PRINCIPAL DE APLICACIÓN ---
with st.form("aplicacion_form"):
    
    # --- SECCIÓN 1: INFORMACIÓN GENERAL ---
    st.subheader("1. Información General de la Aplicación")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_aplicacion = st.date_input("Fecha de Aplicación", datetime.now())
    with col2:
        sectores_del_fundo = ['J-3', 'W1', 'W2', 'K1', 'K2', 'General']
        sector_aplicacion = st.selectbox("Lote / Sector", options=sectores_del_fundo)
    with col3:
        hectareas = st.number_input("Hectáreas Tratadas", min_value=0.0, format="%.2f")

    objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control de Oídio, Fertilización Foliar...")
    
    st.divider()

    # --- SECCIÓN 2: CALDO DE APLICACIÓN (MEZCLA DE PRODUCTOS) ---
    st.subheader("2. Caldo de Aplicación")
    
    # Selección de productos del inventario
    if not df_inventario.empty:
        productos_disponibles = df_inventario['Producto'].tolist()
        
        # Interfaz para añadir productos a la mezcla
        col_prod, col_dosis, col_btn = st.columns([2,1,1])
        with col_prod:
            producto_a_anadir = st.selectbox("Seleccione un producto del inventario", options=productos_disponibles)
        with col_dosis:
            dosis_producto = st.number_input("Dosis (cantidad por Hectárea)", min_value=0.0, format="%.3f")
        with col_btn:
            st.write("") # Espacio para alinear el botón
            if st.button("➕ Añadir Producto a la Mezcla"):
                cantidad_total_usada = dosis_producto * hectareas
                st.session_state.mezcla_productos.append({
                    "Producto": producto_a_anadir,
                    "Dosis_por_Ha": dosis_producto,
                    "Cantidad_Total_Usada": round(cantidad_total_usada, 2)
                })

    # Mostrar la mezcla actual
    if st.session_state.mezcla_productos:
        st.write("**Mezcla Actual:**")
        df_mezcla = pd.DataFrame(st.session_state.mezcla_productos)
        st.dataframe(df_mezcla, use_container_width=True)

    st.divider()

    # --- SECCIÓN 3: MAQUINARIA Y MÉTODO ---
    st.subheader("3. Maquinaria y Método de Aplicación")
    col_maq1, col_maq2, col_maq3 = st.columns(3)
    with col_maq1:
        tractor_utilizado = st.text_input("Tractor Utilizado")
        volumen_agua_total = st.number_input("Volumen de Agua Total (L)", min_value=0)
    with col_maq2:
        pulverizador = st.text_input("Pulverizador / Fumigador")
        presion_bar = st.number_input("Presión (bar)", min_value=0)
    with col_maq3:
        metodo_aplicacion = st.selectbox("Método de Aplicación", ["Foliar", "Drench", "Espolvoreo"])
        nombre_operario = st.text_input("Nombre del Aplicador")

    # --- SECCIÓN 4: HORARIOS ---
    st.subheader("4. Horarios")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        hora_inicio = st.time_input("Hora de Inicio", time(6, 0))
    with col_t2:
        hora_final = st.time_input("Hora Final", time(9, 0))

    # --- BOTÓN DE ENVÍO FINAL ---
    st.divider()
    submitted_aplicacion = st.form_submit_button("✅ Guardar Registro de Aplicación Completo")


# --- LÓGICA PARA GUARDAR Y ACTUALIZAR TODO ---
if submitted_aplicacion:
    if not st.session_state.mezcla_productos:
        st.error("Error: Debe añadir al menos un producto a la mezcla.")
    else:
        # 1. Actualizar el inventario
        inventario_actualizado = df_inventario.copy()
        for producto_usado in st.session_state.mezcla_productos:
            nombre = producto_usado["Producto"]
            cantidad_usada = producto_usado["Cantidad_Total_Usada"]
            
            # Restar del stock
            stock_actual = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Cantidad_Stock'].iloc[0]
            nuevo_stock = stock_actual - cantidad_usada
            
            # Actualizar el DataFrame
            inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Cantidad_Stock'] = nuevo_stock

        guardar_datos(inventario_actualizado, ARCHIVO_INVENTARIO)
        
        # 2. Guardar el registro de la aplicación
        productos_str = ", ".join([p["Producto"] for p in st.session_state.mezcla_productos])
        
        nuevo_registro_app = pd.DataFrame([{
            "Fecha": fecha_aplicacion.strftime("%Y-%m-%d"),
            "Sector": sector_aplicacion,
            "Hectareas": hectareas,
            "Objetivo": objetivo_tratamiento,
            "Productos_Usados": productos_str,
            "Volumen_Agua_L": volumen_agua_total,
            "Tractor": tractor_utilizado,
            "Pulverizador": pulverizador,
            "Metodo": metodo_aplicacion,
            "Operario": nombre_operario,
            "Hora_Inicio": hora_inicio.strftime("%H:%M"),
            "Hora_Final": hora_final.strftime("%H:%M")
        }])
        
        df_aplicaciones_final = pd.concat([df_aplicaciones, nuevo_registro_app], ignore_index=True)
        guardar_datos(df_aplicaciones_final, ARCHIVO_APLICACIONES)
        
        st.success("✅ ¡Registro de aplicación guardado y stock de inventario actualizado exitosamente!")
        
        # Limpiar la mezcla para el siguiente registro
        st.session_state.mezcla_productos = []
        st.rerun() # Recarga la página para limpiar el formulario
