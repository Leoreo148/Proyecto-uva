import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos y stock, conectado a una base de datos permanente con Supabase.")

# --- INICIALIZAR SESSION STATE ---
if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

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

# --- FUNCIONES PARA CARGAR DATOS ---
@st.cache_data(ttl=60)
def cargar_datos_supabase():
    if supabase:
        try:
            response_productos = supabase.table('Productos').select("*").order('Producto').execute()
            df_productos = pd.DataFrame(response_productos.data)
            response_ingresos = supabase.table('Ingresos').select("*").execute()
            df_ingresos = pd.DataFrame(response_ingresos.data)
            response_salidas = supabase.table('Salidas').select("*").execute()
            df_salidas = pd.DataFrame(response_salidas.data)
            return df_productos, df_ingresos, df_salidas
        except Exception as e:
            st.error(f"Error al leer los datos de Supabase: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- FUNCIONES DE LÓGICA DE NEGOCIO ---
def calcular_stock_por_lote(df_ingresos, df_salidas):
    if df_ingresos.empty:
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']), pd.DataFrame()
    
    df_ingresos['Cantidad'] = pd.to_numeric(df_ingresos['Cantidad'], errors='coerce').fillna(0)
    df_ingresos['Precio_Unitario'] = pd.to_numeric(df_ingresos['Precio_Unitario'], errors='coerce').fillna(0)
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
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    
    agg_funcs = {'Stock_Restante': 'sum', 'Valor_Lote': 'sum'}
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index().rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    
    return total_stock_producto, stock_lotes_detallado

# --- CARGA INICIAL DE DATOS ---
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

        if st.form_submit_button("Añadir Producto a Supabase"):
            if supabase and all([prod_codigo, prod_nombre]):
                try:
                    nuevo_producto_data = {
                        'Codigo': prod_codigo, 'Producto': prod_nombre, 'Ingrediente_Activo': prod_ing_activo,
                        'Unidad': prod_unidad, 'Proveedor': prod_proveedor, 'Tipo_Accion': prod_tipo_accion,
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

# SECCIÓN 2: CATÁLOGO DE PRODUCTOS Y GESTIÓN
st.divider()
st.header("📖 Catálogo de Productos y Stock Actual")

if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Añada un producto para empezar.")
else:
    df_total_stock, df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)

    # --- DIÁLOGO DE EDICIÓN ---
    if st.session_state.editing_product_id:
        producto_a_editar = df_productos[df_productos['id'] == st.session_state.editing_product_id].iloc[0]
        
        @st.dialog("✏️ Editar Producto")
        def edit_dialog():
            with st.form("edit_form_dialog"):
                st.write(f"**Editando:** {producto_a_editar['Producto']} (Código: {producto_a_editar['Codigo']})")
                
                new_nombre = st.text_input("Nombre del Producto", value=producto_a_editar['Producto'])
                new_ing_activo = st.text_input("Ingrediente Activo", value=producto_a_editar.get('Ingrediente_Activo', ''))
                new_stock_min = st.number_input("Stock Mínimo", min_value=0.0, step=1.0, format="%.2f", value=float(producto_a_editar.get('Stock_Minimo', 0.0)))
                new_unidad = st.selectbox("Unidad", ["Litro", "Kilo", "Unidad", "Galón", "Bolsa"], index=["Litro", "Kilo", "Unidad", "Galón", "Bolsa"].index(producto_a_editar.get('Unidad', 'Litro')))
                new_proveedor = st.text_input("Proveedor", value=producto_a_editar.get('Proveedor', ''))
                new_tipo_accion = st.selectbox("Tipo de Acción", ["Fertilizante", "Fungicida", "Insecticida", "Herbicida", "Bioestimulante", "Otro"], index=["Fertilizante", "Fungicida", "Insecticida", "Herbicida", "Bioestimulante", "Otro"].index(producto_a_editar.get('Tipo_Accion', 'Otro')))
                
                col1, col2 = st.columns(2)
                if col1.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                    try:
                        update_data = {
                            'Producto': new_nombre, 'Ingrediente_Activo': new_ing_activo,
                            'Stock_Minimo': new_stock_min, 'Unidad': new_unidad,
                            'Proveedor': new_proveedor, 'Tipo_Accion': new_tipo_accion
                        }
                        supabase.table('Productos').update(update_data).eq('id', st.session_state.editing_product_id).execute()
                        st.toast("✅ Producto actualizado.")
                        st.session_state.editing_product_id = None
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al actualizar: {e}")

                if col2.form_submit_button("❌ Cancelar", use_container_width=True):
                    st.session_state.editing_product_id = None
                    st.rerun()
        
        edit_dialog()

    # --- MOSTRAR LA TABLA CON BOTONES DENTRO USANDO DATA_EDITOR ---
    columnas_display = ['Codigo', 'Producto', 'Stock_Actual', 'Stock_Minimo', 'Unidad', 'Stock_Valorizado']
    for col in columnas_display:
        if col not in df_vista_kardex.columns:
            df_vista_kardex[col] = 0
    df_vista_kardex = df_vista_kardex[['id'] + columnas_display]

    df_display = df_vista_kardex.copy()
    df_display['Stock_Valorizado'] = df_display['Stock_Valorizado'].map('S/{:,.2f}'.format)
    df_display['Stock_Actual'] = df_display['Stock_Actual'].map('{:,.2f}'.format)
    
    # Añadimos columnas para los botones de acción
    df_display['Editar'] = False
    df_display['Eliminar'] = False
    
    edited_df = st.data_editor(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_order=('Codigo', 'Producto', 'Stock_Actual', 'Stock_Minimo', 'Unidad', 'Stock_Valorizado', 'Editar', 'Eliminar'),
        column_config={
            "id": None, # Ocultamos la columna de id de Supabase
            "Editar": st.column_config.ButtonColumn("✏️", help="Editar este producto"),
            "Eliminar": st.column_config.ButtonColumn("🗑️", help="Eliminar este producto"),
        },
        disabled=columnas_display # Hacemos que los datos no se puedan editar directamente en la tabla
    )

    # Lógica para manejar el clic en el botón de Editar
    edit_row = edited_df[edited_df.Editar].reset_index()
    if not edit_row.empty:
        product_id = df_display.loc[edit_row['index'][0], 'id']
        st.session_state.editing_product_id = product_id
        st.rerun()

    # Lógica para manejar el clic en el botón de Eliminar
    delete_row = edited_df[edited_df.Eliminar].reset_index()
    if not delete_row.empty:
        product_id = df_display.loc[delete_row['index'][0], 'id']
        product_name = df_display.loc[delete_row['index'][0], 'Producto']
        
        # Usamos un diálogo de confirmación para la eliminación
        @st.dialog("🗑️ Confirmar Eliminación")
        def delete_dialog():
            st.warning(f"¿Estás seguro de que quieres eliminar el producto **'{product_name}'**?")
            st.write("Esta acción no se puede deshacer.")
            col1, col2 = st.columns(2)
            if col1.button("Sí, Eliminar Permanentemente", use_container_width=True):
                try:
                    supabase.table('Productos').delete().eq('id', product_id).execute()
                    st.toast("✅ Producto eliminado.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al eliminar: {e}")
            if col2.button("No, Cancelar", use_container_width=True):
                st.rerun()
        
        delete_dialog()
