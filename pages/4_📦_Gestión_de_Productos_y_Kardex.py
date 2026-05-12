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

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

if 'editing_product_id' not in st.session_state:
    st.session_state.editing_product_id = None

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

st.info("💡 **Guía de Unidades:** Usa **001** para productos líquidos (Lt) y **002** para sólidos/polvos (Kg).")

# --- 3. CARGA DE DATOS AUDITADA ---
@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    p = supabase.table('Productos').select("*").order('Producto').execute()
    # 💡 AÑADIDO: Traemos el Estado_Registro de la tabla Ingresos
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, Fecha_Vencimiento, Proveedor, Factura, Observaciones, Estado_Registro").execute()
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)

def generar_kardex(df_p, df_i, df_s):
    # 🛡️ FIX BÚNKER: Variables inicializadas
    df_balance = pd.DataFrame()
    
    if df_p.empty: return pd.DataFrame()
    
    # Limpieza básica y protección de columnas nuevas (Soft Delete)
    df_p['Stock_Minimo'] = df_p.get('Stock_Minimo', 0.0).fillna(0.0)
    if 'Activo' not in df_p.columns: df_p['Activo'] = True
    df_p['Activo'] = df_p['Activo'].fillna(True).astype(bool)
    
    if df_i.empty:
        df_final = df_p.copy()
        for col in ['Stock_Lote', 'Valorizado_PEN']: df_final[col] = 0.0
        df_final['Dias_para_Vencer'] = 999
        df_final['Estado_Registro'] = 'Sin Ingresos'
        return df_final

    # Protección si el Estado_Registro es nulo en datos viejos
    if 'Estado_Registro' not in df_i.columns: df_i['Estado_Registro'] = 'Completo 🟢'
    df_i['Estado_Registro'] = df_i['Estado_Registro'].fillna('Completo 🟢')

    # Cálculo de saldos
    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']
    else:
        df_balance = df_i.copy()
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada']

    # Merge con catálogo
    df_final = pd.merge(df_balance, df_p, left_on='Codigo_Producto', right_on='Codigo', how='right')
    
    # 🛡️ FIX MATEMÁTICO: Forzar a número antes de multiplicar
    df_final['Stock_Lote'] = df_final['Stock_Lote'].fillna(0.0)
    df_final['Precio_Unitario_PEN'] = pd.to_numeric(df_final.get('Precio_Unitario_PEN', 0), errors='coerce').fillna(0.0)
    df_final['Valorizado_PEN'] = df_final['Stock_Lote'] * df_final['Precio_Unitario_PEN']
    
    # --- PROCESAMIENTO DE FECHAS SEGURO ---
    hoy = pd.Timestamp(date.today())
    df_final['Venc_Date'] = pd.to_datetime(df_final.get('Fecha_Vencimiento'), errors='coerce')
    df_final['Dias_para_Vencer'] = (df_final['Venc_Date'] - hoy).dt.days
    df_final.loc[df_final['Venc_Date'].isnull() | (df_final['Venc_Date'].dt.year < 2000), 'Dias_para_Vencer'] = 999
    
    return df_final

# --- 4. PROCESAMIENTO Y ANÁLISIS ABC ---
df_p, df_i, df_s = cargar_todo()
df_kardex_crudo = generar_kardex(df_p, df_i, df_s)
df_kardex = df_kardex_crudo.copy()

if not df_kardex.empty and df_kardex.get('Valorizado_PEN', pd.Series([0])).sum() > 0:
    df_kardex = df_kardex.sort_values(by='Valorizado_PEN', ascending=False).reset_index(drop=True)
    total_valor = df_kardex['Valorizado_PEN'].sum()
    df_kardex['Porcentaje_Acumulado'] = df_kardex['Valorizado_PEN'].cumsum() / total_valor
    
    condiciones = [
        (df_kardex['Porcentaje_Acumulado'] <= 0.80), 
        (df_kardex['Porcentaje_Acumulado'] > 0.80) & (df_kardex['Porcentaje_Acumulado'] <= 0.95), 
        (df_kardex['Porcentaje_Acumulado'] > 0.95)
    ]
    valores = ['A (Crítico)', 'B (Intermedio)', 'C (Rutina)']
    df_kardex['Clase_ABC'] = np.select(condiciones, valores, default='C (Rutina)')
    df_kardex.loc[df_kardex['Valorizado_PEN'] == 0, 'Clase_ABC'] = 'Sin Stock'
else:
    df_kardex['Clase_ABC'] = 'Sin Stock'

# --- 5. PANEL DE CONTROL ---
with stylable_container(key="green_panel", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.subheader("📦 Gestión Maestra de Inventario")
    
    c0, c1, c2, c3 = st.columns([1.5, 2, 2, 2])
    with c0:
        # 💡 NUEVO FILTRO: Ocultar Archivados
        st.write("")
        ocultar_archivados = st.checkbox("Ocultar Archivados", value=True)
    with c1:
        busqueda = st.text_input("🔍 Buscador:", placeholder="Lote, Producto...")
    with c2:
        tipos_limpios = sorted([str(t) for t in df_kardex.get('Tipo_Accion', []).unique() if t and str(t) not in ['0', 'nan', 'None']])
        filtro_tipo = st.selectbox("Categoría:", ["Todos"] + tipos_limpios)
    with c3:
        cols_detalle = ['Estado_Registro', 'Proveedor', 'Factura', 'Precio_Unitario_PEN', 'Observaciones']
        mostrar_extras = st.multiselect("⚙️ Columnas extra:", options=cols_detalle, default=['Estado_Registro'])

# Aplicar Filtros
if not df_kardex.empty:
    if ocultar_archivados and 'Activo' in df_kardex.columns:
        df_kardex = df_kardex[df_kardex['Activo'] == True]
    if busqueda:
        mask = df_kardex.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        df_kardex = df_kardex[mask]
    if filtro_tipo != "Todos":
        df_kardex = df_kardex[df_kardex['Tipo_Accion'] == filtro_tipo]

# --- 6. MÉTRICAS A PRUEBA DE BALAS ---
st.write("")
m1, m2, m3, m4 = st.columns(4)
style_metric_cards(background_color="#ffffff", border_left_color="#1e3d33")

val_total = df_kardex['Valorizado_PEN'].sum() if 'Valorizado_PEN' in df_kardex.columns else 0.0
m1.metric("Valorización (S/)", f"S/ {val_total:,.2f}")

n_alertas = len(df_kardex[df_kardex['Stock_Lote'] < df_kardex['Stock_Minimo']]) if 'Stock_Lote' in df_kardex.columns and 'Stock_Minimo' in df_kardex.columns else 0
m2.metric("Alertas Stock", n_alertas)

n_venc = len(df_kardex[df_kardex['Dias_para_Vencer'] < 15]) if 'Dias_para_Vencer' in df_kardex.columns else 0
m3.metric("Vencimientos <15d", n_venc)
m4.metric("Lotes en Vista", len(df_kardex) if not df_kardex.empty else 0)

# --- 7. AG-GRID ---
if not df_kardex.empty:
    cols_base = ['Codigo', 'Producto', 'Clase_ABC', 'Codigo_Lote', 'Stock_Lote', 'Unidad'] + mostrar_extras + ['Dias_para_Vencer']
    cols_visibles = [c for c in cols_base if c in df_kardex.columns]

    gb = GridOptionsBuilder.from_dataframe(df_kardex[cols_visibles])
    gb.configure_pagination(paginationAutoPageSize=False, paginationPageSize=15)
    gb.configure_selection('single', use_checkbox=True)
    
    for col in cols_visibles: gb.configure_column(col, minWidth=120)

    cellsytle_jcode = JsCode("""
    function(params) {
        if (params.data.Stock_Lote <= 0) { return { 'color': 'white', 'backgroundColor': '#e74c3c' }; }
        if (params.data.Dias_para_Vencer < 15) { return { 'color': 'black', 'backgroundColor': '#f1c40f' }; }
        return null;
    }
    """)
    gb.configure_column("Stock_Lote", cellStyle=cellsytle_jcode)
    
    grid_response = AgGrid(df_kardex, gridOptions=gb.build(), update_mode=GridUpdateMode.SELECTION_CHANGED, allow_unsafe_jscode=True, theme='balham', height=500)

    # Exportación
    st.write("")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_kardex[cols_visibles].to_excel(writer, index=False)
    st.download_button("📥 Descargar Reporte (Excel)", data=buffer.getvalue(), file_name=f"Kardex_{date.today()}.xlsx", mime="application/vnd.ms-excel")

    # --- 8. ACCIONES Y DETALLES ---
    selected = grid_response['selected_rows']
    if selected is not None and not (isinstance(selected, pd.DataFrame) and selected.empty):
        sel_row = selected.iloc[0] if isinstance(selected, pd.DataFrame) else selected[0]
        
        st.divider()
        c_acc1, c_acc2, c_acc3 = st.columns([2,2,4])
        
        if c_acc1.button("✏️ Editar Producto Master"):
            match = df_p[df_p['Codigo'] == sel_row['Codigo']]
            if not match.empty:
                st.session_state.editing_product_id = int(match.iloc[0]['id'])
                st.rerun()
                
        # 💡 NUEVO BOTÓN: Archivar Producto (Soft Delete)
        if c_acc2.button("📦 Archivar/Desactivar Master", type="secondary"):
            match = df_p[df_p['Codigo'] == sel_row['Codigo']]
            if not match.empty:
                real_id = int(match.iloc[0]['id'])
                supabase.table('Productos').update({"Activo": False}).eq('id', real_id).execute()
                st.success("Producto archivado. Sus registros históricos se mantienen, pero ya no aparecerá en búsquedas nuevas.")
                st.cache_data.clear()
                st.rerun()
        
        with c_acc3:
            with stylable_container("obs", css_styles="{ background-color: #e8f4fd; padding: 10px; border-radius: 8px; border: 1px solid #b3d7ff;}"):
                st.write(f"**💡 Observaciones del Lote:** {sel_row.get('Observaciones','Sin notas.')}")
else:
    st.info("El Kardex está vacío. Ingresa productos para comenzar.")

# --- 9. DIÁLOGOS DE GESTIÓN ---
if st.session_state.editing_product_id:
    # 🛡️ Blindaje extra: asegurarnos de que el DataFrame no esté vacío al buscar
    match_prod = df_p[df_p['id'] == st.session_state.editing_product_id]
    
    if not match_prod.empty:
        prod_to_edit = match_prod.iloc[0]
        
        @st.dialog("✏️ Editar Maestro")
        def show_edit_dialog(p):
            # LA CAJA DEL FORMULARIO
            with st.form("form_ed"):
                st.write(f"Editando: **{p['Producto']}**")
                col_a, col_b = st.columns(2)
                n_nombre = col_a.text_input("Nombre", value=p['Producto'])
                n_min = col_b.number_input("Mínimo", value=float(p.get('Stock_Minimo', 0)))
                n_car = col_a.number_input("Carencia", value=int(p.get('Periodo_Carencia_Dias', 0)))
                n_tipo = col_b.selectbox("Tipo", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Regulador", "Agroquímicos", "N/A"])
                n_inc = st.text_area("Incompatibilidades", value=p.get('Incompatible_Con', ''))
                
                # Único botón permitido dentro del form
                submit = st.form_submit_button("Guardar Cambios")
                
                if submit:
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
            
            # 🛑 EL FIX: El botón normal va AFUERA del bloque 'with st.form', pero dentro del diálogo
            if st.button("❌ Cancelar Edición"):
                st.session_state.editing_product_id = None
                st.rerun()
                
        show_edit_dialog(prod_to_edit)