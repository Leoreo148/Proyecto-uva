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
    st.warning("El catálogo de productos está vacío.")
else:
    df_total_stock, _ = calcular_stock_por_lote(df_ingresos, df_salidas)
    df_vista_kardex = pd.merge(df_productos, df_total_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)

    # --- DIÁLOGO DE EDICIÓN ---
    if st.session_state.editing_product_id:
        producto_a_editar = df_productos[df_productos['id'] == st.session_state.editing_product_id].iloc[0]
        
        @st.dialog("✏️ Editar Producto")
        def edit_dialog():
            with st.form("edit_form_dialog"):
                st.write(f"**Editando:** {producto_a_editar['Producto']} (Código: {producto_a_editar['Codigo']})")
                unidades = ["Litro", "Kilo", "Unidad", "Galón", "Bolsa"]
                tipos_accion = ["Fertilizante", "Fungicida", "Insecticida", "Herbicida", "Bioestimulante", "Otro"]
                
                new_nombre = st.text_input("Nombre del Producto", value=producto_a_editar['Producto'])
                new_ing_activo = st.text_input("Ingrediente Activo", value=producto_a_editar.get('Ingrediente_Activo', ''))
                new_stock_min = st.number_input("Stock Mínimo", min_value=0.0, format="%.2f", value=float(producto_a_editar.get('Stock_Minimo', 0.0)))
                
                # --- CORRECCIÓN PARA EVITAR ValueError ---
                current_unidad = str(producto_a_editar.get('Unidad', '')).strip()
                try:
                    unidad_index = unidades.index(current_unidad)
                except ValueError:
                    unidad_index = 0 # Default to first item if not found
                new_unidad = st.selectbox("Unidad", unidades, index=unidad_index)

                new_proveedor = st.text_input("Proveedor", value=producto_a_editar.get('Proveedor', ''))

                # --- CORRECCIÓN PARA EVITAR ValueError ---
                current_tipo = str(producto_a_editar.get('Tipo_Accion', '')).strip()
                try:
                    tipo_index = tipos_accion.index(current_tipo)
                except ValueError:
                    tipo_index = 0 # Default to first item if not found
                new_tipo_accion = st.selectbox("Tipo de Acción", tipos_accion, index=tipo_index)
                
                col1, col2 = st.columns(2)
                if col1.form_submit_button("💾 Guardar Cambios"):
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
                if col2.form_submit_button("❌ Cancelar"):
                    st.session_state.editing_product_id = None
                    st.rerun()
        edit_dialog()

    # --- DIÁLOGO DE ELIMINACIÓN ---
    if st.session_state.deleting_product_id:
        producto_a_eliminar = df_productos[df_productos['id'] == st.session_state.deleting_product_id].iloc[0]
        @st.dialog("🗑️ Confirmar Eliminación")
        def delete_dialog():
            st.warning(f"¿Estás seguro de que quieres eliminar el producto **'{producto_a_eliminar['Producto']}'**?")
            st.write("Esta acción no se puede deshacer.")
            col1, col2 = st.columns(2)
            if col1.button("Sí, Eliminar Permanentemente"):
                supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
                st.toast("✅ Producto eliminado.")
                st.session_state.deleting_product_id = None
                st.cache_data.clear()
                st.rerun()
            if col2.button("No, Cancelar"):
                st.session_state.deleting_product_id = None
                st.rerun()
        delete_dialog()

    # --- MOSTRAR LA TABLA CON BOTONES (MÉTODO ALTERNATIVO) ---
    header_cols = st.columns([2, 4, 2, 2, 1, 2, 1, 1])
    headers = ['Código', 'Producto', 'Stock Actual', 'Stock Mínimo', 'Unidad', 'Valorizado', 'Editar', 'Borrar']
    for col, header in zip(header_cols, headers):
        col.markdown(f"**{header}**")

    st.markdown("---")

    for index, row in df_vista_kardex.iterrows():
        row_cols = st.columns([2, 4, 2, 2, 1, 2, 1, 1])
        row_cols[0].text(row.get('Codigo', ''))
        row_cols[1].text(row.get('Producto', ''))
        row_cols[2].text(f"{row.get('Stock_Actual', 0):.2f}")
        row_cols[3].text(f"{row.get('Stock_Minimo', 0):.2f}")
        row_cols[4].text(row.get('Unidad', ''))
        row_cols[5].text(f"S/ {row.get('Stock_Valorizado', 0):,.2f}")

        if row_cols[6].button("✏️", key=f"edit_{row['id']}", use_container_width=True):
            st.session_state.editing_product_id = row['id']
            st.rerun()

        if row_cols[7].button("🗑️", key=f"delete_{row['id']}", use_container_width=True):
            st.session_state.deleting_product_id = row['id']
            st.rerun()
