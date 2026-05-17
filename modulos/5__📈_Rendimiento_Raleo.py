import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO
from supabase import create_client, Client

# 🚨 CANDADO DE SEGURIDAD (Colocar al inicio de la página, justo debajo de los imports)
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal antes de acceder a este módulo.")
    st.stop() # Frena la ejecución del resto del código de golpe

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Raleo", page_icon="📈", layout="wide")
st.title("📈 Dashboard de Rendimiento de Raleo")
st.write("Analiza el rendimiento del personal, calcula los pagos y visualiza el avance por fecha y sector.")

# --- CONSTANTES ---
# Define la tarifa que se paga por cada racimo real contado.
TARIFA_POR_RACIMO = 0.07

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

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_raleo_supabase():
    """Carga, limpia y procesa los datos de raleo desde la tabla de Supabase."""
    if supabase is None:
        return pd.DataFrame()
    
    try:
        response = supabase.table('Control_Raleo').select("*").execute()
        df = pd.DataFrame(response.data)
        
        if df.empty:
            return pd.DataFrame()

        # Limpieza y procesamiento de datos
        df['Fecha'] = pd.to_datetime(df['Fecha'])
        # --- MODIFICADO: Usamos 'Racimos_Reales' para el cálculo del pago ---
        df['Pago_Calculado_S'] = df['Racimos_Reales'] * TARIFA_POR_RACIMO
        return df
    except Exception as e:
        st.error(f"Error al cargar los datos de raleo: {e}")
        return pd.DataFrame()

def to_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria para descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Raleo')
    return output.getvalue()

# --- CARGA Y FILTROS ---
df_raleo = cargar_datos_raleo_supabase()

if df_raleo.empty:
    st.warning("Aún no se ha registrado ninguna jornada de raleo. Por favor, ingrese datos en 'Control de Raleo'.")
    st.stop()

st.sidebar.header("Filtros del Dashboard")

# Filtro de Fechas
today = datetime.now().date()
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=7))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# Filtro de Sector
sectores = ['Todos'] + sorted(df_raleo['Sector'].unique().tolist())
sector_seleccionado = st.sidebar.selectbox("Seleccione un Sector", options=sectores)

# NUEVO: Filtro de Trabajador para armar planillas de pago individuales
trabajadores = ['Todos'] + sorted(df_raleo['Nombre_del_Trabajador'].unique().tolist())
trabajador_seleccionado = st.sidebar.selectbox("Seleccione un Trabajador", options=trabajadores)

# Aplicar filtros al DataFrame
df_filtrado = df_raleo[
    (df_raleo['Fecha'].dt.date >= fecha_inicio) &
    (df_raleo['Fecha'].dt.date <= fecha_fin)
]
if sector_seleccionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['Sector'] == sector_seleccionado]
if trabajador_seleccionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['Nombre_del_Trabajador'] == trabajador_seleccionado]

# --- DASHBOARD ---
if df_filtrado.empty:
    st.info("No se encontraron registros para los filtros seleccionados.")
else:
    st.header(f"Mostrando Datos del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")

    # --- MODIFICADO: KPIs con Racimos_Reales ---
    total_racimos = df_filtrado['Racimos_Reales'].sum()
    pago_total = df_filtrado['Pago_Calculado_S'].sum()
    promedio_diario = total_racimos / df_filtrado['Fecha'].nunique() if df_filtrado['Fecha'].nunique() > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Racimos Reales", f"{total_racimos:,.0f}")
    col2.metric("Pago Total Calculado", f"S/ {pago_total:,.2f}")
    col3.metric("Promedio Racimos por Día", f"{promedio_diario:,.1f}")

    st.divider()

    # --- MODIFICADO: Gráficos con Racimos_Reales ---
    # --- MODIFICADO: Gráficos a 3 columnas para incluir Análisis de Costos ---
    col_graf1, col_graf2, col_graf3 = st.columns(3)
    
    with col_graf1:
        st.subheader("🏆 Ranking de Personal")
        df_ranking = df_filtrado.groupby('Nombre_del_Trabajador').agg(
            Total_Racimos=('Racimos_Reales', 'sum')
        ).sort_values(by='Total_Racimos', ascending=False).reset_index().head(10) # Top 10 para no saturar

        fig_ranking = px.bar(
            df_ranking, x='Total_Racimos', y='Nombre_del_Trabajador', orientation='h',
            title='Top 10: Racimos por Persona', text='Total_Racimos',
            color_discrete_sequence=['#2ecc71']
        )
        fig_ranking.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_ranking, use_container_width=True)

    with col_graf2:
        st.subheader("📅 Evolución Diaria")
        df_evolucion = df_filtrado.groupby(df_filtrado['Fecha'].dt.date)['Racimos_Reales'].sum().reset_index()
        fig_evolucion = px.line(
            df_evolucion, x='Fecha', y='Racimos_Reales',
            title='Avance Total por Día', markers=True,
            color_discrete_sequence=['#e74c3c']
        )
        st.plotly_chart(fig_evolucion, use_container_width=True)

    with col_graf3:
        st.subheader("💰 Inversión por Sector")
        df_sector_costo = df_filtrado.groupby('Sector')['Pago_Calculado_S'].sum().reset_index()
        fig_sector = px.pie(
            df_sector_costo, values='Pago_Calculado_S', names='Sector', 
            title='Distribución de Pago por Lote', hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Prism
        )
        st.plotly_chart(fig_sector, use_container_width=True)
    
    st.divider()

    # --- MODIFICADO: Tabla detallada con nuevas columnas ---
    st.subheader("📋 Tabla de Datos Detallada")
    columnas_display = ['Fecha', 'Sector', 'Evaluador', 'Numero_de_Fila', 'Nombre_del_Trabajador', 'Racimos_Reales', 'Tandas_Equivalentes', 'Pago_Calculado_S']
    df_display = df_filtrado.copy()
    df_display['Pago_Calculado_S'] = df_display['Pago_Calculado_S'].round(2)
    df_display['Tandas_Equivalentes'] = df_display['Tandas_Equivalentes'].round(1)
    
    st.dataframe(df_display[columnas_display].sort_values(by="Fecha", ascending=False), use_container_width=True)
    
    excel_data = to_excel(df_filtrado[columnas_display])
    st.download_button(
        label="📥 Descargar Reporte Filtrado a Excel",
        data=excel_data,
        file_name=f"Reporte_Raleo_{fecha_inicio.strftime('%Y%m%d')}_al_{fecha_fin.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
