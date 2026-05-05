import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np
from supabase import create_client, Client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, GridUpdateMode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="Kardex & Inventario Pro", page_icon="📦", layout="wide")

# Inicialización crítica del Session State para evitar el AttributeError
if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

# Estilo de métricas
try:
    style_metric_cards(background_color="#f0f2f6", border_left_color="#28a745")
except:
    pass

st.title("📦 Panel de Control: Kardex e Inventario (Build 8.2)")
st.write("Visualización técnica con alertas de seguridad biológica.")

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- 3. FUNCIONES DE DATOS ---
# --- 3. FUNCIONES DE DATOS (AJUSTADAS) ---
@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # IMPORTANTE: Seleccionamos 'id' en Ingresos para poder restarle las salidas
    p = supabase.table('Productos').select("*").order('Producto').execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, Fecha_Vencimiento").execute()
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)

def generar_kardex(df_p, df_i, df_s):
    # Si no hay productos, no hay nada que mostrar
    if df_p.empty: 
        st.warning("⚠️ El catálogo de Productos está vacío.")
        return pd.DataFrame()
    
    # --- FIX: Asegurar columnas numéricas del catálogo ---
    if 'Stock_Minimo' not in df_p.columns: df_p['Stock_Minimo'] = 0.0
    if 'Periodo_Carencia_Dias' not in df_p.columns: df_p['Periodo_Carencia_Dias'] = 0

    # Si no hay ingresos, el stock es cero para todos
    if df_i.empty:
        df_p['Stock_Lote'] = 0.0
        df_p['Valorizado_PEN'] = 0.0
        df_p['Dias_para_Vencer'] = 999 # <-- FIX: Columna virtual para evitar el KeyError
        df_p['Tipo_Accion'] = df_p.get('Tipo_Accion', 'N/A')
        df_p['Unidad'] = df_p.get('Unidad', 'N/A')
        return df_p

    # 1. CALCULAR SALIDAS POR INGRESO_ID
    if not df_s.empty:
        resumen_salidas = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, resumen_salidas, left_on='id', right_on='Ingreso_ID', how='left').fillna(0)
        df_balance['Stock_Disponible'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']
    else:
        df_balance = df_i.copy()
        df_balance['Stock_Disponible'] = df_balance['Cantidad_Ingresada']

    # 2. AGRUPAR POR PRODUCTO
    resumen_prod = df_balance.groupby('Codigo_Producto').agg({
        'Stock_Disponible': 'sum',
        'Precio_Unitario_PEN': 'mean', 
        'Fecha_Vencimiento': 'min'     
    }).reset_index()

    # 3. MERGE FINAL CON MAESTRO DE PRODUCTOS
    df_final = pd.merge(df_p, resumen_prod, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    
    df_final = df_final.rename(columns={'Stock_Disponible': 'Stock_Lote'})
    df_final['Valorizado_PEN'] = df_final['Stock_Lote'] * df_final['Precio_Unitario_PEN']
    
    hoy = pd.Timestamp(date.today())
    df_final['Venc_Date'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
    df_final['Dias_para_Vencer'] = (df_final['Venc_Date'] - hoy).dt.days.fillna(999)
    
    return df_final

# --- 4. PROCESAMIENTO ---
df_p, df_i, df_s = cargar_todo()
df_kardex = generar_kardex(df_p, df_i, df_s)

# --- 5. INTERFAZ: MÉTRICAS ---
if not df_kardex.empty:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Valor Total Almacén", f"S/ {df_kardex['Valorizado_PEN'].sum():,.2f}")
    m2.metric("Insumos en Crítico", len(df_kardex[df_kardex['Stock_Lote'] < df_kardex['Stock_Minimo']]))
    m3.metric("Próximos a Vencer", len(df_kardex[df_kardex['Dias_para_Vencer'] < 30]))
    m4.metric("Productos en Catálogo", len(df_p))

# --- 6. TABLA INTERACTIVA (AG-GRID) ---
st.subheader("📊 Inventario en Tiempo Real")

if not df_kardex.empty:
    # Columnas que queremos mostrar
    cols_mostrar = ['Codigo', 'Producto', 'Tipo_Accion', 'Stock_Lote', 'Stock_Minimo', 'Unidad', 'Periodo_Carencia_Dias', 'Dias_para_Vencer', 'Valorizado_PEN']
    
    gb = GridOptionsBuilder.from_dataframe(df_kardex[cols_mostrar])
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=12)
    gb.configure_side_bar()
    gb.configure_selection('single', use_checkbox=True)
    
    # Formateo y Colores (JavaScript)
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
        height=450
    )

    # --- 7. ACCIONES ---
    selected = grid_response['selected_rows']
    
    if selected is not None and not selected.empty:
        # En AgGrid nuevo, selected es un DataFrame o una lista. Manejamos ambos:
        if isinstance(selected, pd.DataFrame):
            sel_row = selected.iloc[0]
        else:
            sel_row = selected[0]

        st.divider()
        c1, c2, c3 = st.columns([2, 2, 4])
        
        if c1.button("✏️ Editar Producto"):
            # Buscar ID real por Código
            match = df_p[df_p['Codigo'] == sel_row['Codigo']]
            if not match.empty:
                st.session_state.editing_product_id = int(match.iloc[0]['id'])
                st.rerun()

        if c2.button("🗑️ Eliminar Producto", type="primary"):
            match = df_p[df_p['Codigo'] == sel_row['Codigo']]
            if not match.empty:
                st.session_state.deleting_product_id = int(match.iloc[0]['id'])
                st.rerun()

        with c3:
            with stylable_container("info", css_styles="div { background-color: #e8f4fd; padding: 10px; border-radius: 5px;}"):
                st.write(f"**🔬 Info Técnica:** {sel_row['Producto']} | Carencia: {sel_row['Periodo_Carencia_Dias']} días.")

# --- 8. DIÁLOGOS DE GESTIÓN ---

# Edición
if st.session_state.editing_product_id:
    # Obtener datos del producto a editar
    prod_to_edit = df_p[df_p['id'] == st.session_state.editing_product_id].iloc[0]
    
    @st.dialog("✏️ Editar Maestro")
    def show_edit_dialog(p):
        with st.form("form_ed"):
            st.write(f"Editando: **{p['Producto']}**")
            col_a, col_b = st.columns(2)
            n_nombre = col_a.text_input("Nombre", value=p['Producto'])
            n_min = col_b.number_input("Mínimo", value=float(p['Stock_Minimo']))
            n_car = col_a.number_input("Carencia", value=int(p.get('Periodo_Carencia_Dias', 0)))
            n_tipo = col_b.selectbox("Tipo", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Regulador"])
            n_inc = st.text_area("Incompatibilidades", value=p.get('Incompatible_Con', ''))
            
            if st.form_submit_button("Guardar"):
                data_upd = {
                    "Producto": n_nombre, 
                    "Stock_Minimo": n_min, 
                    "Periodo_Carencia_Dias": n_car, 
                    "Tipo_Accion": n_tipo, 
                    "Incompatible_Con": n_inc
                }
                supabase.table('Productos').update(data_upd).eq('id', p['id']).execute()
                st.session_state.editing_product_id = None
                st.cache_data.clear()
                st.rerun()
            if st.button("Cerrar"):
                st.session_state.editing_product_id = None
                st.rerun()
                
    show_edit_dialog(prod_to_edit)

# Eliminación
if st.session_state.deleting_product_id:
    @st.dialog("🗑️ Confirmar")
    def show_del_dialog():
        st.error("¿Seguro que deseas eliminar este producto?")
        if st.button("SÍ, ELIMINAR"):
            supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
            st.session_state.deleting_product_id = None
            st.cache_data.clear()
            st.rerun()
        if st.button("Cancelar"):
            st.session_state.deleting_product_id = None
            st.rerun()
    show_del_dialog()