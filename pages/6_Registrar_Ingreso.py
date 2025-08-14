import streamlit as st
import pandas as pd
import os
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso", page_icon="📈", layout="wide")
st.title("📈 Registrar Ingreso de Productos")
st.write("Registre la compra o llegada de nueva mercadería al almacén.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Maestro.xlsx'
ARCHIVO_INGRESOS = 'Historial_Ingresos.xlsx'

# --- FUNCIONES ---
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
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Codigo', 'Producto', 'Stock_Actual'])
df_ingresos = cargar_datos(ARCHIVO_INGRESOS, [])

# --- FORMULARIO DE INGRESO ---
st.subheader("Registrar Nuevo Ingreso")

if not df_inventario.empty:
    with st.form("ingreso_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            # Menú desplegable para seleccionar el producto por su nombre
            producto_seleccionado = st.selectbox(
                "Seleccione el Producto que ingresa:",
                options=df_inventario['Producto']
            )
        with col2:
            cantidad_ingresada = st.number_input("Cantidad Ingresada", min_value=0.01, format="%.2f")

        # Campos adicionales
        col3, col4 = st.columns(2)
        with col3:
            referencia = st.text_input("Referencia (N° de Guía, Factura, etc.)")
        with col4:
            responsable = st.text_input("Recibido por:")
        
        submitted = st.form_submit_button("✅ Registrar Ingreso y Actualizar Stock")

        if submitted:
            # --- LÓGICA DE ACTUALIZACIÓN ---
            # 1. Añadir el movimiento al historial de ingresos
            id_ingreso = datetime.now().strftime("%Y%m%d%H%M%S")
            codigo_producto = df_inventario.loc[df_inventario['Producto'] == producto_seleccionado, 'Codigo'].iloc[0]
            
            nuevo_ingreso = pd.DataFrame([{
                "ID_Ingreso": id_ingreso,
                "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "Codigo_Producto": codigo_producto,
                "Producto": producto_seleccionado,
                "Cantidad_Ingresada": cantidad_ingresada,
                "Referencia": referencia,
                "Responsable": responsable
            }])
            
            df_ingresos_final = pd.concat([df_ingresos, nuevo_ingreso], ignore_index=True)
            
            # 2. Actualizar el stock en el inventario maestro
            stock_actual = df_inventario.loc[df_inventario['Producto'] == producto_seleccionado, 'Stock_Actual'].iloc[0]
            nuevo_stock = stock_actual + cantidad_ingresada
            df_inventario.loc[df_inventario['Producto'] == producto_seleccionado, 'Stock_Actual'] = nuevo_stock

            # 3. Guardar ambos archivos
            exito_inv, msg_inv = guardar_datos(df_inventario, ARCHIVO_INVENTARIO)
            exito_ing, msg_ing = guardar_datos(df_ingresos_final, ARCHIVO_INGRESOS)
            
            if exito_inv and exito_ing:
                st.success(f"¡Ingreso de {cantidad_ingresada} unidades de '{producto_seleccionado}' registrado y stock actualizado!")
            else:
                st.error(f"Error al guardar. Inventario: {msg_inv}, Ingresos: {msg_ing}")
else:
    st.warning("El catálogo de productos está vacío. Por favor, añada un producto en la página de 'Inventario de Productos' antes de registrar un ingreso.")

st.divider()

# --- HISTORIAL DE INGRESOS ---
st.header("📚 Historial de Ingresos Recientes")
if not df_ingresos.empty:
    st.dataframe(df_ingresos.tail(10).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no se ha registrado ningún ingreso.")
