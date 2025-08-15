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

# --- !! AJUSTE CLAVE !!: Definición de columnas movida aquí para ser global ---
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
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual']), pd.DataFrame()
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
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto')['Stock_Restante'].sum().reset_index().rename(columns={'Stock_Restante': 'Stock_Actual'})
    return total_stock_producto, stock_lotes_detallado

# --- CARGA INICIAL DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- SECCIÓN 1: CARGA INICIAL ---
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel", expanded=True):
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"])
    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            with st.spinner("Procesando archivo Excel..."):
                try:
                    df_new_productos = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1)
                    df_new_productos = df_new_productos.rename(columns={'CODIGO': 'Codigo', 'PRODUCTOS': 'Producto', 'ING. ACTIVO': 'Ingrediente_Activo', 'UM': 'Unidad', 'PROVEEDOR': 'Proveedor', 'SUBGRUPO': 'Tipo_Accion'})
                    df_new_productos.dropna(subset=['Codigo', 'Producto'], inplace=True)

                    df_stock_sheet = pd.read_excel(uploaded_file, sheet_name='STOCK', header=2)
                    
                    df1 = df_stock_sheet[['PRODUCTO', 'CANT']].copy()
                    df2 = df_stock_sheet[['PRODUCTO.1', 'CANT.1']].rename(columns={'PRODUCTO.1': 'PRODUCTO', 'CANT.1': 'CANT'})
                    df3 = df_stock_sheet[['PRODUCTO.2', 'CANT.2']].rename(columns={'PRODUCTO.2': 'PRODUCTO', 'CANT.2': 'CANT'})
                    df_stock_total = pd.concat([df1, df2, df3], ignore_index=True).dropna(subset=['PRODUCTO'])
                    
                    df_stock_total['CANT'] = pd.to_numeric(df_stock_total['CANT'], errors='coerce')
                    df_stock_total.fillna({'CANT': 0}, inplace=True)
                    df_stock_total = df_stock_total[df_stock_total['CANT'] > 0]

                    df_merged = pd.merge(df_stock_total, df_new_productos, left_on='PRODUCTO', right_on='Producto', how='left')
                    
                    df_new_ingresos_list = []
                    productos_no_encontrados = []
                    for _, row in df_merged.iterrows():
                        if pd.notna(row['Codigo']):
                            ingreso_data = {
                                'Codigo_Lote': f"{row['Codigo']}-INV-INICIAL",
                                'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Tipo': 'Ajuste de Inventario Inicial',
                                'Proveedor': 'N/A', 'Factura': 'N/A', 'Producto': row['Producto'],
                                'Codigo_Producto': row['Codigo'], 'Cantidad': row['CANT'],
                                'Precio_Unitario': 0.0, 'Fecha_Vencimiento': None
                            }
                            df_new_ingresos_list.append(ingreso_data)
                        else:
                            productos_no_encontrados.append(row['PRODUCTO'])
                    
                    if productos_no_encontrados:
                        st.warning(f"Productos en 'STOCK' pero no en 'Cod_Producto': {', '.join(productos_no_encontrados)}")

                    df_new_ingresos = pd.DataFrame(df_new_ingresos_list).drop_duplicates(subset=['Codigo_Producto'], keep='first')
                    
                    # Usa la variable COLS_SALIDAS globalmente definida
                    guardar_kardex(df_productos=df_new_productos, df_ingresos=df_new_ingresos, df_salidas=pd.DataFrame(columns=COLS_SALIDAS))
                    st.success("¡Catálogo y stock inicial cargados exitosamente!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocurrió un error. Verifique su archivo Excel. Detalle: {e}")
        else:
            st.warning("Por favor, suba su archivo Excel para continuar.")

# El resto del archivo no ha cambiado
# ... (código para añadir producto y vista de kardex) ...
