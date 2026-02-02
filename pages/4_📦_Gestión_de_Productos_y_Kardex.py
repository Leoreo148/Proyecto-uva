import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Panel de Control: Kardex e Inventario (Build 7.4)")
st.write("Visualización técnica de stock, alertas de reposición y trazabilidad de vencimientos.")

# --- INICIALIZAR SESSION STATE ---
if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

# --- FUNCIÓN DE CONEXIÓN ---
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

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def cargar_datos_kardex():
    if supabase:
        try:
            res_p = supabase.table('Productos').select("*").order('Producto').execute()
            df_p = pd.DataFrame(res_p.data)
            res_i = supabase.table('Ingresos').select("Codigo_Producto, Codigo_Lote, Cantidad, Precio_Unitario, Fecha_Vencimiento").execute()
            df_i = pd.DataFrame(res_i.data)
            res_s = supabase.table('Salidas').select("Codigo_Producto, Codigo_Lote, Cantidad").execute()
            df_s = pd.DataFrame(res_s.data)
            return df_p, df_i, df_s
        except Exception as e:
            st.error(f"Error en carga de datos: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- LÓGICA DE CÁLCULO ---
def procesar_kardex_detallado(df_i, df_s):
    if df_i.empty:
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado', 'Prox_Vencimiento'])
    for df in [df_i, df_s]:
        if not df.empty:
            df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce').fillna(0)
    ing_lote = df_i.groupby(['Codigo_Producto', 'Codigo_Lote']).agg({'Cantidad': 'sum', 'Precio_Unitario': 'first', 'Fecha_Vencimiento': 'first'}).reset_index().rename(columns={'Cantidad': 'Cant_Ing'})
    sal_lote = df_s.groupby(['Codigo_Producto', 'Codigo_Lote'])['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cant_Sal'})
    k_lotes = pd.merge(ing_lote, sal_lote, on=['Codigo_Producto', 'Codigo_Lote'], how='left').fillna(0)
    k_lotes['Stock_Lote'] = k_lotes['Cant_Ing'] - k_lotes['Cant_Sal']
    k_lotes['Valor_Lote'] = k_lotes['Stock_Lote'] * k_lotes['Precio_Unitario']
    hoy = date.today()
    def dias_venc(f_str):
        if not f_str: return 999
        try: return (datetime.strptime(f_str, '%Y-%m-%d').date() - hoy).days
        except: return 999
    k_lotes['Dias_Venc'] = k_lotes['Fecha_Vencimiento'].apply(dias_venc)
    resumen = k_lotes.groupby('Codigo_Producto').agg({'Stock_Lote': 'sum', 'Valor_Lote': 'sum', 'Dias_Venc': 'min'}).reset_index().rename(columns={'Stock_Lote': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado', 'Dias_Venc': 'Prox_Vencimiento'})
    return resumen

# --- PROCESAMIENTO INICIAL ---
df_productos, df_ingresos, df_salidas = cargar_datos_kardex()
df_resumen_stock = procesar_kardex_detallado(df_ingresos, df_salidas)

# --- SECCIÓN DE FILTROS Y BÚSQUEDA ---
st.header("📖 Estado de Insumos en Almacén")

if not df_productos.empty:
    df_vista = pd.merge(df_productos, df_resumen_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    
    # Barra de herramientas (Buscador y Ordenamiento)
    col_search, col_sort, col_order = st.columns([2, 1, 1])
    
    with col_search:
        query = st.text_input("🔍 Buscar por nombre o código", placeholder="Ej: Urea o F001")
    
    with col_sort:
        sort_by = st.selectbox("Ordenar por", options=["Producto", "Stock_Actual", "Stock_Valorizado", "Prox_Vencimiento"])
    
    with col_order:
        order = st.selectbox("Dirección", options=["Ascendente", "Descendente"])

    # Aplicar Filtro de Búsqueda
    if query:
        df_vista = df_vista[
            (df_vista['Producto'].str.contains(query, case=False)) | 
            (df_vista['Codigo'].str.contains(query, case=False))
        ]

    # Aplicar Ordenamiento
    is_asc = True if order == "Ascendente" else False
    df_vista = df_vista.sort_values(by=sort_by, ascending=is_asc)

    # --- RENDERIZADO DE LA TABLA ---
    st.markdown("---")
    h_cols = st.columns([1.5, 3, 1.5, 1.5, 1.5, 1.5, 0.8, 0.8])
    headers = ["Código", "Producto", "Stock Actual", "Mínimo", "Vencimiento", "Valorizado", "Edit", "Borrar"]
    for col, h in zip(h_cols, headers): col.markdown(f"**{h}**")
    st.markdown("---")

    for _, row in df_vista.iterrows():
        is_low_stock = row['Stock_Actual'] < row['Stock_Minimo']
        venc = row['Prox_Vencimiento']
        venc_text = "N/A" if venc == 999 else ("❌ VENCIDO" if venc < 0 else (f"⚠️ {int(venc)} d" if venc <= 15 else f"{int(venc)} d"))

        with st.container():
            r_cols = st.columns([1.5, 3, 1.5, 1.5, 1.5, 1.5, 0.8, 0.8])
            r_cols[0].text(row['Codigo'])
            r_cols[1].text(f"⚠️ {row['Producto']}" if is_low_stock else row['Producto'])
            
            if is_low_stock: r_cols[2].markdown(f":red[{row['Stock_Actual']:.2f}]")
            else: r_cols[2].text(f"{row['Stock_Actual']:.2f}")
            
            r_cols[3].text(f"{row['Stock_Minimo']:.2f}")
            r_cols[4].text(venc_text)
            r_cols[5].text(f"S/ {row['Stock_Valorizado']:,.2f}")

            if r_cols[6].button("✏️", key=f"ed_{row['id']}"):
                st.session_state.editing_product_id = row['id']
                st.rerun()
            if r_cols[7].button("🗑️", key=f"del_{row['id']}"):
                st.session_state.deleting_product_id = row['id']
                st.rerun()
        st.divider()
else:
    st.info("El catálogo está vacío.")

# --- DIÁLOGOS DE EDICIÓN Y ELIMINACIÓN (Se mantienen igual para no romper la lógica) ---
if st.session_state.editing_product_id:
    producto_a_editar = df_productos[df_productos['id'] == st.session_state.editing_product_id].iloc[0]
    @st.dialog("✏️ Editar Producto")
    def edit_dialog():
        with st.form("edit_form_dialog"):
            st.write(f"**Editando:** {producto_a_editar['Producto']}")
            new_nombre = st.text_input("Nombre", value=producto_a_editar['Producto'])
            new_ing = st.text_input("Ingrediente Activo", value=producto_a_editar.get('Ingrediente_Activo', ''))
            new_min = st.number_input("Stock Mínimo", value=float(producto_a_editar.get('Stock_Minimo', 0.0)))
            c1, c2 = st.columns(2)
            if c1.form_submit_button("💾 Guardar"):
                supabase.table('Productos').update({'Producto': new_nombre, 'Ingrediente_Activo': new_ing, 'Stock_Minimo': new_min}).eq('id', st.session_state.editing_product_id).execute()
                st.session_state.editing_product_id = None
                st.cache_data.clear()
                st.rerun()
            if c2.form_submit_button("❌ Cancelar"):
                st.session_state.editing_product_id = None
                st.rerun()
    edit_dialog()

if st.session_state.deleting_product_id:
    @st.dialog("🗑️ Confirmar Eliminación")
    def delete_dialog():
        st.warning("Esta acción es irreversible.")
        if st.button("Sí, Eliminar"):
            supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
            st.session_state.deleting_product_id = None
            st.cache_data.clear()
            st.rerun()
        if st.button("No, Cancelar"):
            st.session_state.deleting_product_id = None
            st.rerun()
    delete_dialog()