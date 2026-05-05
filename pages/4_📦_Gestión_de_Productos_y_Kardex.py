import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np
from supabase import create_client, Client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, GridUpdateMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="Kardex & Inventario Pro", page_icon="📦", layout="wide")

if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

try:
    style_metric_cards(background_color="#f0f2f6", border_left_color="#28a745")
except:
    pass

st.title("📦 Panel de Control: Kardex e Inventario Lote a Lote (Build 8.5)")
st.write("Visualización técnica expandida con datos de compras y propiedades biológicas.")

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- 3. FUNCIONES DE DATOS ---
@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: 
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # IMPORTANTE: Ahora también traemos el 'Proveedor' de la tabla Ingresos
    p = supabase.table('Productos').select("*").order('Producto').execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, Fecha_Vencimiento, Proveedor").execute()
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)

def generar_kardex(df_p, df_i, df_s):
    if df_p.empty: 
        st.warning("⚠️ El catálogo de Productos está vacío.")
        return pd.DataFrame()
    
    # --- Garantizar columnas del catálogo maestro ---
    df_p['Stock_Minimo'] = df_p.get('Stock_Minimo', 0.0).fillna(0.0)
    df_p['Periodo_Carencia_Dias'] = df_p.get('Periodo_Carencia_Dias', 0).fillna(0)
    df_p['Ingrediente_Activo'] = df_p.get('Ingrediente_Activo', 'N/A').fillna('N/A')
    df_p['Incompatible_Con'] = df_p.get('Incompatible_Con', 'Ninguna').fillna('Ninguna')
    df_p['Tipo_Accion'] = df_p.get('Tipo_Accion', 'N/A').fillna('N/A')
    df_p['Unidad'] = df_p.get('Unidad', 'N/A').fillna('N/A')

    # Si no hay ingresos, mostramos el catálogo en cero
    if df_i.empty:
        df_final = df_p.copy()
        df_final['Stock_Lote'] = 0.0
        df_final['Valorizado_PEN'] = 0.0
        df_final['Dias_para_Vencer'] = 999 
        df_final['Codigo_Lote'] = 'Sin Lote'
        df_final['Proveedor'] = 'N/A'
        df_final['Precio_Unitario_PEN'] = 0.0
        return df_final

    # 1. CALCULAR SALIDAS POR INGRESO_ID
    if not df_s.empty:
        resumen_salidas = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, resumen_salidas, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_balance['Stock_Disponible'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']
    else:
        df_balance = df_i.copy()
        df_balance['Stock_Disponible'] = df_balance['Cantidad_Ingresada']

    # 2. MERGE LOTE A LOTE (Aquí está el cambio clave: unimos pero SIN agrupar para no perder datos)
    df_final = pd.merge(df_balance, df_p, left_on='Codigo_Producto', right_on='Codigo', how='right')
    
    # 3. LIMPIEZA DE DATOS FINALES
    df_final['Stock_Lote'] = df_final['Stock_Disponible'].fillna(0.0)
    df_final['Codigo_Lote'] = df_final['Codigo_Lote'].fillna('Sin Lote')
    df_final['Proveedor'] = df_final['Proveedor'].fillna('N/A')
    df_final['Precio_Unitario_PEN'] = df_final['Precio_Unitario_PEN'].fillna(0.0)
    
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
    # Ajuste: Calculamos el stock total real por producto para que la métrica no cuente lotes dobles
    stock_total_prod = df_kardex.groupby('Codigo')['Stock_Lote'].sum().reset_index()
    stock_min_prod = df_p[['Codigo', 'Stock_Minimo']].drop_duplicates()
    criticos_df = pd.merge(stock_total_prod, stock_min_prod, on='Codigo')
    num_criticos = len(criticos_df[criticos_df['Stock_Lote'] < criticos_df['Stock_Minimo']])

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Valor Total Almacén", f"S/ {df_kardex['Valorizado_PEN'].sum():,.2f}")
    m2.metric("Insumos en Crítico", num_criticos)
    m3.metric("Lotes Próximos a Vencer", len(df_kardex[df_kardex['Dias_para_Vencer'] < 30]))
    m4.metric("Productos en Catálogo", len(df_p))

# --- 6. TABLA INTERACTIVA (AG-GRID) ---
st.subheader("📊 Inventario General (Vista Expandida)")

if not df_kardex.empty:
    # --- LISTA COMPLETA DE COLUMNAS QUE PEDISTE ---
    cols_mostrar = [
        'Codigo', 'Producto', 'Codigo_Lote', 'Stock_Lote', 'Unidad', 
        'Precio_Unitario_PEN', 'Valorizado_PEN', 'Proveedor', 
        'Ingrediente_Activo', 'Tipo_Accion', 'Incompatible_Con', 
        'Periodo_Carencia_Dias', 'Dias_para_Vencer'
    ]
    
    # Filtramos para asegurarnos que todas existen
    cols_reales = [c for c in cols_mostrar if c in df_kardex.columns]
    
    gb = GridOptionsBuilder.from_dataframe(df_kardex[cols_reales])
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_side_bar()
    gb.configure_selection('single', use_checkbox=True)
    
    cellsytle_jcode = JsCode("""
    function(params) {
        if (params.data.Stock_Lote <= 0) {
            return { 'color': 'white', 'backgroundColor': '#e74c3c' };
        }
        if (params.data.Dias_para_Vencer < 15) {
            return { 'color': 'black', 'backgroundColor': '#f1c40f' };
        }
        return null;
    }
    """)
    gb.configure_column("Stock_Lote", cellStyle=cellsytle_jcode)
    grid_options = gb.build()
    
    # He quitado 'FIT_CONTENTS' para que te permita hacer scroll horizontal (ya que hay muchas columnas)
    grid_response = AgGrid(
        df_kardex,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True, 
        theme='balham', 
        height=550
    )

    # --- 7. ACCIONES ---
    selected = grid_response['selected_rows']
    
    if selected is not None and not selected.empty:
        if isinstance(selected, pd.DataFrame):
            sel_row = selected.iloc[0]
        else:
            sel_row = selected[0]

        st.divider()
        c1, c2, c3 = st.columns([2, 2, 4])
        
        if c1.button("✏️ Editar Producto Master"):
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
                st.write(f"**🔬 Info Técnica:** {sel_row['Producto']} | Activo: {sel_row['Ingrediente_Activo']} | Lote Seleccionado: {sel_row['Codigo_Lote']}")

# --- 8. DIÁLOGOS DE GESTIÓN (Se mantienen igual) ---
if st.session_state.editing_product_id:
    prod_to_edit = df_p[df_p['id'] == st.session_state.editing_product_id].iloc[0]
    
    @st.dialog("✏️ Editar Maestro")
    def show_edit_dialog(p):
        with st.form("form_ed"):
            st.write(f"Editando: **{p['Producto']}**")
            col_a, col_b = st.columns(2)
            n_nombre = col_a.text_input("Nombre", value=p['Producto'])
            n_min = col_b.number_input("Mínimo", value=float(p.get('Stock_Minimo', 0)))
            n_car = col_a.number_input("Carencia", value=int(p.get('Periodo_Carencia_Dias', 0)))
            n_tipo = col_b.selectbox("Tipo", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Regulador", "Agroquímicos", "N/A"])
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

if st.session_state.deleting_product_id:
    @st.dialog("🗑️ Confirmar")
    def show_del_dialog():
        st.error("¿Seguro que deseas eliminar este producto por completo?")
        if st.button("SÍ, ELIMINAR"):
            supabase.table('Productos').delete().eq('id', st.session_state.deleting_product_id).execute()
            st.session_state.deleting_product_id = None
            st.cache_data.clear()
            st.rerun()
        if st.button("Cancelar"):
            st.session_state.deleting_product_id = None
            st.rerun()
    show_del_dialog()