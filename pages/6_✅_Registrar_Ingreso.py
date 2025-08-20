import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso por Lote", page_icon="📥", layout="wide")
st.title("📥 Registrar Ingreso de Mercadería por Lote")
st.write("Registre cada compra o ingreso como un lote único con su propio costo y fecha de vencimiento.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_para_ingreso():
    """Carga el catálogo de productos y el historial COMPLETO de ingresos desde Supabase."""
    if supabase:
        try:
            # Cargar el catálogo de productos para el formulario
            res_productos = supabase.table('Productos').select("Codigo, Producto").order('Producto').execute()
            df_productos = pd.DataFrame(res_productos.data)
            
            # Cargar TODOS los ingresos para buscar el último precio
            res_ingresos = supabase.table('Ingresos').select("Producto, Precio_Unitario, created_at").execute()
            df_ingresos_todos = pd.DataFrame(res_ingresos.data)
            
            return df_productos, df_ingresos_todos
        except Exception as e:
            st.error(f"Error al cargar datos de Supabase: {e}")
    return pd.DataFrame(), pd.DataFrame()

# --- CARGA DE DATOS ---
df_productos, df_todos_ingresos = cargar_datos_para_ingreso()

# --- INTERFAZ DE REGISTRO DE INGRESO ---
st.subheader("📝 Nuevo Registro de Lote")

if df_productos.empty:
    st.error("No se pueden registrar ingresos porque el catálogo de productos está vacío.")
    st.info("Por favor, vaya a la página '📦 Gestión de Productos y Kardex' y añada al menos un producto.")
else:
    st.markdown("##### 1. Información del Producto")
    
    producto_seleccionado = st.selectbox(
        "Seleccione el Producto que ingresa:",
        options=df_productos['Producto'].unique()
    )

    # --- LÓGICA PARA ENCONTRAR EL ÚLTIMO PRECIO ---
    ultimo_precio = 0.0
    if producto_seleccionado and not df_todos_ingresos.empty:
        # Filtramos los ingresos solo para el producto seleccionado
        ingresos_del_producto = df_todos_ingresos[df_todos_ingresos['Producto'] == producto_seleccionado].copy()
        if not ingresos_del_producto.empty:
            # Ordenamos por fecha de creación para encontrar el más reciente
            ingresos_del_producto['created_at'] = pd.to_datetime(ingresos_del_producto['created_at'])
            ingreso_mas_reciente = ingresos_del_producto.sort_values(by='created_at', ascending=False).iloc[0]
            ultimo_precio = float(ingreso_mas_reciente['Precio_Unitario'])

    if producto_seleccionado:
        codigo_producto_visible = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
        st.info(f"**Código del Producto Seleccionado:** `{codigo_producto_visible}` | **Último precio registrado:** `S/ {ultimo_precio:.2f}`")

    with st.form("ingreso_lote_form", clear_on_submit=True):
        cantidad_ingresada = st.number_input("Cantidad Ingresada (en la unidad del producto)", min_value=0.01, format="%.2f")

        st.markdown("##### 2. Información del Lote (Costo y Caducidad)")
        col1, col2 = st.columns(2)
        with col1:
            # El campo de precio ahora usa el último precio encontrado como valor por defecto
            precio_unitario = st.number_input("Precio Unitario (Costo por Unidad)", min_value=0.00, value=ultimo_precio, format="%.2f", help="El costo de compra de una unidad (Kg, L, etc.) de este lote.")
        with col2:
            fecha_vencimiento = st.date_input("Fecha de Vencimiento (Opcional)", value=None)

        st.markdown("##### 3. Documentación de Soporte")
        col3, col4, col5 = st.columns(3)
        with col3:
            fecha_ingreso = st.date_input("Fecha de Ingreso", datetime.now())
        with col4:
            proveedor = st.text_input("Proveedor")
        with col5:
            factura = st.text_input("Factura / Guía de Remisión")
        
        submitted = st.form_submit_button("✅ Guardar Ingreso del Lote")

        if submitted and supabase:
            try:
                codigo_producto = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                codigo_lote = f"{codigo_producto}-{timestamp}"
                
                nuevo_ingreso_data = {
                    'Codigo_Lote': codigo_lote,
                    'Fecha': fecha_ingreso.strftime("%Y-%m-%d"),
                    'Tipo': 'Ingreso por Compra',
                    'Proveedor': proveedor,
                    'Factura': factura,
                    'Producto': producto_seleccionado,
                    'Codigo_Producto': codigo_producto,
                    'Cantidad': cantidad_ingresada,
                    'Precio_Unitario': precio_unitario,
                    'Fecha_Vencimiento': fecha_vencimiento.strftime("%Y-%m-%d") if fecha_vencimiento else None
                }
                
                supabase.table('Ingresos').insert(nuevo_ingreso_data).execute()
                st.success(f"¡Lote '{codigo_lote}' para '{producto_seleccionado}' registrado exitosamente!")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"Error al guardar en Supabase: {e}")

st.divider()

# --- HISTORIAL DE INGRESOS RECIENTES ---
st.header("📚 Historial de Ingresos Recientes")
# Para la visualización, sí cargamos solo los últimos 15 para no saturar
if supabase:
    res_historial = supabase.table('Ingresos').select("*").order('created_at', desc=True).limit(15).execute()
    df_historial_ingresos = pd.DataFrame(res_historial.data)
    
    if not df_historial_ingresos.empty:
        columnas_a_mostrar = [
            'Fecha', 'Producto', 'Cantidad', 'Precio_Unitario', 
            'Codigo_Lote', 'Proveedor', 'Factura', 'Fecha_Vencimiento'
        ]
        columnas_existentes = [col for col in columnas_a_mostrar if col in df_historial_ingresos.columns]
        st.dataframe(df_historial_ingresos[columnas_existentes], use_container_width=True)
    else:
        st.info("Aún no se ha registrado ningún ingreso.")
