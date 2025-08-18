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
    """Calcula el stock detallado por lote y el total por producto."""
    if df_ingresos.empty:
        # Devuelve dataframes vacíos con la estructura de columnas completa para evitar errores
        cols_totales = ['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']
        cols_lotes = ['Codigo_Lote', 'Stock_Restante', 'Valor_Lote', 'Codigo_Producto', 'Producto', 'Fecha_Vencimiento', 'Precio_Unitario']
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
    
    if 'Precio_Unitario' not in stock_lotes_detallado.columns:
        stock_lotes_detallado['Precio_Unitario'] = 0
        
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    
    agg_funcs = {'Stock_Restante': 'sum', 'Valor_Lote': 'sum'}
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index().rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    
    return total_stock_producto, stock_lotes_detallado

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA INICIAL DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- SECCIÓN 1: DIAGNÓSTICO DE CARGA INICIAL ---
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel", expanded=True):
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"])
    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            try:
                st.subheader("🕵️‍♂️ Iniciando Diagnóstico de Columnas...")
                
                # Cargar la hoja 'Ingreso' y mostrar las columnas TAL CUAL las lee pandas
                st.write("1. Leyendo la hoja 'Ingreso' con encabezado en la segunda fila...")
                df_ingresos_debug = pd.read_excel(uploaded_file, sheet_name='Ingreso', header=1)
                
                st.write("2. Estas son las columnas que se encontraron (antes de cualquier limpieza):")
                # Usamos st.code para ver la lista exacta, incluyendo espacios o caracteres raros
                st.code(df_ingresos_debug.columns.to_list())
                
                st.warning("Por favor, copia la lista de columnas que aparece en el cuadro de arriba y pégala en el chat.")
                st.info("El problema es que el nombre 'FECHA' no se encuentra exactamente como se esperaba en esa lista. Con la lista que me envíes, lo corregiré al instante.")

            except Exception as e:
                st.error(f"Ocurrió un error incluso durante el diagnóstico: {e}")
                    
# --- (El resto del código se mantiene igual) ---
st.divider()
st.header("Kardex y Stock Actual")
if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Cargue el archivo inicial o añada un producto manualmente.")
else:
    df_total_stock, df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
    
    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    
    df_vista_kardex = df_vista_kardex[['Codigo', 'Producto', 'Stock_Actual', 'Unidad', 'Stock_Valorizado']]
    
    df_display = df_vista_kardex.copy()
    df_display['Stock_Valorizado'] = df_display['Stock_Valorizado'].map('${:,.2f}'.format)
    df_display['Stock_Actual'] = df_display['Stock_Actual'].map('{:,.2f}'.format)

    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.subheader("📥 Descargar Reportes")
    col1, col2 = st.columns(2)
    with col1:
        excel_resumen = to_excel(df_vista_kardex)
        st.download_button(label="Descargar Resumen de Stock", data=excel_resumen, file_name=f"Resumen_Stock_{datetime.now().strftime('%Y%m%d')}.xlsx")
    with col2:
        lotes_activos_full = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0.001]
        excel_detallado = to_excel(lotes_activos_full)
        st.download_button(label="Descargar Inventario Detallado por Lote", data=excel_detallado, file_name=f"Detalle_Lotes_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    st.divider()
    
    st.subheader("Ver Desglose de Lotes Activos por Producto")
    producto_seleccionado = st.selectbox("Seleccione un producto:", options=df_productos['Producto'])
    if producto_seleccionado:
        codigo_seleccionado = df_productos.loc[df_productos['Producto'] == producto_seleccionado, 'Codigo'].iloc[0]
        
        lotes_del_producto = df_stock_lotes[df_stock_lotes['Codigo_Producto'] == codigo_seleccionado]
        lotes_activos = lotes_del_producto[lotes_del_producto['Stock_Restante'] > 0.001].copy()
        
        if lotes_activos.empty:
            st.info(f"No hay lotes con stock activo para '{producto_seleccionado}'.")
        else:
            lotes_activos['Precio_Unitario'] = lotes_activos['Precio_Unitario'].map('${:,.2f}'.format)
            lotes_activos['Stock_Restante'] = lotes_activos['Stock_Restante'].map('{:,.2f}'.format)
            lotes_activos['Valor_Lote'] = lotes_activos['Valor_Lote'].map('${:,.2f}'.format)
            st.dataframe(lotes_activos[['Codigo_Lote', 'Stock_Restante', 'Precio_Unitario', 'Valor_Lote', 'Fecha_Vencimiento']], use_container_width=True, hide_index=True)
