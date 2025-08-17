import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time, timedelta
from io import BytesIO
import openpyxl 
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Inventario y Operaciones", page_icon="📦", layout="wide")
st.title("📦 Centro de Inventario y Operaciones")
st.write("Gestiona tu inventario por lotes, registra ingresos y controla todo el flujo de aplicaciones desde un solo lugar.")

# --- NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'
ARCHIVO_HORAS = 'Registro_Horas_Tractor.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# --- DEFINICIÓN DE COLUMNAS (GLOBAL) ---
COLS_PRODUCTOS = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
COLS_INGRESOS = ['Codigo_Lote', 'Fecha', 'Tipo', 'Proveedor', 'Factura', 'Producto', 'Codigo_Producto', 'Cantidad', 'Precio_Unitario', 'Fecha_Vencimiento']
COLS_SALIDAS = ['Fecha', 'Lote_Sector', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento', 'Codigo_Lote']

# --- FUNCIONES CORE (CENTRALIZADAS) ---
def cargar_kardex():
    if os.path.exists(KARDEX_FILE):
        try:
            xls = pd.ExcelFile(KARDEX_FILE)
            df_productos = pd.read_excel(xls, sheet_name=SHEET_PRODUCTS) if SHEET_PRODUCTS in xls.sheet_names else pd.DataFrame(columns=COLS_PRODUCTOS)
            df_ingresos = pd.read_excel(xls, sheet_name=SHEET_INGRESOS) if SHEET_INGRESOS in xls.sheet_names else pd.DataFrame(columns=COLS_INGRESOS)
            df_salidas = pd.read_excel(xls, sheet_name=SHEET_SALIDAS) if SHEET_SALIDAS in xls.sheet_names else pd.DataFrame(columns=COLS_SALIDAS)
        except Exception as e:
            st.error(f"Error al leer el archivo Kardex: {e}")
            return pd.DataFrame(columns=COLS_PRODUCTOS), pd.DataFrame(columns=COLS_INGRESOS), pd.DataFrame(columns=COLS_SALIDAS)
    else:
        return pd.DataFrame(columns=COLS_PRODUCTOS), pd.DataFrame(columns=COLS_INGRESOS), pd.DataFrame(columns=COLS_SALIDAS)
    return df_productos, df_ingresos, df_salidas

def guardar_kardex(df_productos, df_ingresos, df_salidas):
    with pd.ExcelWriter(KARDEX_FILE, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name=SHEET_PRODUCTS, index=False)
        df_ingresos.to_excel(writer, sheet_name=SHEET_INGRESOS, index=False)
        df_salidas.to_excel(writer, sheet_name=SHEET_SALIDAS, index=False)
    return True

def calcular_stock_por_lote(df_ingresos, df_salidas):
    if df_ingresos.empty:
        cols_totales = ['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']
        cols_lotes = ['Codigo_Lote', 'Stock_Restante', 'Valor_Lote', 'Codigo_Producto']
        return pd.DataFrame(columns=cols_totales), pd.DataFrame(columns=cols_lotes)
    ingresos_por_lote = df_ingresos.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Ingresada'})
    if not df_salidas.empty and 'Codigo_Lote' in df_salidas.columns:
        salidas_por_lote = df_salidas.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Consumida'})
        stock_lotes = pd.merge(ingresos_por_lote, salidas_por_lote, on='Codigo_Lote', how='left').fillna(0)
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada'] - stock_lotes['Cantidad_Consumida']
    else:
        stock_lotes = ingresos_por_lote
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada']
    lote_info = df_ingresos.drop_duplicates(subset=['Codigo_Lote'])[['Codigo_Lote', 'Codigo_Producto', 'Producto', 'Precio_Unitario', 'Fecha_Vencimiento']]
    stock_lotes_detallado = pd.merge(stock_lotes, lote_info, on='Codigo_Lote', how='left')
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    agg_funcs = {'Stock_Restante': 'sum', 'Valor_Lote': 'sum'}
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index().rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    return total_stock_producto, stock_lotes_detallado

def cargar_datos_genericos(nombre_archivo, columnas_defecto=None):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    return pd.DataFrame(columns=columnas_defecto if columnas_defecto is not None else [])

def guardar_datos_genericos(df, nombre_archivo):
    df.to_excel(nombre_archivo, index=False, engine='openpyxl')
    return True

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA DE DATOS PRINCIPAL (UNA SOLA VEZ) ---
df_productos, df_ingresos, df_salidas = cargar_kardex()
df_ordenes = cargar_datos_genericos(ORDENES_FILE, ['ID_Orden', 'Status'])
df_horas = cargar_datos_genericos(ARCHIVO_HORAS, [])

# --- CREACIÓN DE PESTAÑAS ---
tab_kardex, tab_ingreso, tab_mezclas, tab_aplicacion = st.tabs([
    "📊 Kardex y Productos", 
    "📥 Registrar Ingreso", 
    "⚗️ Gestión de Mezclas", 
    "🚜 Gestión de Aplicación"
])

# --- PESTAÑA 1: KARDEX Y PRODUCTOS ---
with tab_kardex:
    st.header("Visión General del Inventario")
    
    with st.expander("⬆️ Cargar Catálogo Inicial desde Excel"):
        st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
        uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"], key="main_uploader")
        if st.button("Procesar Archivo Excel Completo"):
            if uploaded_file:
                with st.spinner("Procesando archivo Excel..."):
                    try:
                        # ... Lógica completa de procesamiento de Excel ...
                        st.success("¡Catálogo y stock inicial cargados exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ocurrió un error. Verifique su archivo Excel. Detalle: {e}")

    with st.expander("➕ Añadir Nuevo Producto al Catálogo"):
        with st.form("nuevo_producto_form", clear_on_submit=True):
            st.subheader("Datos del Nuevo Producto")
            codigo = st.text_input("Código de Producto (único)")
            producto = st.text_input("Nombre Comercial del Producto")
            ing_activo = st.text_input("Ingrediente Activo")
            unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL", "Unidad"])
            proveedor = st.text_input("Proveedor Principal")
            tipo_accion = st.selectbox("Tipo de Acción / Subgrupo", ["FUNGICIDA", "INSECTICIDA", "HERBICIDA", "FERTILIZANTE", "COADYUVANTE", "OTRO"])
            submitted_nuevo = st.form_submit_button("Añadir Producto al Catálogo")
            if submitted_nuevo:
                if codigo and producto:
                    # ... Lógica para guardar el nuevo producto ...
                    st.success(f"¡Producto '{producto}' añadido al catálogo!")
                    st.rerun()

    st.divider()

    st.subheader("Kardex y Stock Actual")
    if df_productos.empty:
        st.warning("El catálogo de productos está vacío.")
    else:
        # ... Lógica para mostrar el kardex, descargas y desglose por lote ...
        pass

# --- PESTAÑA 2: REGISTRAR INGRESO ---
with tab_ingreso:
    st.header("Registrar Ingreso de Mercadería por Lote")
    if df_productos.empty:
        st.error("Catálogo de productos vacío. Añada productos en la pestaña de Kardex.")
    else:
        with st.form("ingreso_lote_form", clear_on_submit=True):
            # ... Contenido completo del formulario de 6_..._Ingreso.py ...
            if st.form_submit_button("✅ Guardar Ingreso del Lote"):
                # ... Lógica de guardado de lote ...
                st.success("¡Lote registrado!")
                st.rerun()
# --- PESTAÑA 3: GESTIÓN DE MEZCLAS ---
with tab_mezclas:
    st.header("Gestionar y Programar Mezclas de Aplicación")
    # (Aquí va el código completo de la página 7_...Gestión_de_Mezclas.py)
    # Ejemplo del formulario:
    with st.expander("👨‍🔬 Programar Nueva Receta de Mezcla"):
        with st.form("programar_form"):
            # ... (código del formulario de mezclas)
            if st.form_submit_button("✅ Programar Orden de Mezcla"):
                # ... (lógica de guardado de orden)
                st.success("¡Orden programada!")
    
    st.divider()
    st.subheader("📋 Recetas Pendientes de Preparar")
    # (Aquí va la lógica para mostrar y confirmar mezclas pendientes)

# --- PESTAÑA 4: GESTIÓN DE APLICACIÓN ---
with tab_aplicacion:
    st.header("Finalizar Aplicaciones y Registrar Horas de Tractor")
    # (Aquí va el código completo de la página 8_...Gestión_de_Aplicación_y_Horas.py)
    st.subheader("✅ Tareas Listas para Aplicar")
    # (Lógica para mostrar y finalizar tareas)
    
    st.divider()
    st.subheader("📚 Historiales")
    # (Historial de horas y aplicaciones)
