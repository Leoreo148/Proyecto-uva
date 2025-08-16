import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import plotly.express as px
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Raleo", page_icon="📈", layout="wide")
st.title("📈 Dashboard de Rendimiento de Raleo")
st.write("Analiza el rendimiento del personal, calcula los pagos y visualiza el avance por fecha y sector.")

# --- CONSTANTES ---
TARIFA_POR_RACIMO = 0.07
ARCHIVO_RALEO = 'Registro_Raleo.xlsx'

# --- FUNCIONES ---
def cargar_datos_raleo():
    """Carga, limpia y procesa los datos de raleo desde el archivo Excel."""
    if not os.path.exists(ARCHIVO_RALEO):
        return pd.DataFrame()
    
    df = pd.read_excel(ARCHIVO_RALEO)
    df['Fecha'] = pd.to_datetime(df['Fecha'])
    df['Pago Calculado (S/)'] = df['Racimos Raleados'] * TARIFA_POR_RACIMO
    return df

def to_excel(df):
    """Convierte un DataFrame a un archivo Excel en memoria para descarga."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Raleo')
    return output.getvalue()

# --- CARGA Y FILTROS ---
# La línea @st.cache_data ha sido eliminada de la función de carga
df_raleo = cargar_datos_raleo()

if df_raleo.empty:
    st.warning("Aún no se ha registrado ninguna jornada de raleo. Por favor, ingrese datos en 'Control de Raleo'.")
    st.stop()

st.sidebar.header("Filtros del Dashboard")

# Filtro de Fechas
today = datetime.now().date()
# Usamos .date() para asegurar que no haya conflictos de zona horaria
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=7))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# Filtro de Sector
sectores = ['Todos'] + sorted(df_raleo['Sector'].unique().tolist())
sector_seleccionado = st.sidebar.selectbox("Seleccione un Sector", options=sectores)

# Aplicar filtros al DataFrame
df_filtrado = df_raleo[
    (df_raleo['Fecha'].dt.date >= fecha_inicio) &
    (df_raleo['Fecha'].dt.date <= fecha_fin)
]
if sector_seleccionado != 'Todos':
    df_filtrado = df_filtrado[df_filtrado['Sector'] == sector_seleccionado]

# --- DASHBOARD ---
if df_filtrado.empty:
    st.info("No se encontraron registros para los filtros seleccionados.")
else:
    st.header(f"Mostrando Datos del {fecha_inicio.strftime('%d/%m/%Y')} al {fecha_fin.strftime('%d/%m/%Y')}")

    # KPIs
    total_racimos = df_filtrado['Racimos Raleados'].sum()
    pago_total = df_filtrado['Pago Calculado (S/)'].sum()
    promedio_diario = total_racimos / df_filtrado['Fecha'].nunique() if df_filtrado['Fecha'].nunique() > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Racimos Raleados", f"{total_racimos:,.0f}")
    col2.metric("Pago Total Calculado", f"S/ {pago_total:,.2f}")
    col3.metric("Promedio Racimos por Día", f"{promedio_diario:,.1f}")

    st.divider()

    # Gráficos
    col_graf1, col_graf2 = st.columns(2)
    with col_graf1:
        st.subheader("🏆 Ranking de Personal")
        df_ranking = df_filtrado.groupby('Nombre del Trabajador').agg(
            Total_Racimos=('Racimos Raleados', 'sum'),
            Pago_Total=('Pago Calculado (S/)', 'sum')
        ).sort_values(by='Total_Racimos', ascending=False).reset_index()

        fig_ranking = px.bar(
            df_ranking, x='Total_Racimos', y='Nombre del Trabajador', orientation='h',
            title='Total de Racimos Raleados por Persona', text='Total_Racimos',
            labels={'Nombre del Trabajador': 'Trabajador', 'Total_Racimos': 'Nº de Racimos'}
        )
        fig_ranking.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_ranking, use_container_width=True)

    with col_graf2:
        st.subheader("📅 Evolución Diaria del Raleo")
        df_evolucion = df_filtrado.groupby(df_filtrado['Fecha'].dt.date)['Racimos Raleados'].sum().reset_index()
        fig_evolucion = px.line(
            df_evolucion, x='Fecha', y='Racimos Raleados',
            title='Total de Racimos Raleados por Día', markers=True,
            labels={'Fecha': 'Día', 'Racimos Raleados': 'Nº de Racimos'}
        )
        st.plotly_chart(fig_evolucion, use_container_width=True)
    
    st.divider()

    # Tabla detallada y botón de descarga
    st.subheader("📋 Tabla de Datos Detallada")
    # Aseguramos que el pago tenga 2 decimales en la tabla
    df_display = df_filtrado.copy()
    df_display['Pago Calculado (S/)'] = df_display['Pago Calculado (S/)'].round(2)
    st.dataframe(df_display[['Fecha', 'Sector', 'Nombre del Trabajador', 'Racimos Raleados', 'Pago Calculado (S/)']].sort_values(by="Fecha", ascending=False), use_container_width=True)
    
    excel_data = to_excel(df_filtrado)
    st.download_button(
        label="📥 Descargar Reporte Filtrado a Excel",
        data=excel_data,
        file_name=f"Reporte_Raleo_{fecha_inicio.strftime('%Y%m%d')}_al_{fecha_fin.strftime('%Y%m%d')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
