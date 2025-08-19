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

# (Asegúrate de tener todas las importaciones necesarias al inicio de tu archivo:
# streamlit, json, base64, gspread, pandas, etc.)

# (Asegúrate de tener todas las importaciones: streamlit, json, base64, etc.)

@st.cache_resource
def get_google_sheets_client():
    """
    VERSIÓN DE DIAGNÓSTICO:
    Usa una credencial hardcodeada para aislar el problema.
    """
    # --- INICIO DE LA PRUEBA DE DIAGNÓSTICO ---
    # ADVERTENCIA: ....
    # ¡RECUERDA BORRAR ESTO DESPUÉS!

    creds_b64_str_temporal = "ewogICJ0eXBlIjogInNlcnZpY2VfYWNjb3VudCIsCiAgInByb2plY3RfaWQiOiAibXktcHJvamVjdC01MDI3My00Njk1MTQiLAogICJwcml2YXRlX2tleV9pZCI6ICI2OTdjZjdlYjM5OWY4MTNiYWRkYWY4NjkxMWQ5OGVkYjQ4NGFiMTY2IiwKICAicHJpdmF0ZV9rZXkiOiAiLS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tXG5NSUlFdmdJQkFEQU5CZ2txaGtpRzl3MEJBUUVGQUFTQ0JLZ3dnZ1NrQWdFQUFvSUJBUUN5YmFydE12NlRIb3JOXG5QaGdqU2lSNGRTYnJoNVovK3VHLzVFQ2hlTmdzMXNNWU5Xa2V0dTYrMUpQblcvN2JTRWJDSkdEdm44NkRGWEFSXG5VbElLTlN2TW9yMFJoS09BbDNzd1dyRjZtZ2lsMitlTkpLRFhRME55NTdjc0o4UW9wbzJkWXNpd1k1bitEdkNNXG5pR2h3eEE1Ry9SR3Z0V285aEsyeUVRTFhCdXZ4cCtjMXQzc3FPcDhBMTdlL1Y5dVFmM0VtUHBseWdya290WVhUXG5tbEozNFRpMFdjMTM0Wk1zWno0bjRDVG56K2FNWW5OZXNLYTNIL3NST0tUKzBaVW9jQmZUZmltbjlyR0FjQ1A2XG5qbVpkNnVlS1REeDMzNUoyQXAxR2J5dDdMd0t6dk51VU9lT1YwY2Nkck5CZGtXYUZ3clYvVUdmVlVXZ2FVdHgxXG5Ha0xmOEpQdEFnTUJBQUVDZ2dFQUxhM1oxb1A1bkp4ekdIeFBIYW03a0lNZGhhcmVvc0VOemx5WEZ6K2l5RWZyXG5CbVdXRmVEcldqdDk2ZnNwVWVZOUJ6TGRCanU1V09IQ0lRMGNKN1RaRTdpT0F0QWNNNjJVUWhyVjJQZGFRMnY2XG42YTE0NStNMmYxSkhHS3pOa1VLaWVxcHhpb2JWUTY5N2NkN3lMZnhqVTFVeWsvTXowYkFINzlCZkU4R1g0Zk9XXG55TmRXRkVkbVZvejgwd2daRlgvb1BhMHVTN1Q5bW1TNWpHejJpVVE3L3c1UHJpZWkrcHB1VHdQMHQwamRyUnJXXG5PUXMxY3dkZFZqSWJDK1U2UWI4Z2RZa1FxZXB6ZGRYTk9qb2RiRFpMVzNVMUtubkcrK1RGSDI5NjRxS2xVRkx1XG4zU1Vjc1JiNk8vQklRcHB0Umdoem9jci9uZm4wN05FRFdQWGJJcm42bVFLQmdRRGNMTThiLzk3cHNEMnhQWkZOXG5iWWluaVRHQURpdHZoWjBCckpIYmNOZGdPNDZPc2krOHJESzRwNTVJVDZSVjdwYWY4T3A4MzZBRGJmWmhKRnAwXG5aZEFPU2RBcS9FdFlSUS9hTkR0K0V4QWFlaEhSV3A2bVlGNlNLYllTdzRsbSthV1JpSXZxWVcxQ1FzWS92cFMzXG5lZE1WN05VWTJZSlE0OGxza2NhQ1RmNVZ2d0tCZ1FEUGRmQ29lSndPc29uTTVHUEZ6ZDZ2Q2s3TkJ1bFJaY2lvXG5CWnd0ME5SNzdWeG1PUGJ3anRUVzVXSStVWmU2NGJlaWEvT256eENqaXJ0OG5RZzYzZ0h1RUN2dWt0ZTZnMWd2XG5hSWI1S2JBZGtadXA4NjBjTnFtOEF0M2RGa2plMlFBRWp5UytxKzN4aWlXamh3MUpWRXRFdU16akgrcUN6UnJBXG5vbGNFRit6NVV3S0JnUUM4Yi9WS0IzR25HOW1SQ2hxRDVBMGpKajRoVlA5RDBWMFJBN3RKem9mbXF0SlZ1cGMwXG5xVVEzMmUyVUFlV3FUaXJIOUk4Y0ZPQ0VUdWFoT1ZYWmJSSG1TTEpMTitiY1F5OVFGNGdiWFFGWlI4UmNJMnpKXG5CSTJzRnRybnNFYTJ4VTg1QVY2T1dKZ0VMOVl3MUZHL3ZobzFGNTlDUjFaTEdNbFpqR0lUUCtFL1RRS0JnUUNoXG5JVFFpVlZLMzQ1azlodUdySHlObWhqWC83ZTlISml1N3ZHZTUrZWtldTVNNVhlTUZvWm5Uc21Na2pkQ3YrR0hkXG5COFU5djRobnpQZWphSCtjNFJOVXFFREcwa3cxYzVBSmVrRGl3cXNqdkJUUDRnL0F5di8zbzY1WDZkZjlKVU5yXG5SeFk5OVdFZ2FiQ2tHdCtKNWF0MEc2Z2VlNHB6dndPWlBEMGpVOFhkT3dLQmdGbFc0NUNRZlFNZitsTTFBaUw1XG5ISmxsc21YdGdadytXTWJKaGVSb1dzcTRabCtnTGJNaHEzOFdaNVpONGFwbHR1SHp3OFU4NHh3a3V5Q2RicUM2XG5rTXVyMENEMVlud1haWHN0NWZHeVBESncyNUpsVVBNdWNaWmpoRnFjYmk2TmJOdFVyK1I4VGR6UllEdDJ5a1ZsXG5lTzRENlI0ZDN5MUFxK3k3SDFOdXcvckxcbi0tLS0tRU5EIFBSSVZBVEUgS0VZLS0tLS1cbiIsCiAgImNsaWVudF9lbWFpbCI6ICJiZWxlc3NpYTIwMjVAbXktcHJvamVjdC01MDI3My00Njk1MTQuaWFtLmdzZXJ2aWNlYWNjb3VudC5jb20iLAogICJjbGllbnRfaWQiOiAiMTAxMTk4OTMwODU5ODY5MjExNDk4IiwKICAiYXV0aF91cmkiOiAiaHR0cHM6Ly9hY2NvdW50cy5nb29nbGUuY29tL28vb2F1dGgyL2F1dGgiLAogICJ0b2tlbl91cmkiOiAiaHR0cHM6Ly9vYXV0aDIuZ29vZ2xlYXBpcy5jb20vdG9rZW4iLAogICJhdXRoX3Byb3ZpZGVyX3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vb2F1dGgyL3YxL2NlcnRzIiwKICAiY2xpZW50X3g1MDlfY2VydF91cmwiOiAiaHR0cHM6Ly93d3cuZ29vZ2xlYXBpcy5jb20vcm9ib3QvdjEvbWV0YWRhdGEveDUwOS9iZWxlc3NpYTIwMjUlNDBteS1wcm9qZWN0LTUwMjczLTQ2OTUxNC5pYW0uZ3NlcnZpY2VhY2NvdW50LmNvbSIsCiAgInVuaXZlcnNlX2RvbWFpbiI6ICJnb29nbGVhcGlzLmNvbSIKfQo="

    # --- FIN DE LA PRUEBA ---

    if creds_b64_str_temporal == "AQUÍ_VA_EL_TEXTO_LARGO_BASE64":
        st.error("Error de prueba: Debes reemplazar el texto de ejemplo con tu credencial Base64 en el código.")
        return None

    try:
        # El resto del código usa esta variable temporal en lugar de st.secrets
        creds_bytes = base64.b64decode(creds_b64_str_temporal)
        creds_json_str = creds_bytes.decode('utf-8')
        creds_dict = json.loads(creds_json_str)
        gspread_client = gspread.service_account_from_dict(creds_dict)

        st.success("¡DIAGNÓSTICO EXITOSO! La credencial funciona desde el código.")
        st.warning("RECUERDA QUITAR EL SECRETO DEL CÓDIGO AHORA.")

        return gspread_client
    except Exception as e:
        st.error("DIAGNÓSTICO FALLIDO: La credencial no funciona ni siquiera desde el código.", icon="🔥")
        st.code(f"El error sugiere que el texto Base64 está corrupto. Detalle: {e}", language="text")
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
