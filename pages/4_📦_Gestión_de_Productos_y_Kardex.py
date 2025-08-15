import streamlit as st
import pandas as pd
import os
from datetime import datetime
import openpyxl 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y visualización del stock total y detallado por lotes.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# --- FUNCIONES CORE DEL KARDEX ---
def cargar_kardex():
    # Define las columnas esperadas para cada hoja para crear DataFrames vacíos si es necesario
    cols_productos = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
    cols_ingresos = ['Codigo_Lote', 'Fecha', 'Tipo', 'Proveedor', 'Factura', 'Producto', 'Codigo_Producto', 'Cantidad', 'Precio_Unitario', 'Fecha_Vencimiento']
    cols_salidas = ['Fecha', 'Lote_Sector', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento', 'Codigo_Lote']

    if os.path.exists(KARDEX_FILE):
        try:
            xls = pd.ExcelFile(KARDEX_FILE)
            df_productos = pd.read_excel(xls, sheet_name=SHEET_PRODUCTS)
            df_ingresos = pd.read_excel(xls, sheet_name=SHEET_INGRESOS)
            df_salidas = pd.read_excel(xls, sheet_name=SHEET_SALIDAS)
        except Exception as e:
            st.error(f"Error al leer el archivo Kardex: {e}")
            return pd.DataFrame(columns=cols_productos), pd.DataFrame(columns=cols_ingresos), pd.DataFrame(columns=cols_salidas)
    else:
        return pd.DataFrame(columns=cols_productos), pd.DataFrame(columns=cols_ingresos), pd.DataFrame(columns=cols_salidas)
    return df_productos, df_ingresos, df_salidas


def guardar_kardex(df_productos, df_ingresos, df_salidas):
    with pd.ExcelWriter(KARDEX_FILE, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name=SHEET_PRODUCTS, index=False)
        df_ingresos.to_excel(writer, sheet_name=SHEET_INGRESOS, index=False)
        df_salidas.to_excel(writer, sheet_name=SHEET_SALIDAS, index=False)
    return True

def calcular_stock_por_lote(df_ingresos, df_salidas):
    """
    Calcula el stock restante para cada lote y el stock total para cada producto.
    """
    # Suma de ingresos por lote
    ingresos_por_lote = df_ingresos.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Ingresada'})

    # Suma de salidas por lote (si la columna Codigo_Lote ya existe en Salidas)
    if not df_salidas.empty and 'Codigo_Lote' in df_salidas.columns:
        salidas_por_lote = df_salidas.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Consumida'})
        stock_lotes = pd.merge(ingresos_por_lote, salidas_por_lote, on='Codigo_Lote', how='left').fillna(0)
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada'] - stock_lotes['Cantidad_Consumida']
    else:
        # Si no hay salidas registradas por lote, el stock restante es el total ingresado
        stock_lotes = ingresos_por_lote
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada']

    # Añadir información detallada de cada lote (precio, fecha venc., etc.)
    lote_info = df_ingresos.drop_duplicates(subset=['Codigo_Lote'])[['Codigo_Lote', 'Codigo_Producto', 'Producto', 'Precio_Unitario', 'Fecha_Vencimiento']]
    stock_lotes_detallado = pd.merge(stock_lotes, lote_info, on='Codigo_Lote', how='left')

    # Calcular el stock total por producto sumando el restante de sus lotes
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto')['Stock_Restante'].sum().reset_index().rename(columns={'Stock_Restante': 'Stock_Actual'})
    
    return total_stock_producto, stock_lotes_detallado


# --- CARGA DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- INTERFAZ DE USUARIO ---
# (Las secciones de Carga Inicial y Añadir Nuevo Producto no cambian y se omiten por brevedad, pero deben permanecer en tu archivo)
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel"):
    # (Este código no cambia)
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"], key="kardex_uploader")
    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            # (Lógica de procesamiento del excel aquí, no ha cambiado)
            st.success("Procesado (lógica simulada)")

with st.expander("➕ Añadir un Nuevo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        # (Este código no cambia)
        st.subheader("Datos del Nuevo Producto")
        st.text_input("Código de Producto (único)")
        st.form_submit_button("Añadir Producto al Catálogo")

st.divider()

# --- SECCIÓN 3: VISUALIZACIÓN DEL KARDEX (MODIFICADA) ---
st.header("Kardex y Stock Actual")

if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Añada un producto manualmente o cargue el catálogo inicial.")
else:
    # Calcular stock total y por lote
    df_total_stock, df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
    
    # Unir catálogo con stock total para la vista principal
    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    df_vista_kardex = df_vista_kardex[['Codigo', 'Producto', 'Stock_Actual', 'Unidad', 'Tipo_Accion', 'Proveedor']]

    st.info("El stock total es la suma de todos los lotes activos de un producto.")
    
    # Filtro para la tabla principal
    filtro_texto = st.text_input("Buscar producto por nombre o código:")
    if filtro_texto:
        df_vista_kardex_filtrada = df_vista_kardex[
            df_vista_kardex['Producto'].str.contains(filtro_texto, case=False) |
            df_vista_kardex['Codigo'].str.contains(filtro_texto, case=False)
        ]
    else:
        df_vista_kardex_filtrada = df_vista_kardex

    st.dataframe(df_vista_kardex_filtrada, use_container_width=True, hide_index=True)
    
    st.divider()
    
    # --- !! NUEVA SECCIÓN: DESGLOSE DE LOTES !! ---
    st.subheader("Ver Desglose de Lotes Activos por Producto")
    producto_seleccionado = st.selectbox(
        "Seleccione un producto para ver el detalle de sus lotes:",
        options=df_productos['Producto']
    )

    if producto_seleccionado:
        codigo_seleccionado = df_productos.loc[df_productos['Producto'] == producto_seleccionado, 'Codigo'].iloc[0]
        
        # Filtrar los lotes para el producto seleccionado
        lotes_del_producto = df_stock_lotes[df_stock_lotes['Codigo_Producto'] == codigo_seleccionado]
        
        # Mostrar solo lotes con stock restante
        lotes_activos = lotes_del_producto[lotes_del_producto['Stock_Restante'] > 0.001].copy() # Usar un umbral pequeño para evitar problemas de punto flotante
        
        if lotes_activos.empty:
            st.info(f"No hay lotes con stock activo para '{producto_seleccionado}'.")
        else:
            # Formatear columnas para mejor visualización
            lotes_activos['Precio_Unitario'] = lotes_activos['Precio_Unitario'].map('${:,.2f}'.format)
            lotes_activos['Stock_Restante'] = lotes_activos['Stock_Restante'].map('{:,.2f}'.format)
            
            st.dataframe(
                lotes_activos[['Codigo_Lote', 'Stock_Restante', 'Precio_Unitario', 'Fecha_Vencimiento']],
                use_container_width=True,
                hide_index=True
            )
