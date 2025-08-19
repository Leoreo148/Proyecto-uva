import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- LIBRERÍAS NUEVAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y stock, conectado a una base de datos permanente con Supabase.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
@st.cache_resource
def init_supabase_connection():
    """
    Inicializa y cachea la conexión a Supabase usando las credenciales de st.secrets.
    """
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

# --- NUEVAS FUNCIONES PARA CARGAR Y GUARDAR DATOS EN SUPABASE ---
@st.cache_data(ttl=60) # Cachear los datos por 60 segundos
def cargar_datos_supabase():
    """
    Carga las tres tablas del Kardex (Productos, Ingresos, Salidas) desde Supabase.
    """
    if supabase is None:
        st.warning("La conexión con Supabase no está disponible. No se pueden cargar los datos.")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    try:
        # Cargar Productos
        response_productos = supabase.table('Productos').select("*").execute()
        df_productos = pd.DataFrame(response_productos.data)

        # Cargar Ingresos
        # (Descomentar cuando la tabla 'Ingresos' exista en Supabase)
        # response_ingresos = supabase.table('Ingresos').select("*").execute()
        # df_ingresos = pd.DataFrame(response_ingresos.data)
        df_ingresos = pd.DataFrame() # Placeholder mientras no existe la tabla

        # Cargar Salidas
        # (Descomentar cuando la tabla 'Salidas' exista en Supabase)
        # response_salidas = supabase.table('Salidas').select("*").execute()
        # df_salidas = pd.DataFrame(response_salidas.data)
        df_salidas = pd.DataFrame() # Placeholder mientras no existe la tabla
        
        # Convertir columnas de fecha al formato correcto
        for df in [df_ingresos, df_salidas]:
            if not df.empty and 'Fecha' in df.columns:
                df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        if not df_ingresos.empty and'Fecha_Vencimiento' in df_ingresos.columns:
            df_ingresos['Fecha_Vencimiento'] = pd.to_datetime(df_ingresos['Fecha_Vencimiento'], errors='coerce')

        st.success("¡Datos cargados desde Supabase exitosamente!")
        return df_productos, df_ingresos, df_salidas

    except Exception as e:
        st.error(f"Error al leer los datos de Supabase: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- FUNCIONES DE LÓGICA DE NEGOCIO (SIN CAMBIOS) ---
def calcular_stock_por_lote(df_ingresos, df_salidas):
    """Calcula el stock detallado por lote y el total por producto."""
    if df_ingresos.empty:
        cols_totales = ['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']
        cols_lotes = ['Codigo_Lote', 'Stock_Restante', 'Valor_Lote', 'Codigo_Producto', 'Producto', 'Fecha_Vencimiento', 'Precio_Unitario']
        return pd.DataFrame(columns=cols_totales), pd.DataFrame(columns=cols_lotes)
    
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
    """Convierte un DataFrame a un archivo Excel en memoria para descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA INICIAL DE DATOS DESDE SUPABASE ---
df_productos, df_ingresos, df_salidas = cargar_datos_supabase()

# --- INTERFAZ DE USUARIO ---

# SECCIÓN 1: AÑADIR NUEVO PRODUCTO
with st.expander("➕ Añadir Nuevo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Detalles del Nuevo Producto")
        
        col1, col2 = st.columns(2)
        with col1:
            prod_codigo = st.text_input("Código del Producto (ej: F001)")
            prod_nombre = st.text_input("Nombre del Producto")
            prod_ing_activo = st.text_input("Ingrediente Activo")
            prod_stock_min = st.number_input("Stock Mínimo", min_value=0.0, step=1.0, format="%.2f")
        with col2:
            prod_unidad = st.selectbox("Unidad", ["Litro", "Kilo", "Unidad", "Galón", "Bolsa"])
            prod_proveedor = st.text_input("Proveedor Principal")
            prod_tipo_accion = st.selectbox("Tipo de Acción", ["Fertilizante", "Fungicida", "Insecticida", "Herbicida", "Bioestimulante", "Otro"])

        submitted = st.form_submit_button("Añadir Producto a Supabase")
        
        if submitted and supabase:
            if not all([prod_codigo, prod_nombre, prod_unidad]):
                st.warning("Por favor, complete al menos Código, Nombre y Unidad.")
            else:
                try:
                    nuevo_producto_data = {
                        'Codigo': prod_codigo,
                        'Producto': prod_nombre,
                        'Ingrediente_Activo': prod_ing_activo,
                        'Unidad': prod_unidad,
                        'Proveedor': prod_proveedor,
                        'Tipo_Accion': prod_tipo_accion,
                        'Stock_Minimo': prod_stock_min
                    }
                    supabase.table('Productos').insert(nuevo_producto_data).execute()
                    st.success(f"¡Producto '{prod_nombre}' añadido a la base de datos!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar el producto en Supabase: {e}")

# SECCIÓN 2: VISUALIZACIÓN DEL KARDEX Y STOCK
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

