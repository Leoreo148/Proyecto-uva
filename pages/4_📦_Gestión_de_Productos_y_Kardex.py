import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np
from supabase import create_client, Client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, GridUpdateMode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Kardex & Inventario Pro", page_icon="📦", layout="wide")

# 🔥 FIX #1: INICIALIZAR SESSION STATE (Esto es lo que faltaba)
if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

# Estilo personalizado para las métricas
style_metric_cards(background_color="#f0f2f6", border_left_color="#28a745")

st.title("📦 Panel de Control: Kardex e Inventario (Build 8.1)")
st.write("Visualización técnica con alertas de seguridad biológica y trazabilidad financiera.")

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE DATOS OPTIMIZADA ---
@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    p = supabase.table('Productos').select("*").order('Producto').execute()
    i = supabase.table('Ingresos').select("Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, Fecha_Vencimiento").execute()
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)

# --- MOTOR DEL KARDEX ---
def generar_kardex_maestro(df_p, df_i, df_s):
    if df_p.empty: return pd.DataFrame()
    resumen_lotes = df_i.copy()
    resumen_lotes['Stock_Lote'] = resumen_lotes['Cantidad_Ingresada'] 
    
    resumen_prod = resumen_lotes.groupby('Codigo_Producto').agg({
        'Stock_Lote': 'sum',
        'Precio_Unitario_PEN': 'mean',
        'Fecha_Vencimiento': 'min'
    }).reset_index()
    
    df_final = pd.merge(df_p, resumen_prod, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    df_final['Valorizado_PEN'] = df_final['Stock_Lote'] * df_final['Precio_Unitario_PEN']
    
    hoy = pd.Timestamp(date.today())
    df_final['Venc_Date'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
    df_final['Dias_para_Vencer'] = (df_final['Venc_Date'] - hoy).dt.days.fillna(999)
    return df_final

# --- PROCESAMIENTO ---
df_p, df_i, df_s = cargar_todo()
df_kardex = generar_kardex_maestro(df_p, df_i, df_s)

# --- HEADER: MÉTRICAS ---
if not df_kardex.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Valor Total Almacén", f"S/ {df_kardex['Valorizado_PEN'].sum():,.2f}")
    m2.metric("Insumos en Crítico", len(df_kardex[df_kardex['Stock_Lote'] < df_kardex['Stock_Minimo']]))
    m3.metric("Próximos a Vencer", len(df_kardex[df_kardex['Dias_para_Vencer'] < 30]))
    m4.metric("Productos en Catálogo", len(df_p))

# --- CUERPO: TABLA INTERACTIVA ---
st.subheader("📊 Inventario en Tiempo Real")

if not df_kardex.empty:
    gb = GridOptionsBuilder.from_dataframe(df_kardex[[
        'Codigo', 'Producto', 'Tipo_Accion', 'Stock_Lote', 'Stock_Minimo', 
        'Unidad', 'Periodo_Carencia_Dias', 'Dias_para_Vencer', 'Valorizado_PEN'
    ]])
    
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_side_bar()
    gb.configure_selection('single', use_checkbox=True)
    
    # Colores de alerta
    cellsytle_jcode = """
    function(params) {
        if (params.data.Stock_Lote < params.data.Stock_Minimo) {
            return { 'color': 'white', 'backgroundColor': '#e74c3c' };
        }
        if (params.data.Dias_para_Vencer < 15) {
            return { 'color': 'black', 'backgroundColor': '#f1c40f' };
        }
        return null;
    }
    """
    gb.configure_column("Stock_Lote", cellStyle=cellsytle_jcode)
    grid_options = gb.build()
    
    grid_response = AgGrid(
        df_kardex,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
        theme='balham', 
        height=500
    )

    selected = grid_response['selected_rows']
    
    if selected is not None and not selected.empty:
        prod_data = selected.iloc[0]
        st.divider()
        c1, c2, c3 = st.columns([2, 2, 4])
        
        with c1:
            if st.button("✏️ Editar Producto"):
                # Buscamos el ID real en df_p usando el código seleccionado
                id_real = df_p[df_p['Codigo'] == prod_data['Codigo']].iloc[0]['id']
                st.session_state.editing_product_id = id_real
                st.rerun()
        with c2:
            if st.button("🗑️ Eliminar Producto", type="primary"):
                id_real = df_p[df_p['Codigo'] == prod_data['Codigo']].iloc[0]['id']
                st.session_state.deleting_product_id = id_real
                st.rerun()
        with col_info := c3:
            with stylable_container("info_box", css_styles="div { background-color: #e8f4fd; padding: 10px; border-radius: 5px;}"):
                st.markdown(f"**🔬 Nota Técnica:** {prod_data['Producto']} tiene un periodo de carencia de **{prod_data['Periodo_Carencia_Dias']} días**.")

# --- DIÁLOGOS DE GESTIÓN (LIMPIOS) ---

# Diálogo de Edición
if st.session_state.editing_product_id:
    p_edit = df_p[df_p['id'] == st.session_state.editing_product_id].iloc[0]
    
    @st.dialog("✏️ Actualizar Maestro de Producto")
    def edit_pro():
        with st.form("edit_p"):
            st.write(f"Editando: **{p_edit['Producto']}**")
            col_a, col_b = st.columns(2)
            nombre = col_a.text_input("Nombre Comercial", value=p_edit['Producto'])
            minimo = col_b.number_input("Stock Mínimo", value=float(p_edit['Stock_Minimo']))
            carencia = col_a.number_input("Días de Carencia", value=int(p_edit.get('Periodo_Carencia_Dias', 0)))
            tipo = col_b.selectbox("Tipo de Acción", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Regulador"], index=0)
            incomp = st.text_area("Incompatibilidades", value=p_edit.get('Incompatible_Con', ''))
            
            c_save, c_cancel = st.columns(2)
            if c_save.form_submit_button("Guardar"):
                upd = {"Producto": nombre, "Stock_Minimo": minimo, "Periodo_Carencia_Dias": carencia, "Tipo_Accion": tipo, "Incompatible_Con": incomp}
                supabase.table('Productos').update(upd).eq('id', p_edit['id']).execute()
                st.session_state.editing_product_id = None
                st.cache_data.clear()
                st.rerun()
            if c_cancel.form_submit_button("Cancelar"):
                st.session_state.editing_product_id = None
                st.rerun()
    edit_pro()

# Diálogo de Eliminación
if st.session_state.deleting_product_id:
    @st.dialog("🗑️ Confirmar Eliminación")
    def delete_dialog():
        st.warning("¿Estás seguro? Esta acción borrará el producto del catálogo.")
        c_yes, c_no = st.columns(2)
        if c_yes.button("Sí, Eliminar"):
            supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
            st.session_state.deleting_product_id = None
            st.cache_data.clear()
            st.rerun()
        if c_no.button("No, Cancelar"):
            st.session_state.deleting_product_id = None
            st.rerun()
    delete_dialog()