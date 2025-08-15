import streamlit as st
import pandas as pd
import os
from datetime import datetime
import openpyxl

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso por Lote", page_icon="📥", layout="wide")
st.title("📥 Registrar Ingreso de Mercadería por Lote")
st.write("Registre cada compra o ingreso como un lote único con su propio costo y fecha de vencimiento.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# --- FUNCIONES CORE DEL KARDEX ---
# Estas funciones son las mismas que en el módulo de Kardex para mantener la consistencia.
def cargar_kardex():
    """
    Carga todas las hojas del archivo Kardex. Si no existen, crea DataFrames vacíos.
    """
    if os.path.exists(KARDEX_FILE):
        try:
            xls = pd.ExcelFile(KARDEX_FILE)
            df_productos = pd.read_excel(xls, sheet_name=SHEET_PRODUCTS)
            df_ingresos = pd.read_excel(xls, sheet_name=SHEET_INGRESOS)
            df_salidas = pd.read_excel(xls, sheet_name=SHEET_SALIDAS)
        except Exception as e:
            st.error(f"Error al leer el archivo Kardex: {e}")
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    else:
        st.warning("Archivo 'kardex_fundo.xlsx' no encontrado. Por favor, cargue primero el catálogo de productos.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    return df_productos, df_ingresos, df_salidas

def guardar_kardex(df_productos, df_ingresos, df_salidas):
    """
    Guarda todos los dataframes en un único archivo Excel con múltiples hojas.
    """
    with pd.ExcelWriter(KARDEX_FILE, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name=SHEET_PRODUCTS, index=False)
        df_ingresos.to_excel(writer, sheet_name=SHEET_INGRESOS, index=False)
        df_salidas.to_excel(writer, sheet_name=SHEET_SALIDAS, index=False)
    return True

# --- CARGA DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- INTERFAZ DE REGISTRO DE INGRESO ---
st.subheader("📝 Nuevo Registro de Lote")

if df_productos.empty:
    st.error("No se pueden registrar ingresos porque el catálogo de productos está vacío.")
    st.info("Por favor, vaya a la página '📦 Gestión de Productos y Kardex' y añada al menos un producto.")
else:
    with st.form("ingreso_lote_form", clear_on_submit=True):
        st.markdown("##### 1. Información del Producto")
        
        # Selección del producto
        producto_seleccionado = st.selectbox(
            "Seleccione el Producto que ingresa:",
            options=df_productos['Producto'].unique()
        )
        
        # Cantidad
        cantidad_ingresada = st.number_input("Cantidad Ingresada (en la unidad del producto)", min_value=0.01, format="%.2f")

        st.markdown("##### 2. Información del Lote (Costo y Caducidad)")
        col1, col2 = st.columns(2)
        with col1:
            precio_unitario = st.number_input("Precio Unitario (Costo por Unidad)", min_value=0.00, format="%.2f", help="El costo de compra de una unidad (Kg, L, etc.) de este lote.")
        with col2:
            fecha_vencimiento = st.date_input("Fecha de Vencimiento (Opcional)", value=None)

        st.markdown("##### 3. Documentación de Soporte")
        col3, col4, col5 = st.columns(3)
        with col3:
            fecha_ingreso = st.date_input("Fecha de Ingreso", datetime.now())
        with col4:
            proveedor = st.text_input("Proveedor")
        with col5:
            factura = st.text_input("Factura / Guía de Remisión")
        
        submitted = st.form_submit_button("✅ Guardar Ingreso del Lote")

        if submitted:
            # --- LÓGICA DE GUARDADO DEL LOTE ---
            
            # Obtener el código del producto seleccionado
            codigo_producto = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
            
            # Generar un código de lote único
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            codigo_lote = f"{codigo_producto}-{timestamp}"
            
            # Crear el nuevo registro como un DataFrame
            nuevo_ingreso_data = {
                'Codigo_Lote': codigo_lote,
                'Fecha': fecha_ingreso.strftime("%Y-%m-%d"),
                'Tipo': 'Ingreso por Compra',
                'Proveedor': proveedor,
                'Factura': factura,
                'Producto': producto_seleccionado,
                'Codigo_Producto': codigo_producto,
                'Cantidad': cantidad_ingresada,
                'Precio_Unitario': precio_unitario,
                'Fecha_Vencimiento': fecha_vencimiento.strftime("%Y-%m-%d") if fecha_vencimiento else None
            }
            df_nuevo_ingreso = pd.DataFrame([nuevo_ingreso_data])
            
            # Unir con el historial de ingresos existente
            df_ingresos_actualizado = pd.concat([df_ingresos, df_nuevo_ingreso], ignore_index=True)
            
            # Guardar el archivo kardex completo
            exito = guardar_kardex(df_productos, df_ingresos_actualizado, df_salidas)
            
            if exito:
                st.success(f"¡Lote '{codigo_lote}' para el producto '{producto_seleccionado}' registrado exitosamente!")
            else:
                st.error("Hubo un error al guardar el registro en el archivo Kardex.")

st.divider()

# --- HISTORIAL DE INGRESOS RECIENTES ---
st.header("📚 Historial de Ingresos Recientes")
if not df_ingresos.empty:
    # Mostramos las columnas más relevantes
    columnas_a_mostrar = [
        'Fecha', 'Producto', 'Cantidad', 'Precio_Unitario', 
        'Codigo_Lote', 'Proveedor', 'Factura', 'Fecha_Vencimiento'
    ]
    # Filtramos para asegurarnos que solo mostramos columnas que existen
    columnas_existentes = [col for col in columnas_a_mostrar if col in df_ingresos.columns]
    st.dataframe(df_ingresos[columnas_existentes].tail(15).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no se ha registrado ningún ingreso.")
