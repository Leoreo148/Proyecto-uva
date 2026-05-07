import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Fundo")
st.write("Métricas clave de inventario, operaciones y estado del cultivo para una visión completa.")

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

# --- FUNCIÓN DE CARGA DE DATOS CENTRALIZADA ---
@st.cache_data(ttl=600) # Cachear los datos por 10 minutos
def cargar_todos_los_datos_supabase():
    """Carga todos los DataFrames necesarios para el dashboard desde Supabase."""
    if not supabase:
        return { "error": "No se pudo conectar a Supabase." }
    
    tablas_a_cargar = [
        "Productos", "Ingresos", "Salidas", "Control_Raleo", 
        "Registro_Horas_Tractor", "Ordenes_de_Trabajo", 
        "Diametro_Baya", "Monitoreo_Mosca"
    ]
    
    dataframes = {}
    try:
        for tabla in tablas_a_cargar:
            response = supabase.table(tabla).select("*").execute()
            dataframes[tabla] = pd.DataFrame(response.data)
        return dataframes
    except Exception as e:
        st.error(f"Error al cargar la tabla '{tabla}': {e}")
        return { "error": f"Fallo al cargar la tabla {tabla}." }

# --- FUNCIÓN DE CÁLCULO DE STOCK (REUTILIZADA) ---
def calcular_stock(df_ingresos, df_salidas):
    if df_ingresos.empty:
        return pd.DataFrame()
    
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
        
    lote_info = df_ingresos.drop_duplicates(subset=['Codigo_Lote'])
    stock_lotes_detallado = pd.merge(stock_lotes, lote_info, on='Codigo_Lote', how='left')
    
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    return stock_lotes_detallado

# --- CARGA Y PROCESAMIENTO PRINCIPAL ---
data = cargar_todos_los_datos_supabase()

if "error" in data:
    st.stop()

# Asignar DataFrames a variables para claridad
df_productos = data.get("Productos", pd.DataFrame())
df_ingresos = data.get("Ingresos", pd.DataFrame())
df_salidas = data.get("Salidas", pd.DataFrame())
df_raleo = data.get("Control_Raleo", pd.DataFrame())
df_horas_tractor = data.get("Registro_Horas_Tractor", pd.DataFrame())
df_ordenes = data.get("Ordenes_de_Trabajo", pd.DataFrame())
df_baya = data.get("Diametro_Baya", pd.DataFrame())
df_mosca = data.get("Monitoreo_Mosca", pd.DataFrame())

# Convertir columnas de fecha
for df, cols in [(df_ingresos, ['Fecha', 'Fecha_Vencimiento']), (df_salidas, ['Fecha']), 
                 (df_raleo, ['Fecha']), (df_horas_tractor, ['Fecha']), 
                 (df_ordenes, ['Fecha_Programada', 'Aplicacion_Completada_Fecha']), 
                 (df_baya, ['Fecha']), (df_mosca, ['Fecha'])]:
    if not df.empty:
        for col in cols:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors='coerce')

df_stock_lotes = calcular_stock(df_ingresos, df_salidas)

# --- BARRA LATERAL Y FILTROS ---
st.sidebar.header("Filtros del Dashboard")
today = datetime.now().date()
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=30))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# --- VISTA PRINCIPAL ---
st.header("Resumen General del Fundo")

# --- KPIs ---
kpi_cols = st.columns(6)

with kpi_cols[0]:
    valor_total_inventario = df_stock_lotes['Valor_Lote'].sum() if not df_stock_lotes.empty else 0
    st.metric("💰 Valor Inventario", f"S/ {valor_total_inventario:,.2f}")

with kpi_cols[1]:
    ordenes_activas = len(df_ordenes[df_ordenes['Status'] != 'Completada']) if not df_ordenes.empty else 0
    st.metric("🛠️ Órdenes Activas", f"{ordenes_activas}")

with kpi_cols[2]:
    df_horas_filtrado = df_horas_tractor[(df_horas_tractor['Fecha'].dt.date >= fecha_inicio) & (df_horas_tractor['Fecha'].dt.date <= fecha_fin)] if not df_horas_tractor.empty else pd.DataFrame()
    horas_totales = df_horas_filtrado['Total_Horas'].sum() if not df_horas_filtrado.empty else 0
    st.metric(f"🚜 Horas Tractor (Período)", f"{horas_totales:,.1f} h")

with kpi_cols[3]:
    diametro_promedio = 0
    if not df_baya.empty:
        ultima_fecha_baya = df_baya['Fecha'].max()
        df_ultima_medicion = df_baya[df_baya['Fecha'] == ultima_fecha_baya]
        columnas_medicion = [col for col in df_ultima_medicion.columns if 'Racimo' in col]
        if columnas_medicion:
            valores = df_ultima_medicion[columnas_medicion].to_numpy().flatten()
            diametro_promedio = valores[valores > 0].mean() if len(valores[valores > 0]) > 0 else 0
    st.metric("🍇 Diámetro Baya (Últ. Med.)", f"{diametro_promedio:.2f} mm")

with kpi_cols[4]:
    umbral_mosca = st.number_input("Umbral MTD:", min_value=0.1, value=0.5, step=0.1, key="umbral_kpi", help="Moscas por Trampa por Día")
    sectores_en_alerta = 0
    if not df_mosca.empty:
        df_mosca['Total_Capturas'] = df_mosca[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum(axis=1)
        df_ultimas_moscas = df_mosca.loc[df_mosca.groupby('Numero_Trampa')['Fecha'].idxmax()]
        # Asumiendo 7 días de evaluación para el MTD
        df_ultimas_moscas['MTD'] = df_ultimas_moscas['Total_Capturas'] / 7
        trampas_en_alerta = df_ultimas_moscas[df_ultimas_moscas['MTD'] >= umbral_mosca]
        sectores_en_alerta = trampas_en_alerta['Sector'].nunique()
    st.metric("🪰 Sectores en Alerta (Mosca)", f"{sectores_en_alerta}")
    
with kpi_cols[5]:
    lotes_por_vencer = 0
    if not df_stock_lotes.empty and 'Fecha_Vencimiento' in df_stock_lotes.columns:
        df_stock_lotes['Fecha_Vencimiento'] = pd.to_datetime(df_stock_lotes['Fecha_Vencimiento'], errors='coerce')
        df_activos = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0].dropna(subset=['Fecha_Vencimiento'])
        lotes_por_vencer = len(df_activos[(df_activos['Fecha_Vencimiento'].dt.date <= today + timedelta(days=30)) & (df_activos['Fecha_Vencimiento'].dt.date >= today)])
    st.metric("⚠️ Lotes por Vencer (30d)", f"{lotes_por_vencer}")

st.divider()

# --- GRÁFICOS Y WIDGETS SELECCIONABLES ---
st.header("Análisis Detallado")
opciones_widgets = ["Inventario", "Rendimiento de Raleo", "Horas de Tractor", "Monitoreo de Mosca"]
widgets_seleccionados = st.multiselect(
    "Seleccione los widgets que desea visualizar:",
    options=opciones_widgets,
    default=opciones_widgets
)

if "Inventario" in widgets_seleccionados:
    with st.container(border=True):
        st.subheader("📦 Resumen de Inventario")
        gcol1, gcol2 = st.columns(2)
        with gcol1:
            if not df_stock_lotes.empty and not df_productos.empty:
                df_valor_tipo = pd.merge(df_stock_lotes, df_productos, left_on='Codigo_Producto', right_on='Codigo', how='left')
                df_valor_tipo = df_valor_tipo.groupby('Tipo_Accion')['Valor_Lote'].sum().reset_index()
                fig_pie = px.pie(df_valor_tipo, values='Valor_Lote', names='Tipo_Accion', title="Distribución del Valor en Almacén", hole=.3)
                st.plotly_chart(fig_pie, use_container_width=True)
        with gcol2:
            st.write("**Productos con Stock Bajo**")
            if not df_stock_lotes.empty and not df_productos.empty:
                df_stock_total = df_stock_lotes.groupby('Codigo_Producto')['Stock_Restante'].sum().reset_index()
                df_stock_alert = pd.merge(df_stock_total, df_productos, left_on='Codigo_Producto', right_on='Codigo')
                df_stock_alert = df_stock_alert[df_stock_alert['Stock_Restante'] < df_stock_alert['Stock_Minimo']]
                st.dataframe(df_stock_alert[['Producto', 'Stock_Restante', 'Stock_Minimo']], use_container_width=True)

if "Rendimiento de Raleo" in widgets_seleccionados:
    with st.container(border=True):
        st.subheader("✂️ Rendimiento de Raleo (Período Seleccionado)")
        df_raleo_filtrado = df_raleo[(df_raleo['Fecha'].dt.date >= fecha_inicio) & (df_raleo['Fecha'].dt.date <= fecha_fin)] if not df_raleo.empty else pd.DataFrame()
        if not df_raleo_filtrado.empty:
            df_ranking = df_raleo_filtrado.groupby('Nombre_del_Trabajador')['Racimos_Estimados'].sum().sort_values(ascending=False).reset_index().head(10)
            fig_ranking = px.bar(df_ranking, x='Racimos_Estimados', y='Nombre_del_Trabajador', orientation='h', title='Top 10 Personal de Raleo', text='Racimos_Estimados')
            fig_ranking.update_layout(yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_ranking, use_container_width=True)
        else:
            st.info("No hay datos de raleo para el período seleccionado.")

if "Horas de Tractor" in widgets_seleccionados:
     with st.container(border=True):
        st.subheader("🚜 Control de Mantenimiento de Tractores")
        if not df_horas_tractor.empty:
            df_horas_acumuladas = df_horas_tractor.groupby('Tractor')['Total_Horas'].sum().reset_index()
            df_horas_acumuladas['Proximo_Mantenimiento'] = 300 # Límite de horas
            df_horas_acumuladas['Progreso_%'] = (df_horas_acumuladas['Total_Horas'] % 300) / 300 * 100
            
            for index, row in df_horas_acumuladas.iterrows():
                st.text(f"Tractor: {row['Tractor']} (Total Horas: {row['Total_Horas']:.1f})")
                st.progress(int(row['Progreso_%']))
        else:
            st.info("No hay registros de horas de tractor.")

if "Monitoreo de Mosca" in widgets_seleccionados:
    with st.container(border=True):
        st.subheader("🪰 Focos de Mosca de la Fruta (Última Semana)")
        if not df_mosca.empty:
            df_mosca_semana = df_mosca[df_mosca['Fecha'].dt.date >= (today - timedelta(days=7))]
            if not df_mosca_semana.empty:
                df_mosca_semana['Total_Capturas'] = df_mosca_semana[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum(axis=1)
                df_capturas_sector = df_mosca_semana.groupby('Sector')['Total_Capturas'].sum().sort_values(ascending=False).reset_index()
                fig_mosca = px.bar(df_capturas_sector, x='Sector', y='Total_Capturas', title='Total Capturas por Sector (Últimos 7 días)', text='Total_Capturas')
                st.plotly_chart(fig_mosca, use_container_width=True)
            else:
                st.info("No hay capturas de mosca registradas en los últimos 7 días.")
