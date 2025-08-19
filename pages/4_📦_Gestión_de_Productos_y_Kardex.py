import json
import base64
import streamlit as st
import pandas as pd
import os
from datetime import datetime
import openpyxl 
from io import BytesIO
import gspread
from gspread_pandas import Spread, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y visualización del stock total, valorizado y detallado por lotes.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
# Ya no usamos nombres de archivos locales, sino el nombre de la Hoja de Google
SPREADSHEET_NAME = "BaseDeDatos_Fundo"
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# Añadimos la nueva columna 'Stock_Minimo' que conversamos
COLS_PRODUCTOS = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion', 'Stock_Minimo']

# Reemplaza la función de diagnóstico con esta versión final
@st.cache_resource
def get_google_sheets_client():
    SECRET_KEY_NAME = "gcp_service_account" 

    if SECRET_KEY_NAME not in st.secrets:
        st.error(f"Error: No se encontró la clave '{SECRET_KEY_NAME}' en los Secrets.")
        return None

    creds_b64_str = st.secrets[SECRET_KEY_NAME]

    try:
        creds_bytes = base64.b64decode(creds_b64_str)
        creds_json_str = creds_bytes.decode('utf-8')
        creds_dict = json.loads(creds_json_str)
        gspread_client = gspread.service_account_from_dict(creds_dict)
        return gspread_client
    except Exception as e:
        st.error("FALLO CRÍTICO AL PROCESAR LAS CREDENCIALES.", icon="🔥")
        st.code(f"Detalle técnico: {e}", language="text")
        return None
        
@st.cache_data(ttl=60) # Cachear los datos por 60 segundos
def cargar_kardex_gsheet():
    """Carga las tres hojas del Kardex desde Google Sheets."""
    try:
        client = get_google_sheets_client()
        spread = Spread(SPREADSHEET_NAME, client=client)
        
        # Leer cada hoja, si no existe, crear un DataFrame vacío
        df_productos = spread.sheet_to_df(sheet=SHEET_PRODUCTS, index=None) if SHEET_PRODUCTS in [s.title for s in spread.sheets] else pd.DataFrame(columns=COLS_PRODUCTOS)
        df_ingresos = spread.sheet_to_df(sheet=SHEET_INGRESOS, index=None) if SHEET_INGRESOS in [s.title for s in spread.sheets] else pd.DataFrame(columns=COLS_INGRESOS)
        df_salidas = spread.sheet_to_df(sheet=SHEET_SALIDAS, index=None) if SHEET_SALIDAS in [s.title for s in spread.sheets] else pd.DataFrame(columns=COLS_SALIDAS)
        
        # Convertir columnas de fecha
        if 'Fecha' in df_ingresos.columns: df_ingresos['Fecha'] = pd.to_datetime(df_ingresos['Fecha'], errors='coerce')
        if 'Fecha_Vencimiento' in df_ingresos.columns: df_ingresos['Fecha_Vencimiento'] = pd.to_datetime(df_ingresos['Fecha_Vencimiento'], errors='coerce')
        if 'Fecha' in df_salidas.columns: df_salidas['Fecha'] = pd.to_datetime(df_salidas['Fecha'], errors='coerce')

        return df_productos, df_ingresos, df_salidas
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return pd.DataFrame(columns=COLS_PRODUCTOS), pd.DataFrame(columns=COLS_INGRESOS), pd.DataFrame(columns=COLS_SALIDAS)

def guardar_kardex_gsheet(df_productos, df_ingresos, df_salidas):
    """Guarda los DataFrames en sus respectivas hojas en Google Sheets."""
    try:
        client = get_google_sheets_client()
        spread = Spread(SPREADSHEET_NAME, client=client)
        
        # Asegurarse que las columnas de fecha se guarden como texto
        df_ingresos_guardar = df_ingresos.copy()
        if 'Fecha' in df_ingresos_guardar.columns:
            df_ingresos_guardar['Fecha'] = pd.to_datetime(df_ingresos_guardar['Fecha']).dt.strftime('%Y-%m-%d')
        if 'Fecha_Vencimiento' in df_ingresos_guardar.columns:
            df_ingresos_guardar['Fecha_Vencimiento'] = pd.to_datetime(df_ingresos_guardar['Fecha_Vencimiento']).dt.strftime('%Y-%m-%d')

        df_salidas_guardar = df_salidas.copy()
        if 'Fecha' in df_salidas_guardar.columns:
            df_salidas_guardar['Fecha'] = pd.to_datetime(df_salidas_guardar['Fecha']).dt.strftime('%Y-%m-%d')

        spread.df_to_sheet(df_productos, index=False, sheet=SHEET_PRODUCTS, replace=True)
        spread.df_to_sheet(df_ingresos_guardar, index=False, sheet=SHEET_INGRESOS, replace=True)
        spread.df_to_sheet(df_salidas_guardar, index=False, sheet=SHEET_SALIDAS, replace=True)
        
        st.cache_data.clear() # Limpiar el cache para que la próxima lectura vea los cambios
        return True
    except Exception as e:
        st.error(f"Error al guardar en Google Sheets: {e}")
        return False
        
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
df_productos, df_ingresos, df_salidas = cargar_kardex_gsheet()

# --- SECCIÓN 1: CARGA INICIAL (CON NOMBRES DE COLUMNA CORREGIDOS) ---
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel", expanded=True):
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"])
    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            with st.spinner("Procesando archivo Excel..."):
                try:
                    # 1. Leer Catálogo de Productos
                    df_new_productos = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1).rename(columns={'CODIGO': 'Codigo', 'PRODUCTOS': 'Producto'})
                    df_new_productos.dropna(subset=['Codigo', 'Producto'], inplace=True)

                    # 2. Leer Stock Físico
                    df_stock_sheet = pd.read_excel(uploaded_file, sheet_name='STOCK', header=2)
                    p1 = df_stock_sheet[['PRODUCTO', 'CANT']].copy().rename(columns={'PRODUCTO': 'Producto', 'CANT': 'Cantidad'})
                    p2 = df_stock_sheet[['PRODUCTO.1', 'CANT.1']].copy().rename(columns={'PRODUCTO.1': 'Producto', 'CANT.1': 'Cantidad'})
                    p3 = df_stock_sheet[['PRODUCTO.2', 'CANT.2']].copy().rename(columns={'PRODUCTO.2': 'Producto', 'CANT.2': 'Cantidad'})
                    stock_data = pd.concat([p1, p2, p3], ignore_index=True).dropna(subset=['Producto'])
                    stock_data['Cantidad'] = pd.to_numeric(stock_data['Cantidad'], errors='coerce').fillna(0)
                    stock_data = stock_data[stock_data['Cantidad'] > 0]

                    # 3. Leer Precios Históricos usando los nombres de columna que nos diste
                    df_ingresos_historicos = pd.read_excel(uploaded_file, sheet_name='Ingreso', header=1)
                    # Usamos los nombres exactos de tu archivo
                    df_ingresos_historicos['F.DE ING.'] = pd.to_datetime(df_ingresos_historicos['F.DE ING.'])
                    df_ultimos_precios = df_ingresos_historicos.sort_values(by='F.DE ING.', ascending=False).drop_duplicates(subset=['PRODUCTOS'], keep='first')
                    df_ultimos_precios = df_ultimos_precios[['PRODUCTOS', 'PREC. UNI S/.']].rename(columns={'PRODUCTOS': 'Producto', 'PREC. UNI S/.': 'Precio_Unitario'})

                    # 4. Unir todo
                    stock_data['join_key'] = stock_data['Producto'].astype(str).str.strip().str.lower()
                    df_new_productos['join_key'] = df_new_productos['Producto'].astype(str).str.strip().str.lower()
                    df_ultimos_precios['join_key'] = df_ultimos_precios['Producto'].astype(str).str.strip().str.lower()
                    
                    df_merged = pd.merge(stock_data, df_new_productos, on='join_key', how='left')
                    df_final_merged = pd.merge(df_merged, df_ultimos_precios, on='join_key', how='left')
                    df_final_merged['Precio_Unitario'].fillna(0, inplace=True)

                    # 5. Crear lotes iniciales usando el precio encontrado
                    ingresos_list = []
                    for _, row in df_final_merged.iterrows():
                        if pd.notna(row['Codigo']):
                            ingresos_list.append({
                                'Codigo_Lote': f"{row['Codigo']}-INV-INICIAL",
                                'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Tipo': 'Ajuste de Inventario Inicial',
                                'Proveedor': row.get('PROVEEDOR', 'N/A'), 'Factura': row.get('FACTURA', 'N/A'), 
                                'Producto': row['Producto_y'],
                                'Codigo_Producto': row['Codigo'], 'Cantidad': row['Cantidad'],
                                'Precio_Unitario': row['Precio_Unitario'],
                                'Fecha_Vencimiento': None
                            })
                    
                    df_new_ingresos = pd.DataFrame(ingresos_list).drop_duplicates(subset=['Codigo_Producto'], keep='first')
                    guardar_kardex_gsheet(df_productos=df_new_productos, df_ingresos=df_new_ingresos, df_salidas=pd.DataFrame(columns=COLS_SALIDAS))
                    st.success("¡Catálogo y stock inicial (con precios) cargados exitosamente!")
                    st.rerun()

                except KeyError as e:
                    st.error(f"Error de columna: No se encontró la columna {e}. Revisa que los nombres en tu Excel sean correctos.")
                except Exception as e:
                    st.error(f"Ocurrió un error. Verifique su archivo Excel. Detalle: {e}")
                    
# --- (El resto del código se mantiene igual) ---
st.divider()
st.header("Kardex y Stock Actual")
if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Cargue el archivo inicial o añada un producto manualmente.")
else:
    df_total_stock, df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
    
    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    
    # --- AJUSTE DE ROBUSTEZ ---
    # Se asegura de mostrar solo las columnas que realmente existen para evitar KeyErrors
    columnas_a_mostrar = ['Codigo', 'Producto', 'Stock_Actual', 'Unidad', 'Stock_Valorizado']
    columnas_existentes = [col for col in columnas_a_mostrar if col in df_vista_kardex.columns]
    df_vista_kardex = df_vista_kardex[columnas_existentes]
    
    df_display = df_vista_kardex.copy()
    if 'Stock_Valorizado' in df_display.columns:
        df_display['Stock_Valorizado'] = df_display['Stock_Valorizado'].map('${:,.2f}'.format)
    if 'Stock_Actual' in df_display.columns:
        df_display['Stock_Actual'] = df_display['Stock_Actual'].map('{:,.2f}'.format)

    st.dataframe(df_display, use_container_width=True, hide_index=True)
    
    st.subheader("📥 Descargar Reportes")
    col1, col2 = st.columns(2)
    with col1:
        excel_resumen = to_excel(df_vista_kardex)
        st.download_button(label="Descargar Resumen de Stock", data=excel_resumen, file_name=f"Resumen_Stock_{datetime.now().strftime('%Y%m%d')}.xlsx")
    with col2:
        if not df_stock_lotes.empty:
            lotes_activos_full = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0.001]
            excel_detallado = to_excel(lotes_activos_full)
            st.download_button(label="Descargar Inventario Detallado por Lote", data=excel_detallado, file_name=f"Detalle_Lotes_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    st.divider()
    
    st.subheader("Ver Desglose de Lotes Activos por Producto")
    producto_seleccionado = st.selectbox("Seleccione un producto:", options=df_productos['Producto'])
    if producto_seleccionado:
        codigo_seleccionado = df_productos.loc[df_productos['Producto'] == producto_seleccionado, 'Codigo'].iloc[0]
        
        if not df_stock_lotes.empty and 'Codigo_Producto' in df_stock_lotes.columns:
            lotes_del_producto = df_stock_lotes[df_stock_lotes['Codigo_Producto'] == codigo_seleccionado]
            lotes_activos = lotes_del_producto[lotes_del_producto['Stock_Restante'] > 0.001].copy()
            
            if lotes_activos.empty:
                st.info(f"No hay lotes con stock activo para '{producto_seleccionado}'.")
            else:
                lotes_activos['Precio_Unitario'] = lotes_activos['Precio_Unitario'].map('${:,.2f}'.format)
                lotes_activos['Stock_Restante'] = lotes_activos['Stock_Restante'].map('{:,.2f}'.format)
                lotes_activos['Valor_Lote'] = lotes_activos['Valor_Lote'].map('${:,.2f}'.format)
                st.dataframe(lotes_activos[['Codigo_Lote', 'Stock_Restante', 'Precio_Unitario', 'Valor_Lote', 'Fecha_Vencimiento']], use_container_width=True, hide_index=True)
