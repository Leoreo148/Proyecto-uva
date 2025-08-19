import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y stock, conectado a una base de datos permanente con Supabase.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        return client
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        st.info("Asegúrate de haber configurado SUPABASE_URL y SUPABASE_KEY en los Secrets de tu app.")
        return None

supabase = init_supabase_connection()

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS EN SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_supabase():
    if supabase is None:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        response_productos = supabase.table('Productos').select("*").execute()
        df_productos = pd.DataFrame(response_productos.data)
        response_ingresos = supabase.table('Ingresos').select("*").execute()
        df_ingresos = pd.DataFrame(response_ingresos.data)
        response_salidas = supabase.table('Salidas').select("*").execute()
        df_salidas = pd.DataFrame(response_salidas.data)
        
        st.success("¡Datos cargados desde Supabase exitosamente!")
        return df_productos, df_ingresos, df_salidas
    except Exception as e:
        st.error(f"Error al leer los datos de Supabase: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- FUNCIONES DE LÓGICA DE NEGOCIO (SIN CAMBIOS) ---
def calcular_stock_por_lote(df_ingresos, df_salidas):
    if df_ingresos.empty:
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']), pd.DataFrame(columns=['Codigo_Lote', 'Stock_Restante', 'Valor_Lote'])
    
    df_ingresos['Cantidad'] = pd.to_numeric(df_ingresos['Cantidad'], errors='coerce').fillna(0)
    if not df_salidas.empty:
        df_salidas['Cantidad'] = pd.to_numeric(df_salidas['Cantidad'], errors='coerce').fillna(0)

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
    
    stock_lotes_detallado['Precio_Unitario'] = pd.to_numeric(stock_lotes_detallado['Precio_Unitario'], errors='coerce').fillna(0)
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    
    agg_funcs = {'Stock_Restante': 'sum', 'Valor_Lote': 'sum'}
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index().rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    
    return total_stock_producto, stock_lotes_detallado

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA INICIAL DE DATOS DESDE SUPABASE ---
df_productos, df_ingresos, df_salidas = cargar_datos_supabase()

# --- INTERFAZ DE USUARIO ---

# SECCIÓN 1: CARGA MASIVA DESDE ARCHIVOS CSV (MODIFICADO)
with st.expander("⬆️ Cargar Datos Iniciales desde Excel"):
    st.info("Para la carga masiva, por favor sube los archivos CSV correspondientes a cada hoja de tu Excel. Esto borrará los datos existentes en 'Productos' e 'Ingresos'.")
    
    # Nuevos uploaders para cada archivo CSV necesario
    cod_producto_file = st.file_uploader("Sube el archivo 'Cod_Producto.csv'", type=["csv"])
    stock_file = st.file_uploader("Sube el archivo 'STOCK.csv'", type=["csv"])
    ingreso_file = st.file_uploader("Sube el archivo 'Ingreso.csv'", type=["csv"])
    
    if st.button("Procesar y Cargar a Supabase"):
        # Verificar que todos los archivos fueron subidos
        if cod_producto_file and stock_file and ingreso_file and supabase:
            with st.spinner("Procesando archivos y actualizando Supabase..."):
                try:
                    # Leer cada archivo CSV en un DataFrame, usando el header correcto
                    df_new_productos = pd.read_csv(cod_producto_file, header=1).rename(columns={'CODIGO': 'Codigo', 'PRODUCTOS': 'Producto'})
                    df_new_productos.dropna(subset=['Codigo', 'Producto'], inplace=True)

                    df_stock_sheet = pd.read_csv(stock_file, header=2)
                    p1 = df_stock_sheet[['PRODUCTO', 'CANT']].copy().rename(columns={'PRODUCTO': 'Producto', 'CANT': 'Cantidad'})
                    p2 = df_stock_sheet[['PRODUCTO.1', 'CANT.1']].copy().rename(columns={'PRODUCTO.1': 'Producto', 'CANT.1': 'Cantidad'})
                    p3 = df_stock_sheet[['PRODUCTO.2', 'CANT.2']].copy().rename(columns={'PRODUCTO.2': 'Producto', 'CANT.2': 'Cantidad'})
                    stock_data = pd.concat([p1, p2, p3], ignore_index=True).dropna(subset=['Producto'])
                    stock_data['Cantidad'] = pd.to_numeric(stock_data['Cantidad'], errors='coerce').fillna(0)
                    stock_data = stock_data[stock_data['Cantidad'] > 0]

                    df_ingresos_historicos = pd.read_csv(ingreso_file, header=1)
                    df_ingresos_historicos['F.DE ING.'] = pd.to_datetime(df_ingresos_historicos['F.DE ING.'])
                    df_ultimos_precios = df_ingresos_historicos.sort_values(by='F.DE ING.', ascending=False).drop_duplicates(subset=['PRODUCTOS'], keep='first')
                    df_ultimos_precios = df_ultimos_precios[['PRODUCTOS', 'PREC. UNI S/.']].rename(columns={'PRODUCTOS': 'Producto', 'PREC. UNI S/.': 'Precio_Unitario'})

                    # El resto de la lógica de procesamiento se mantiene igual
                    stock_data['join_key'] = stock_data['Producto'].astype(str).str.strip().str.lower()
                    df_new_productos['join_key'] = df_new_productos['Producto'].astype(str).str.strip().str.lower()
                    df_ultimos_precios['join_key'] = df_ultimos_precios['Producto'].astype(str).str.strip().str.lower()
                    
                    df_merged = pd.merge(stock_data, df_new_productos, on='join_key', how='left')
                    df_final_merged = pd.merge(df_merged, df_ultimos_precios, on='join_key', how='left')
                    df_final_merged['Precio_Unitario'].fillna(0, inplace=True)

                    ingresos_list = []
                    for _, row in df_final_merged.iterrows():
                        if pd.notna(row['Codigo']):
                            ingresos_list.append({
                                'Codigo_Lote': f"{row['Codigo']}-INV-INICIAL",
                                'Fecha': datetime.now().strftime("%Y-%m-%d"),
                                'Tipo': 'Ajuste de Inventario Inicial',
                                'Proveedor': row.get('PROVEEDOR', 'N/A'),
                                'Factura': row.get('FACTURA', 'N/A'),
                                'Producto': row.get('Producto_y', row.get('Producto_x')), # Fallback por si el nombre de columna cambia
                                'Codigo_Producto': row['Codigo'],
                                'Cantidad': row['Cantidad'],
                                'Precio_Unitario': row['Precio_Unitario'],
                                'Fecha_Vencimiento': None
                            })
                    df_new_ingresos = pd.DataFrame(ingresos_list).drop_duplicates(subset=['Codigo_Producto'], keep='first')

                    # --- LÓGICA PARA GUARDAR EN SUPABASE ---
                    st.write("Vaciando tablas existentes para una carga limpia...")
                    supabase.table('Ingresos').delete().neq('id', -1).execute()
                    supabase.table('Productos').delete().neq('id', --1).execute()

                    st.write("Insertando nuevos productos...")
                    productos_records = df_new_productos.to_dict(orient='records')
                    supabase.table('Productos').insert(productos_records).execute()
                    
                    st.write("Insertando registros de inventario inicial...")
                    ingresos_records = df_new_ingresos.to_dict(orient='records')
                    supabase.table('Ingresos').insert(ingresos_records).execute()
                    
                    st.success("¡Datos del archivo Excel cargados en Supabase exitosamente!")
                    st.cache_data.clear()
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocurrió un error durante la carga masiva: {e}")
        else:
            st.warning("Por favor, sube los tres archivos CSV requeridos para procesar.")

# SECCIÓN 2: AÑADIR NUEVO PRODUCTO (MANUALMENTE)
with st.expander("➕ Añadir un solo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Detalles del Nuevo Producto")
        col1, col2 = st.columns(2)
        with col1:
            prod_codigo = st.text_input("Código del Producto (ej: F001)")
            prod_nombre = st.text_input("Nombre del Producto")
        with col2:
            prod_unidad = st.selectbox("Unidad", ["Litro", "Kilo", "Unidad", "Galón", "Bolsa"])
            prod_stock_min = st.number_input("Stock Mínimo", min_value=0.0, step=1.0, format="%.2f")
        
        if st.form_submit_button("Añadir Producto"):
            if supabase and prod_codigo and prod_nombre:
                try:
                    nuevo_producto_data = {
                        'Codigo': prod_codigo,
                        'Producto': prod_nombre,
                        'Unidad': prod_unidad,
                        'Stock_Minimo': prod_stock_min
                    }
                    supabase.table('Productos').insert(nuevo_producto_data).execute()
                    st.success(f"¡Producto '{prod_nombre}' añadido!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.warning("Código y Nombre son obligatorios.")

# SECCIÓN 3: VISUALIZACIÓN DEL KARDEX
st.divider()
st.header("Kardex y Stock Actual")
if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Añada un producto para empezar.")
else:
    df_total_stock, df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
    
    if 'id' in df_productos.columns:
        df_productos = df_productos.rename(columns={'id': 'supabase_id'})

    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    
    columnas_a_mostrar = ['Codigo', 'Producto', 'Stock_Actual', 'Unidad', 'Stock_Valorizado', 'Stock_Minimo']
    for col in columnas_a_mostrar:
        if col not in df_vista_kardex.columns:
            df_vista_kardex[col] = 0

    df_vista_kardex = df_vista_kardex[columnas_a_mostrar]
    
    df_display = df_vista_kardex.copy()
    df_display['Stock_Valorizado'] = df_display['Stock_Valorizado'].map('S/{:,.2f}'.format)
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
            st.download_button(label="Descargar Inventario por Lote", data=excel_detallado, file_name=f"Detalle_Lotes_{datetime.now().strftime('%Y%m%d')}.xlsx")
    
    st.divider()
    
    st.subheader("Ver Desglose de Lotes Activos por Producto")
    if not df_productos.empty and 'Producto' in df_productos.columns and df_productos['Producto'].notna().any():
        producto_seleccionado = st.selectbox("Seleccione un producto:", options=df_productos['Producto'].dropna())
        if producto_seleccionado:
            codigo_seleccionado = df_productos.loc[df_productos['Producto'] == producto_seleccionado, 'Codigo'].iloc[0]
            
            if not df_stock_lotes.empty and 'Codigo_Producto' in df_stock_lotes.columns:
                lotes_del_producto = df_stock_lotes[df_stock_lotes['Codigo_Producto'] == codigo_seleccionado]
                lotes_activos = lotes_del_producto[lotes_del_producto['Stock_Restante'] > 0.001].copy()
                
                if lotes_activos.empty:
                    st.info(f"No hay lotes con stock activo para '{producto_seleccionado}'.")
                else:
                    lotes_activos['Precio_Unitario'] = lotes_activos['Precio_Unitario'].map('S/{:,.2f}'.format)
                    lotes_activos['Stock_Restante'] = lotes_activos['Stock_Restante'].map('{:,.2f}'.format)
                    lotes_activos['Valor_Lote'] = lotes_activos['Valor_Lote'].map('S/{:,.2f}'.format)
                    st.dataframe(lotes_activos[['Codigo_Lote', 'Stock_Restante', 'Precio_Unitario', 'Valor_Lote', 'Fecha_Vencimiento']], use_container_width=True, hide_index=True)

