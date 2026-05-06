import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np
from supabase import create_client
import io

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, GridUpdateMode, JsCode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Kardex & Inventario Maestro", page_icon="📦", layout="wide")

# CSS para mejorar el contraste y el look en móvil
st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .main-header { color: #1e3d33; font-weight: bold; }
    /* Ajuste para que las tablas no se vean blancas puras */
    .ag-theme-balham { --ag-header-background-color: #1e3d33; --ag-header-foreground-color: #ffffff; }
    </style>
    """, unsafe_allow_html=True)

if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None
if 'deleting_product_id' not in st.session_state:
    st.session_state.deleting_product_id = None

try:
    style_metric_cards(background_color="#ffffff", border_left_color="#1e3d33")
except:
    pass

with stylable_container(key="title_box", css_styles="""{ background-color: #1e3d33; color: white; padding: 1rem; border-radius: 0.5rem; margin-bottom: 2rem; }"""):
    st.title("📦 Inventario Lote a Lote (Build 9.0)")
    st.write("Control total de existencias, trazabilidad de facturas y alertas FEFO.")

# --- 2. CONEXIÓN Y CARGA DE DATOS AUDITADA ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    p = supabase.table('Productos').select("*").order('Producto').execute()
    # AUDITORÍA: Añadimos Factura, Guia_Remision, Observaciones y Fecha_Recepcion
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, Fecha_Vencimiento, Proveedor, Factura, Guia_Remision, Observaciones, Fecha_Recepcion").execute()
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)

def generar_kardex(df_p, df_i, df_s):
    if df_p.empty: return pd.DataFrame()
    
    # Limpieza de Catálogo
    for col in ['Stock_Minimo', 'Periodo_Carencia_Dias']:
        df_p[col] = df_p.get(col, 0.0).fillna(0.0)
    
    # Merge con Ingresos y Salidas
    if df_i.empty:
        df_final = df_p.copy()
        df_final[['Stock_Lote', 'Valorizado_PEN']] = 0.0
        return df_final

    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']
    else:
        df_balance = df_i.copy()
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada']

    df_final = pd.merge(df_balance, df_p, left_on='Codigo_Producto', right_on='Codigo', how='right').fillna(0)
    df_final['Valorizado_PEN'] = df_final['Stock_Lote'] * df_final['Precio_Unitario_PEN']
    
    hoy = pd.Timestamp(date.today())
    df_final['Venc_Date'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
    df_final['Dias_para_Vencer'] = (df_final['Venc_Date'] - hoy).dt.days.fillna(999)
    
    return df_final

# --- 3. PROCESAMIENTO ---
df_p, df_i, df_s = cargar_todo()
df_kardex = generar_kardex(df_p, df_i, df_s)

# --- 4. PANEL DE FILTROS Y VISIBILIDAD (MEJORADO) ---
with st.expander("⚙️ Configuración de Filtros y Vista", expanded=True):
    c1, c2, c3 = st.columns([2, 2, 2])
    
    with c1:
        busqueda = st.text_input("🔍 Buscar (Producto/Lote/Factura/IA):")
    with c2:
        tipos = ["Todos"] + sorted(list(df_kardex['Tipo_Accion'].unique()))
        filtro_tipo = st.selectbox("Categoría:", tipos)
    
    with c3:
        # Aquí definimos las columnas que el ingeniero puede encender/apagar
        cols_opcionales = ['Proveedor', 'Factura', 'Guia_Remision', 'Fecha_Recepcion', 'Ingrediente_Activo', 'Incompatible_Con', 'Periodo_Carencia_Dias', 'Precio_Unitario_PEN', 'Valorizado_PEN']
        # Por defecto solo 5 columnas para móvil
        seleccionadas = st.multiselect("Añadir Detalles a la tabla:", options=cols_opcionales, default=[])

# Aplicar Filtros
if busqueda:
    mask = df_kardex.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
    df_kardex = df_kardex[mask]
if filtro_tipo != "Todos":
    df_kardex = df_kardex[df_kardex['Tipo_Accion'] == filtro_tipo]

# --- 5. MÉTRICAS ---
st.divider()
m1, m2, m3, m4 = st.columns(4)
m1.metric("Valor Inventario", f"S/ {df_kardex['Valorizado_PEN'].sum():,.2f}")
m2.metric("Items Críticos", len(df_kardex[df_kardex['Stock_Lote'] < df_kardex['Stock_Minimo']]))
m3.metric("Por Vencer (<15d)", len(df_kardex[df_kardex['Dias_para_Vencer'] < 15]))
m4.metric("Registros", len(df_kardex))

# --- 6. AG-GRID CONFIGURACIÓN (MÓVIL FRIENDLY) ---
# Columnas base (siempre visibles)
cols_base = ['Codigo', 'Producto', 'Codigo_Lote', 'Stock_Lote', 'Unidad']
cols_finales = cols_base + seleccionadas + ['Dias_para_Vencer']

if not df_kardex.empty:
    gb = GridOptionsBuilder.from_dataframe(df_kardex[cols_finales])
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_selection('single', use_checkbox=True)
    
    # Configuración de anchos para que no se vea mal en móvil
    for col in cols_finales:
        if col in ['Producto', 'Proveedor', 'Factura']:
            gb.configure_column(col, minWidth=180, flex=1)
        else:
            gb.configure_column(col, minWidth=100)

    # Colores de Alerta
    cellsytle_jcode = JsCode("""
    function(params) {
        if (params.data.Stock_Lote <= 0) { return { 'color': 'white', 'backgroundColor': '#e74c3c' }; }
        if (params.data.Dias_para_Vencer < 15) { return { 'color': 'black', 'backgroundColor': '#f1c40f' }; }
        return null;
    }
    """)
    gb.configure_column("Stock_Lote", cellStyle=cellsytle_jcode)
    
    grid_response = AgGrid(
        df_kardex,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        allow_unsafe_jscode=True, 
        theme='balham', 
        height=500
    )

    # --- 7. EXPORTAR ---
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_kardex[cols_finales].to_excel(writer, index=False)
    
    st.download_button("📥 Descargar Reporte Personalizado", data=buffer.getvalue(), file_name=f"Kardex_{date.today()}.xlsx", mime="application/vnd.ms-excel")

    # --- 8. ACCIONES ---
    selected = grid_response['selected_rows']
    if selected is not None and not (isinstance(selected, pd.DataFrame) and selected.empty):
        sel_row = selected.iloc[0] if isinstance(selected, pd.DataFrame) else selected[0]
        
        st.divider()
        c_ed1, c_ed2, c_ed3 = st.columns([2,2,4])
        if c_ed1.button("✏️ Editar Maestro"):
            match = df_p[df_p['Codigo'] == sel_row['Codigo']]
            if not match.empty:
                st.session_state.editing_product_id = int(match.iloc[0]['id'])
                st.rerun()
        
        with c_ed3:
            with stylable_container("info", css_styles="{ background-color: #e8f4fd; padding: 10px; border-radius: 5px;}"):
                st.write(f"**📝 Detalles del Lote:** Factura: {sel_row.get('Factura','-')} | Guía: {sel_row.get('Guia_Remision','-')} | Observaciones: {sel_row.get('Observaciones','-')}")

# --- 9. DIÁLOGOS DE GESTIÓN (IDEM ANTERIOR) ---
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