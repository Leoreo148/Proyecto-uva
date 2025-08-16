import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Fundo")
st.write("Métricas clave de inventario, operaciones y sanidad para una visión completa del fundo.")

# --- FUNCIONES DE CARGA Y CÁLCULO (CENTRALIZADAS) ---

@st.cache_data
def cargar_datos(nombre_archivo, columnas_fecha=None):
    """Función genérica y segura para cargar cualquier archivo Excel."""
    if not os.path.exists(nombre_archivo):
        return None
    try:
        df = pd.read_excel(nombre_archivo)
        if columnas_fecha:
            for col in columnas_fecha:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col])
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo {nombre_archivo}: {e}")
        return None

def calcular_stock(df_ingresos, df_salidas):
    """Calcula el stock total y valorizado a partir de los movimientos."""
    if df_ingresos is None or df_ingresos.empty:
        return pd.DataFrame(), pd.DataFrame()
    
    ingresos_por_lote = df_ingresos.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Ingresada'})
    
    if df_salidas is not None and not df_salidas.empty and 'Codigo_Lote' in df_salidas.columns:
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

# --- CARGA DE TODOS LOS DATOS DE LA APLICACIÓN ---
df_kardex_ingresos = cargar_datos('kardex_fundo.xlsx', columnas_fecha=['Fecha', 'Fecha_Vencimiento'])
df_kardex_productos = cargar_datos('kardex_fundo.xlsx')
df_kardex_salidas = cargar_datos('kardex_fundo.xlsx', columnas_fecha=['Fecha'])
df_raleo = cargar_datos('Registro_Raleo.xlsx', columnas_fecha=['Fecha'])
df_horas_tractor = cargar_datos('Registro_Horas_Tractor.xlsx', columnas_fecha=['Fecha'])
df_ordenes = cargar_datos('Ordenes_de_Trabajo.xlsx', columnas_fecha=['Fecha_Programada', 'Aplicacion_Completada_Fecha'])
df_observaciones = cargar_datos('Observaciones_Campo.xlsx', columnas_fecha=['Fecha'])

# Calcular stock
df_stock_lotes = calcular_stock(df_kardex_ingresos, df_kardex_salidas)

# --- BARRA LATERAL CON FILTROS ---
st.sidebar.header("Filtros del Dashboard")
# Filtro de Fechas
today = datetime.now().date()
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=30))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# --- FILTRADO DE DATOS ---
df_raleo_filtrado = df_raleo[(df_raleo['Fecha'].dt.date >= fecha_inicio) & (df_raleo['Fecha'].dt.date <= fecha_fin)] if df_raleo is not None else None
df_horas_filtrado = df_horas_tractor[(df_horas_tractor['Fecha'].dt.date >= fecha_inicio) & (df_horas_tractor['Fecha'].dt.date <= fecha_fin)] if df_horas_tractor is not None else None
df_ordenes_filtrado = df_ordenes[(df_ordenes['Fecha_Programada'].dt.date >= fecha_inicio) & (df_ordenes['Fecha_Programada'].dt.date <= fecha_fin)] if df_ordenes is not None else None

# --- VISTA PRINCIPAL DEL DASHBOARD ---
st.header("Resumen General")

# --- MÉTRICAS CLAVE (KPIs) ---
col1, col2, col3, col4 = st.columns(4)

# KPI 1: Valor de Inventario
with col1:
    valor_total_inventario = df_stock_lotes['Valor_Lote'].sum() if not df_stock_lotes.empty else 0
    st.metric("💰 Valor del Inventario", f"S/ {valor_total_inventario:,.2f}")

# KPI 2: Lotes por Vencer
with col2:
    lotes_por_vencer = 0
    if not df_stock_lotes.empty and 'Fecha_Vencimiento' in df_stock_lotes.columns:
        df_stock_lotes_activos = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0]
        lotes_por_vencer = len(df_stock_lotes_activos[
            (df_stock_lotes_activos['Fecha_Vencimiento'].dt.date <= today + timedelta(days=30)) &
            (df_stock_lotes_activos['Fecha_Vencimiento'].dt.date >= today)
        ])
    st.metric("⚠️ Lotes por Vencer (30d)", f"{lotes_por_vencer} Lotes")

# KPI 3: Órdenes de Trabajo Activas
with col3:
    ordenes_activas = 0
    if df_ordenes is not None:
        ordenes_activas = len(df_ordenes[df_ordenes['Status'] != 'Completada'])
    st.metric("🛠️ Órdenes de Trabajo Activas", f"{ordenes_activas} Órdenes")
    
# KPI 4: Horas de Tractor en el Período
with col4:
    horas_totales = df_horas_filtrado['Total_Horas'].sum() if df_horas_filtrado is not None else 0
    st.metric(f"🚜 Horas de Tractor (Período)", f"{horas_totales:,.1f} Horas")

st.divider()

# --- GRÁFICOS ---
st.header("Análisis Visual")
gcol1, gcol2 = st.columns(2)

with gcol1:
    st.subheader("Valor de Inventario por Tipo")
    if df_kardex_productos is not None and not df_stock_lotes.empty:
        df_valor_tipo = pd.merge(df_stock_lotes, df_kardex_productos, on='Codigo_Producto', how='left')
        df_valor_tipo = df_valor_tipo.groupby('Tipo_Accion')['Valor_Lote'].sum().reset_index()
        fig_pie = px.pie(df_valor_tipo, values='Valor_Lote', names='Tipo_Accion', title="Distribución del Valor en Almacén", hole=.3)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hay datos de inventario para mostrar.")

with gcol2:
    st.subheader("Actividad del Fundo (Período Seleccionado)")
    actividades = {
        "Ingresos Registrados": len(df_kardex_ingresos[(df_kardex_ingresos['Fecha'].dt.date >= fecha_inicio) & (df_kardex_ingresos['Fecha'].dt.date <= fecha_fin)]) if df_kardex_ingresos is not None else 0,
        "Jornadas de Raleo": df_raleo_filtrado['Fecha'].nunique() if df_raleo_filtrado is not None else 0,
        "Aplicaciones Completadas": len(df_ordenes_filtrado[df_ordenes_filtrado['Status'] == 'Completada']) if df_ordenes_filtrado is not None else 0
    }
    df_actividad = pd.DataFrame(list(actividades.items()), columns=['Actividad', 'Cantidad'])
    fig_bar = px.bar(df_actividad, x='Actividad', y='Cantidad', title="Resumen de Operaciones", text='Cantidad')
    st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# --- ALERTAS DE SANIDAD (SIMPLIFICADO) ---
st.header("Alertas de Sanidad")
if df_observaciones is not None:
    ultima_obs = df_observaciones.loc[df_observaciones.groupby('Sector')['Fecha'].idxmax()]
    umbral_oidio = st.slider("Umbral de Alerta de Oídio:", min_value=1, max_value=4, value=3, key='slider_oidio')
    sectores_en_alerta = ultima_obs[ultima_obs['Severidad_Oidio'] >= umbral_oidio]
    
    if not sectores_en_alerta.empty:
        st.warning("¡Sectores con alta severidad de Oídio!")
        for _, row in sectores_en_alerta.iterrows():
            st.error(f"**Sector:** {row['Sector']} | **Severidad:** {row['Severidad_Oidio']}")
    else:
        st.success("✅ Sin alertas críticas de Oídio en la última evaluación.")
else:
    st.info("No se han cargado datos de observación de Oídio.")
