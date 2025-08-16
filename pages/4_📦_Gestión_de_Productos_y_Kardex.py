import streamlit as st
import pandas as pd
import os
from datetime import datetime
import openpyxl 
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y visualización del stock total, valorizado y detallado por lotes.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

COLS_PRODUCTOS = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
COLS_INGRESOS = ['Codigo_Lote', 'Fecha', 'Tipo', 'Proveedor', 'Factura', 'Producto', 'Codigo_Producto', 'Cantidad', 'Precio_Unitario', 'Fecha_Vencimiento']
COLS_SALIDAS = ['Fecha', 'Lote_Sector', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento', 'Codigo_Lote']

# --- FUNCIONES CORE DEL KARDEX ---
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
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index()
    total_stock_producto = total_stock_producto.rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    return total_stock_producto, stock_lotes_detallado

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA INICIAL DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- SECCIÓN 1: CARGA INICIAL (VERSIÓN FINAL) ---
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel", expanded=True):
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"])
    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            with st.spinner("Procesando archivo Excel..."):
                try:
                    df_new_productos = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1).rename(columns={'CODIGO': 'Codigo', 'PRODUCTOS': 'Producto', 'ING. ACTIVO': 'Ingrediente_Activo', 'UM': 'Unidad', 'PROVEEDOR': 'Proveedor', 'SUBGRUPO': 'Tipo_Accion'})
                    df_new_productos.dropna(subset=['Codigo', 'Producto'], inplace=True)

                    df_stock_sheet = pd.read_excel(uploaded_file, sheet_name='STOCK', header=2)
                    
                    # Unificar las tres secciones de la hoja STOCK
                    p1 = df_stock_sheet[['PRODUCTO', 'CANT']].copy().rename(columns={'PRODUCTO': 'Producto', 'CANT': 'Cantidad'})
                    p2 = df_stock_sheet[['PRODUCTO.1', 'CANT.1']].copy().rename(columns={'PRODUCTO.1': 'Producto', 'CANT.1': 'Cantidad'})
                    p3 = df_stock_sheet[['PRODUCTO.2', 'CANT.2']].copy().rename(columns={'PRODUCTO.2': 'Producto', 'CANT.2': 'Cantidad'})
                    
                    stock_data = pd.concat([p1, p2, p3], ignore_index=True)
                    stock_data.dropna(subset=['Producto'], inplace=True)
                    stock_data['Cantidad'] = pd.to_numeric(stock_data['Cantidad'], errors='coerce').fillna(0)
                    stock_data = stock_data[stock_data['Cantidad'] > 0]
                    
                    # Asociar stock con productos usando una llave limpia
                    stock_data['join_key'] = stock_data['Producto'].astype(str).str.strip().str.lower()
                    df_new_productos['join_key'] = df_new_productos['Producto'].astype(str).str.strip().str.lower()
                    
                    df_merged = pd.merge(stock_data, df_new_productos, on='join_key', how='left')
                    
                    # Crear registros de lote para el inventario inicial
                    ingresos_list = []
                    for _, row in df_merged.iterrows():
                        if pd.notna(row['Codigo']):
                            ingresos_list.append({
                                'Codigo_Lote': f"{row['Codigo']}-INV-INICIAL",
                                'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Tipo': 'Ajuste de Inventario Inicial',
                                'Proveedor': 'N/A', 'Factura': 'N/A', 'Producto': row['Producto_y'],
                                'Codigo_Producto': row['Codigo'], 'Cantidad': row['Cantidad'],
                                'Precio_Unitario': 0.0, 'Fecha_Vencimiento': None
                            })
                    
                    df_new_ingresos = pd.DataFrame(ingresos_list).drop_duplicates(subset=['Codigo_Producto'], keep='first')
                    
                    guardar_kardex(df_productos=df_new_productos, df_ingresos=df_new_ingresos, df_salidas=pd.DataFrame(columns=COLS_SALIDAS))
                    st.success("¡Catálogo y stock inicial cargados exitosamente!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocurrió un error. Verifique su archivo Excel. Detalle: {e}")

# --- (El resto del código se mantiene igual) ---
st.divider()
st.header("Kardex y Stock Actual")
# ... (código para mostrar la tabla de kardex)
# ... (código para los botones de descarga)
# ... (código para el desglose de lotes)
