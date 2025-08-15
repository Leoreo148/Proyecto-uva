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
# (Las secciones de Carga Inicial y Añadir Nuevo Producto no cambian y se omiten por brevedad, pero deben permanecer en tu
