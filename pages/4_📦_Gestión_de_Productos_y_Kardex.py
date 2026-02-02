import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex (Build 7)")
st.write("Control central de inventario con alertas de stock y trazabilidad de vencimientos.")

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
            # Traer catálogo maestro
            res_p = supabase.table('Productos').select("*").order('Producto').execute()
            df_p = pd.DataFrame(res_p.data)
            
            # Traer ingresos y salidas usando solo códigos para el cálculo
            res_i = supabase.table('Ingresos').select("Codigo_Producto, Codigo_Lote, Cantidad, Precio_Unitario, Fecha_Vencimiento").execute()
            df_i = pd.DataFrame(res_i.data)
            
            res_s = supabase.table('Salidas').select("Codigo_Producto, Codigo_Lote, Cantidad").execute()
            df_s = pd.DataFrame(res_s.data)
            
            return df_p, df_i, df_s
        except Exception as e:
            st.error(f"Error en carga de datos: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- LÓGICA DE CÁLCULO DE STOCK Y VENCIMIENTOS ---
def procesar_kardex_detallado(df_i, df_s):
    if df_i.empty:
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado', 'Prox_Vencimiento'])

    # Asegurar tipos numéricos
    for df in [df_i, df_s]:
        if not df.empty:
            df['Cantidad'] = pd.to_numeric(df['Cantidad'], errors='coerce').fillna(0)
    
    # 1. Agrupar Ingresos y Salidas por Lote
    ingresos_lote = df_i.groupby(['Codigo_Producto', 'Codigo_Lote']).agg({
        'Cantidad': 'sum',
        'Precio_Unitario': 'first',
        'Fecha_Vencimiento': 'first'
    }).reset_index().rename(columns={'Cantidad': 'Cant_Ing'})

    salidas_lote = df_s.groupby(['Codigo_Producto', 'Codigo_Lote'])['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cant_Sal'})

    # 2. Calcular Stock Restante por Lote
    kardex_lotes = pd.merge(ingresos_lote, salidas_lote, on=['Codigo_Producto', 'Codigo_Lote'], how='left').fillna(0)
    kardex_lotes['Stock_Lote'] = kardex_lotes['Cant_Ing'] - kardex_lotes['Cant_Sal']
    kardex_lotes['Valor_Lote'] = kardex_lotes['Stock_Lote'] * kardex_lotes['Precio_Unitario']

    # 3. Calcular Días para Vencimiento
    hoy = date.today()
    def dias_venc(fecha_str):
        if not fecha_str: return 999
        try:
            venc = datetime.strptime(fecha_str, '%Y-%m-%d').date()
            return (venc - hoy).days
        except: return 999

    kardex_lotes['Dias_Venc'] = kardex_lotes['Fecha_Vencimiento'].apply(dias_venc)

    # 4. Resumen por Producto
    resumen_producto = kardex_lotes.groupby('Codigo_Producto').agg({
        'Stock_Lote': 'sum',
        'Valor_Lote': 'sum',
        'Dias_Venc': 'min' # Nos interesa el lote que vence más pronto
    }).reset_index().rename(columns={'Stock_Lote': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado', 'Dias_Venc': 'Prox_Vencimiento'})

    return resumen_producto

# --- CARGA INICIAL ---
df_productos, df_ingresos, df_salidas = cargar_datos_kardex()
df_resumen_stock = procesar_kardex_detallado(df_ingresos, df_salidas)

# SECCIÓN 1: AÑADIR NUEVO PRODUCTO
with st.expander("➕ Añadir Nuevo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Detalles del Nuevo Producto")
        col1, col2 = st.columns(2)
        with col1:
            prod_codigo = st.text_input("Código del Producto (ej: F001)")
            prod_nombre = st.text_input("Nombre del Producto")
            prod_ing_activo = st.text_input("Ingrediente Activo")
        with col2:
            prod_unidad = st.selectbox("Unidad", ["Litro", "Kilo", "Unidad", "Galón", "Bolsa"])
            prod_stock_min = st.number_input("Stock Mínimo", min_value=0.0, step=1.0, format="%.2f")
            prod_tipo_accion = st.selectbox("Tipo de Acción", ["Fertilizante", "Fungicida", "Insecticida", "Herbicida", "Bioestimulante", "Otro"])

        if st.form_submit_button("Añadir Producto"):
            if prod_codigo and prod_nombre:
                try:
                    nuevo_producto_data = {
                        'Codigo': prod_codigo, 'Producto': prod_nombre, 'Ingrediente_Activo': prod_ing_activo,
                        'Unidad': prod_unidad, 'Tipo_Accion': prod_tipo_accion, 'Stock_Minimo': prod_stock_min
                    }
                    supabase.table('Productos').insert(nuevo_producto_data).execute()
                    st.toast(f"✅ ¡{prod_nombre} añadido!", icon="🎉")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# SECCIÓN 2: VISUALIZACIÓN KARDEX
st.divider()
st.header("📖 Catálogo de Productos y Stock Actual")

if df_productos.empty:
    st.info("El catálogo está vacío.")
else:
    # Unir catálogo con cálculos de stock
    df_vista = pd.merge(df_productos, df_resumen_stock, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)

    # Cabecera de tabla
    h_cols = st.columns([1.5, 3, 1.5, 1.5, 1.5, 1.5, 0.8, 0.8])
    headers = ["Código", "Producto", "Stock Actual", "Mínimo", "Vencimiento", "Valorizado", "Edit", "Borrar"]
    for col, h in zip(h_cols, headers): col.markdown(f"**{h}**")
    st.markdown("---")

    for _, row in df_vista.iterrows():
        # Lógica de Alertas
        is_low_stock = row['Stock_Actual'] < row['Stock_Minimo']
        
        # Formato de Vencimiento
        venc = row['Prox_Vencimiento']
        if venc == 999: venc_text = "N/A"
        elif venc < 0: venc_text = "❌ VENCIDO"
        elif venc <= 15: venc_text = f"⚠️ {int(venc)} días"
        else: venc_text = f"{int(venc)} días"

        with st.container():
            r_cols = st.columns([1.5, 3, 1.5, 1.5, 1.5, 1.5, 0.8, 0.8])
            r_cols[0].text(row['Codigo'])
            
            # Nombre con Alerta Visual
            prod_label = f"⚠️ {row['Producto']}" if is_low_stock else row['Producto']
            r_cols[1].text(prod_label)
            
            # Stock Actual (Rojo si es bajo)
            if is_low_stock: r_cols[2].markdown(f":red[{row['Stock_Actual']:.2f}]")
            else: r_cols[2].text(f"{row['Stock_Actual']:.2f}")
            
            r_cols[3].text(f"{row['Stock_Minimo']:.2f}")
            r_cols[4].text(venc_text)
            r_cols[5].text(f"S/ {row['Stock_Valorizado']:,.2f}")

            # Botones de Acción
            if r_cols[6].button("✏️", key=f"ed_{row['id']}"):
                st.session_state.editing_product_id = row['id']
                st.rerun()
            if r_cols[7].button("🗑️", key=f"del_{row['id']}"):
                st.session_state.deleting_product_id = row['id']
                st.rerun()
        st.divider()

# --- DIÁLOGOS DE EDICIÓN Y ELIMINACIÓN ---
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
                upd = {'Producto': new_nombre, 'Ingrediente_Activo': new_ing, 'Stock_Minimo': new_min}
                supabase.table('Productos').update(upd).eq('id', st.session_state.editing_product_id).execute()
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
        c1, c2 = st.columns(2)
        if c1.button("Sí, Eliminar"):
            supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
            st.session_state.deleting_product_id = None
            st.cache_data.clear()
            st.rerun()
        if c2.button("No, Cancelar"):
            st.session_state.deleting_product_id = None
            st.rerun()
    delete_dialog()