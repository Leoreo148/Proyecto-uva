import streamlit as st
import pandas as pd
from datetime import datetime, date
import numpy as np
from supabase import create_client
import io
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# 🚨 CANDADO VIP: EXCLUSIVO PARA ALMACÉN
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

if st.session_state["rol"] not in ["Admin", "Logistica", "Programador"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para el área de Almacén y Mezclas (Miguel).")
    st.stop()

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

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=60)
def cargar_todo():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    p   = supabase.table('Productos').select("*").order('Producto').execute()
    i   = supabase.table('Ingresos').select(
        "id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN, "
        "Fecha_Vencimiento, Proveedor, Factura, Observaciones, Estado_Registro, Guia_Remision, Responsable"
    ).execute()
    s   = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data)


def generar_kardex(df_p, df_i, df_s):
    """Devuelve (df_por_lote, df_por_producto).
    df_por_lote : una fila por cada ingreso/lote (vista técnica de almacén).
    df_por_producto: stock total agrupado por producto (vista gerencial).
    """
    if df_p.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_p = df_p.copy()
    df_p['Stock_Minimo'] = pd.to_numeric(df_p.get('Stock_Minimo', 0), errors='coerce').fillna(0.0)
    if 'Activo' not in df_p.columns:
        df_p['Activo'] = True
    df_p['Activo'] = df_p['Activo'].fillna(True).astype(bool)

    # --- Calcular stock por lote ---
    if df_i.empty:
        df_lotes = df_p.copy()
        df_lotes['Stock_Lote']     = 0.0
        df_lotes['Valorizado_PEN'] = 0.0
        df_lotes['Dias_para_Vencer'] = 999
        return df_lotes, pd.DataFrame()

    if 'Estado_Registro' not in df_i.columns:
        df_i['Estado_Registro'] = 'Completo 🟢'
    df_i['Estado_Registro'] = df_i['Estado_Registro'].fillna('Completo 🟢')

    if not df_s.empty:
        gastado    = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
    else:
        df_balance = df_i.copy()
        df_balance['Cantidad_Usada'] = 0

    df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']

    # --- Merge lotes → catálogo ---
    df_lotes = pd.merge(df_balance, df_p, left_on='Codigo_Producto', right_on='Codigo', how='right')
    df_lotes['Stock_Lote']          = df_lotes['Stock_Lote'].fillna(0.0)
    df_lotes['Precio_Unitario_PEN'] = pd.to_numeric(df_lotes.get('Precio_Unitario_PEN', 0), errors='coerce').fillna(0.0)
    df_lotes['Valorizado_PEN']      = df_lotes['Stock_Lote'] * df_lotes['Precio_Unitario_PEN']
    df_lotes['Cantidad_Usada']      = df_lotes['Cantidad_Usada'].fillna(0.0)

    hoy = pd.Timestamp(date.today())
    df_lotes['Venc_Date']        = pd.to_datetime(df_lotes.get('Fecha_Vencimiento'), errors='coerce')
    df_lotes['Dias_para_Vencer'] = (df_lotes['Venc_Date'] - hoy).dt.days
    df_lotes.loc[df_lotes['Venc_Date'].isnull() | (df_lotes['Venc_Date'].dt.year < 2000), 'Dias_para_Vencer'] = 999

    # ✅ FIX: Prox_Vencimiento solo sobre lotes con stock real (evita falsas alarmas)
    df_lotes_con_stock = df_lotes[df_lotes['Stock_Lote'] > 0].copy()

    # --- KPI: Salidas por producto para Rotación y Días de Cobertura ---
    # Cruzamos Salidas → Ingresos → Producto para saber cuánto se consumió de cada producto
    if not df_s.empty and 'Ingreso_ID' in df_s.columns:
        # Traemos el código de producto desde los ingresos
        df_s_prod = pd.merge(
            df_s[['Ingreso_ID', 'Cantidad_Usada']],
            df_i[['id', 'Codigo_Producto']],
            left_on='Ingreso_ID', right_on='id', how='left'
        )
        salidas_por_prod = df_s_prod.groupby('Codigo_Producto')['Cantidad_Usada'].sum().reset_index()
        salidas_por_prod.columns = ['Codigo', 'Total_Salidas']
    else:
        salidas_por_prod = pd.DataFrame(columns=['Codigo', 'Total_Salidas'])

    # ✅ Calculamos Prox_Vencimiento FUERA del groupby para evitar el KeyError de índices
    # Solo contamos lotes que aún tienen stock real (evita falsas alarmas de lotes vacíos)
    venc_con_stock = (
        df_lotes_con_stock.groupby('Codigo')['Dias_para_Vencer']
        .min()
        .reset_index()
        .rename(columns={'Dias_para_Vencer': 'Prox_Vencimiento'})
    )

    # Vista agrupada por PRODUCTO (sin Prox_Vencimiento por ahora)
    df_por_producto = (
        df_lotes.groupby(['Codigo', 'Producto', 'Unidad', 'Tipo_Accion', 'Stock_Minimo', 'Activo',
                          'Ingrediente_Activo', 'Marca', 'Formulacion', 'Banda_Toxicologica', 'Ficha_Tecnica_URL'],
                         dropna=False)
        .agg(
            Stock_Total    =('Stock_Lote',    'sum'),
            Valorizado_PEN =('Valorizado_PEN', 'sum'),
            N_Lotes        =('Codigo_Lote',    'count'),
        )
        .reset_index()
    )

    # Incorporamos Prox_Vencimiento limpio (999 = sin vencimiento próximo)
    df_por_producto = pd.merge(df_por_producto, venc_con_stock, on='Codigo', how='left')
    df_por_producto['Prox_Vencimiento'] = df_por_producto['Prox_Vencimiento'].fillna(999).astype(int)



    # Unir Total_Salidas
    df_por_producto = pd.merge(df_por_producto, salidas_por_prod, on='Codigo', how='left')
    df_por_producto['Total_Salidas'] = df_por_producto['Total_Salidas'].fillna(0.0)

    # --- KPIs derivados ---
    PERIODO_DIAS = 180  # Ventana de cálculo: últimos 6 meses

    # ✅ División segura: reemplazamos 0 con NaN ANTES de dividir.
    # np.where evalúa ambas ramas siempre, por eso no podemos usarlo con divisiones.
    stock_safe   = df_por_producto['Stock_Total'].replace(0, np.nan)
    consumo_diario = df_por_producto['Total_Salidas'] / PERIODO_DIAS
    consumo_safe = consumo_diario.replace(0, np.nan)

    # Rotación = Total salidas / Stock actual  (NaN si sin stock)
    df_por_producto['Rotacion'] = (df_por_producto['Total_Salidas'] / stock_safe).round(2)

    # Días de Cobertura = Stock actual / consumo diario  (NaN si sin consumo)
    df_por_producto['Dias_Cobertura'] = (df_por_producto['Stock_Total'] / consumo_safe).round(0)

    # Stock Muerto = tiene stock pero 0 salidas registradas
    df_por_producto['Stock_Muerto'] = (
        (df_por_producto['Stock_Total'] > 0) & (df_por_producto['Total_Salidas'] == 0)
    )

    return df_lotes, df_por_producto


# --- 4. PROCESAMIENTO Y ANÁLISIS ABC ---
df_p, df_i, df_s          = cargar_todo()
df_kardex_lotes, df_kardex = generar_kardex(df_p, df_i, df_s)

# Análisis ABC sobre la vista agrupada
if not df_kardex.empty and df_kardex['Valorizado_PEN'].sum() > 0:
    df_kardex = df_kardex.sort_values('Valorizado_PEN', ascending=False).reset_index(drop=True)
    total_val = df_kardex['Valorizado_PEN'].sum()
    df_kardex['Porcentaje_Acumulado'] = df_kardex['Valorizado_PEN'].cumsum() / total_val
    condiciones = [
        df_kardex['Porcentaje_Acumulado'] <= 0.80,
        (df_kardex['Porcentaje_Acumulado'] > 0.80) & (df_kardex['Porcentaje_Acumulado'] <= 0.95),
        df_kardex['Porcentaje_Acumulado'] > 0.95
    ]
    df_kardex['Clase_ABC'] = np.select(condiciones, ['A (Crítico)', 'B (Intermedio)', 'C (Rutina)'], default='C (Rutina)')
    df_kardex.loc[df_kardex['Valorizado_PEN'] == 0, 'Clase_ABC'] = 'Sin Stock'
elif not df_kardex.empty:
    df_kardex['Clase_ABC'] = 'Sin Stock'

# --- 5. PANEL DE CONTROL Y FILTROS ---
with stylable_container(key="green_panel", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.subheader("📦 Gestión Maestra de Inventario")

    c0, c1, c2, c3 = st.columns([1.5, 2, 2, 2])
    with c0:
        st.write("")
        ocultar_archivados = st.checkbox("Ocultar Archivados", value=True)
    with c1:
        busqueda = st.text_input("🔍 Buscador:", placeholder="Producto, Código...")
    with c2:
        tipos_limpios = sorted([str(t) for t in df_kardex.get('Tipo_Accion', pd.Series()).unique()
                                 if t and str(t) not in ['0', 'nan', 'None']]) if not df_kardex.empty else []
        filtro_tipo = st.selectbox("Categoría:", ["Todos"] + tipos_limpios)
    with c3:
        filtro_abc = st.selectbox("Clase ABC:", ["Todos", "A (Crítico)", "B (Intermedio)", "C (Rutina)", "Sin Stock"])

    with st.expander("🛠️ Filtros Avanzados y Alertas KPI"):
        kpi1, kpi2, kpi3 = st.columns(3)
        filtro_kpi_stock = kpi1.checkbox("🚨 Stock Crítico (< Mínimo)",
                                          help="Solo funciona si configuras el Stock Mínimo en cada producto (editar producto maestro)")
        filtro_kpi_venc  = kpi2.checkbox("⏳ Por Vencer (< 15 días)",
                                          help="Solo alerta lotes que aún tienen stock real, no lotes vacíos")
        filtro_kpi_muerto= kpi3.checkbox("Stock Muerto (sin salidas)",
                                          help="Productos con stock pero sin ninguna salida registrada")

    cols_detalle  = ['Ingrediente_Activo', 'Marca', 'Formulacion', 'Banda_Toxicologica',
                     'Ficha_Tecnica_URL', 'N_Lotes', 'Total_Salidas', 'Rotacion', 'Dias_Cobertura']
    mostrar_extras = st.multiselect("⚙️ Columnas extra:", options=cols_detalle,
                                    default=['Ingrediente_Activo', 'N_Lotes', 'Dias_Cobertura'])

# --- 6. APLICAR FILTROS ---
df_vista = df_kardex.copy() if not df_kardex.empty else pd.DataFrame()

if not df_vista.empty:
    if ocultar_archivados and 'Activo' in df_vista.columns:
        df_vista = df_vista[df_vista['Activo'] == True]
    if busqueda:
        mask = df_vista.apply(lambda row: row.astype(str).str.contains(busqueda, case=False).any(), axis=1)
        df_vista = df_vista[mask]
    if filtro_tipo != "Todos":
        df_vista = df_vista[df_vista['Tipo_Accion'] == filtro_tipo]
    if filtro_abc != "Todos" and 'Clase_ABC' in df_vista.columns:
        df_vista = df_vista[df_vista['Clase_ABC'] == filtro_abc]
    if filtro_kpi_stock and 'Stock_Minimo' in df_vista.columns:
        # Solo aplica cuando Stock_Minimo > 0, ignoramos productos sin mínimo configurado
        df_vista = df_vista[(df_vista['Stock_Minimo'] > 0) & (df_vista['Stock_Total'] < df_vista['Stock_Minimo'])]
    if filtro_kpi_venc:
        df_vista = df_vista[df_vista['Prox_Vencimiento'] < 15]
    if filtro_kpi_muerto and 'Stock_Muerto' in df_vista.columns:
        df_vista = df_vista[df_vista['Stock_Muerto'] == True]

# --- 7. MÉTRICAS ---
st.write("")
c_tc, m1, m2, m3, m4, m5 = st.columns([1.2, 1.8, 1.2, 1.2, 1.2, 1.2])
tc_usd = c_tc.number_input("💵 Tipo de Cambio (S/)", min_value=3.00, max_value=4.50, value=3.75, step=0.01)

style_metric_cards(background_color="#ffffff", border_left_color="#1e3d33")

val_pen    = df_vista['Valorizado_PEN'].sum()  if not df_vista.empty and 'Valorizado_PEN'    in df_vista.columns else 0.0
val_usd    = val_pen / tc_usd if tc_usd > 0 else 0.0
criticos   = len(df_vista[df_vista['Stock_Total'] <= 0])         if not df_vista.empty else 0
# ✅ FIX: solo lotes con stock real
x_vencer   = len(df_vista[df_vista['Prox_Vencimiento'] < 15])    if not df_vista.empty else 0
muertos    = len(df_vista[df_vista['Stock_Muerto'] == True])      if not df_vista.empty and 'Stock_Muerto'    in df_vista.columns else 0

# Días de cobertura promedio (solo productos con consumo real)
cob_valida = df_vista['Dias_Cobertura'].dropna() if not df_vista.empty and 'Dias_Cobertura' in df_vista.columns else pd.Series([])
cob_prom   = int(cob_valida.median()) if len(cob_valida) > 0 else 0

m1.metric("💰 Valorización",           f"S/ {val_pen:,.0f}",     f"${val_usd:,.0f} USD",   delta_color="off")
m2.metric("🔴 Sin Stock",              f"{criticos} productos",  delta_color="off")
m3.metric("⏳ Por Vencer (<15d)",      f"{x_vencer} productos",  delta_color="off")
m4.metric("💀 Stock Muerto",           f"{muertos} productos",   delta_color="off")
m5.metric("📅 Cobertura Mediana",      f"{cob_prom} días",
          help="Días que dura el stock actual al ritmo de consumo actual (mediana de todos los productos con salidas)")

# --- 8. TABLA PRINCIPAL (Vista por Producto) ---
st.write("")
st.markdown("#### 📊 Inventario Consolidado por Producto")

if not df_vista.empty:
    # Añadir columna de alerta visual
    def _alerta(row):
        if row['Stock_Total'] <= 0:                                              return "🔴 Sin Stock"
        if row.get('Stock_Minimo', 0) > 0 and row['Stock_Total'] < row['Stock_Minimo']: return "🟡 Stock Bajo"
        if row['Prox_Vencimiento'] < 15:                                         return "⏳ Por Vencer"
        if row.get('Stock_Muerto', False):                                       return "Sin Movimiento"
        return "🟢 OK"

    df_vista = df_vista.copy()
    df_vista['Alerta'] = df_vista.apply(_alerta, axis=1)

    cols_base    = ['Alerta', 'Clase_ABC', 'Codigo', 'Producto', 'Stock_Total', 'Unidad', 'Valorizado_PEN', 'Prox_Vencimiento']
    cols_visibles = [c for c in cols_base + mostrar_extras if c in df_vista.columns]

    # ✅ MEJORA 1: Tabla nativa de Streamlit con selección
    sel = st.dataframe(
        df_vista[cols_visibles],
        use_container_width=True,
        hide_index=True,
        height=420,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Alerta":           st.column_config.TextColumn("Estado",         width="small"),
            "Clase_ABC":        st.column_config.TextColumn("ABC",            width="small"),
            "Codigo":           st.column_config.TextColumn("Código",         width="small"),
            "Producto":         st.column_config.TextColumn("Producto",       width="large"),
            "Stock_Total":      st.column_config.NumberColumn("Stock Total",  format="%.2f"),
            "Valorizado_PEN":   st.column_config.NumberColumn("Valorizado (S/)", format="S/ %.2f"),
            "Prox_Vencimiento": st.column_config.NumberColumn("Días p/Vencer", format="%d días"),
            "N_Lotes":          st.column_config.NumberColumn("# Lotes",      width="small"),
            "Ficha_Tecnica_URL":st.column_config.LinkColumn("Ficha Técnica"),
        }
    )

    # Exportación Excel
    st.write("")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        df_vista[cols_visibles].to_excel(writer, index=False)
    st.download_button("📥 Descargar Reporte (Excel)", data=buffer.getvalue(),
                       file_name=f"Kardex_{date.today()}.xlsx",
                       mime="application/vnd.ms-excel")

    # --- 9. DETALLE DE LOTES AL SELECCIONAR UN PRODUCTO ---
    filas_sel = sel.selection.rows
    if filas_sel:
        idx       = filas_sel[0]
        cod_sel   = df_vista.iloc[idx]['Codigo']
        prod_sel  = df_vista.iloc[idx]['Producto']

        st.divider()
        st.markdown(f"#### 🗂️ Detalle de Lotes — **{prod_sel}** (`{cod_sel}`)")

        df_lotes_sel = df_kardex_lotes[df_kardex_lotes['Codigo'] == cod_sel].copy()
        if not df_lotes_sel.empty:
            cols_lote = ['Estado_Registro', 'Codigo_Lote', 'Stock_Lote', 'Precio_Unitario_PEN',
                         'Valorizado_PEN', 'Proveedor', 'Factura', 'Dias_para_Vencer', 'Responsable']
            cols_lote_ok = [c for c in cols_lote if c in df_lotes_sel.columns]
            st.dataframe(df_lotes_sel[cols_lote_ok], use_container_width=True, hide_index=True,
                         column_config={
                             "Precio_Unitario_PEN": st.column_config.NumberColumn("Precio U.", format="S/ %.2f"),
                             "Valorizado_PEN":      st.column_config.NumberColumn("Valorizado", format="S/ %.2f"),
                             "Dias_para_Vencer":    st.column_config.NumberColumn("Días p/Vencer", format="%d días"),
                         })
        else:
            st.info("Este producto no tiene lotes de ingreso registrados aún.")

        # Acciones de gestión
        c_acc1, c_acc2 = st.columns(2)

        # BOTÓN: EDITAR PRODUCTO MAESTRO
        if c_acc1.button("✏️ Editar Producto Master"):
            match = df_p[df_p['Codigo'] == cod_sel]
            if not match.empty:
                st.session_state.editing_product_id = int(match.iloc[0]['id'])
                st.rerun()

        # BOTÓN: ARCHIVAR PRODUCTO
        if c_acc2.button("📦 Archivar este Producto", type="secondary"):
            match = df_p[df_p['Codigo'] == cod_sel]
            if not match.empty:
                supabase.table('Productos').update({"Activo": False}).eq('id', int(match.iloc[0]['id'])).execute()
                st.success(f"'{prod_sel}' archivado correctamente.")
                # ✅ MEJORA 2: Caché específica, no global
                cargar_todo.clear()
                st.rerun()

        # Panel de ficha técnica / toxicidad
        row_data = df_vista.iloc[idx]
        banda    = str(row_data.get('Banda_Toxicologica', ''))
        ficha    = str(row_data.get('Ficha_Tecnica_URL', ''))
        obs_raw  = str(df_lotes_sel.get('Observaciones', pd.Series([''])).iloc[0] if not df_lotes_sel.empty else '')
        obs_clean = "Sin notas." if obs_raw.strip() in ['', 'None', 'nan'] else obs_raw

        with stylable_container("obs", css_styles="{ background-color:#e8f4fd; padding:10px; border-radius:8px; border:1px solid #b3d7ff; margin-top:8px;}"):
            c_s1, c_s2 = st.columns(2)
            if banda and banda not in ['nan', 'None', '']:
                c_s1.markdown(f"**☣️ Toxicidad:** {banda}")
            if ficha.startswith('http'):
                c_s2.markdown(f"[📄 Abrir Ficha Técnica]({ficha})")
            st.write(f"**💡 Obs. último lote:** {obs_clean}")

else:
    st.info("No hay productos que coincidan con los filtros aplicados.")

# --- 10. DIÁLOGO DE EDICIÓN ---
if st.session_state.editing_product_id:
    match_prod = df_p[df_p['id'] == st.session_state.editing_product_id]

    if not match_prod.empty:
        prod_to_edit = match_prod.iloc[0]

        # ✅ MEJORA 4: Lista de Formulación unificada con la misma del modal de creación
        FORMULACIONES_MASTER = [
            "pH — Reguladores de pH", "WSB — Bolsas hidrosolubles", "SG  — Gránulos solubles",
            "WG  — Gránulos dispersables", "WP  — Polvos mojables", "SC  — Suspensiones concentradas",
            "CS  — Suspensiones encapsuladas", "SE  — Suspoemulsiones", "OD  — Suspensiones concentradas oleosas",
            "EW  — Emulsiones acuosas", "EC  — Emulsiones concentradas", "SL  — Líquidos solubles",
            "Surfactante / Mojante", "Abono foliar", "Antideriva", "Otro"
        ]
        CATEGORIAS_MASTER = ["Insecticida", "Acaricida", "Fungicida", "Bactericida", "Herbicida",
                             "Defoliante", "Coadyuvante", "Regulador de pH", "Nematicida",
                             "Foliar", "Fertilizante", "Otro", "N/A"]
        BANDAS_MASTER = ["Verde (Ligeramente Tóxico)", "Azul (Moderadamente Tóxico)",
                         "Amarillo (Altamente Tóxico)", "Rojo (Extremadamente Tóxico)", "No Aplica"]

        @st.dialog("✏️ Editar Producto Maestro")
        def show_edit_dialog(p):
            with st.form("form_ed"):
                st.write(f"Editando: **{p['Producto']}**")

                col_a, col_b = st.columns(2)
                n_nombre = col_a.text_input("Nombre Comercial", value=str(p.get('Producto', '')))
                n_marca  = col_b.text_input("Marca / Laboratorio", value=str(p.get('Marca', '')) if pd.notna(p.get('Marca')) else '')

                n_ing = st.text_input("Ingrediente Activo",
                                      value=str(p.get('Ingrediente_Activo', '')) if pd.notna(p.get('Ingrediente_Activo')) else '')

                c1, c2, c3 = st.columns(3)
                n_min = c1.number_input("Stock Mínimo", value=float(p.get('Stock_Minimo', 0)))
                n_car = c2.number_input("Carencia (Días)", value=int(p.get('Periodo_Carencia_Dias', 0)))

                tipo_actual_str = str(p.get('Tipo_Accion', ''))
                tipos_previos   = [t.strip() for t in tipo_actual_str.split(',') if t.strip()] if tipo_actual_str not in ['nan', 'None'] else []
                tipos_validos   = [t for t in tipos_previos if t in CATEGORIAS_MASTER]
                n_tipo = c3.multiselect("Categoría", CATEGORIAS_MASTER, default=tipos_validos)

                c4, c5 = st.columns(2)
                form_actual = str(p.get('Formulacion', 'Otro'))
                idx_form    = FORMULACIONES_MASTER.index(form_actual) if form_actual in FORMULACIONES_MASTER else len(FORMULACIONES_MASTER) - 1
                n_form  = c4.selectbox("Formulación", FORMULACIONES_MASTER, index=idx_form)

                banda_actual = str(p.get('Banda_Toxicologica', 'No Aplica'))
                idx_banda    = BANDAS_MASTER.index(banda_actual) if banda_actual in BANDAS_MASTER else 4
                n_banda = c5.selectbox("Banda Toxicológica", BANDAS_MASTER, index=idx_banda)

                n_ficha = st.text_input("URL Ficha Técnica",
                                        value=str(p.get('Ficha_Tecnica_URL', '')) if pd.notna(p.get('Ficha_Tecnica_URL')) else '')
                n_inc   = st.text_area("Incompatibilidades",
                                       value=str(p.get('Incompatible_Con', '')) if pd.notna(p.get('Incompatible_Con')) else '')

                if st.form_submit_button("💾 Guardar Cambios"):
                    ing_limpios = ", ".join([i.strip().capitalize() for i in n_ing.split(",") if i.strip()]) if n_ing else None
                    data_upd = {
                        "Producto":           n_nombre.strip().upper(),
                        "Marca":              n_marca.strip().upper() if n_marca else None,
                        "Ingrediente_Activo": ing_limpios,
                        "Stock_Minimo":       n_min,
                        "Periodo_Carencia_Dias": n_car,
                        "Tipo_Accion":        ", ".join(n_tipo) if n_tipo else "N/A",
                        "Formulacion":        n_form,
                        "Banda_Toxicologica": n_banda,
                        "Ficha_Tecnica_URL":  n_ficha.strip() if n_ficha else None,
                        "Incompatible_Con":   n_inc.strip() if n_inc else None
                    }
                    supabase.table('Productos').update(data_upd).eq('id', p['id']).execute()
                    st.session_state.editing_product_id = None
                    # ✅ MEJORA 2: Caché específica
                    cargar_todo.clear()
                    st.rerun()

            if st.button("❌ Cancelar Edición"):
                st.session_state.editing_product_id = None
                st.rerun()

        show_edit_dialog(prod_to_edit)