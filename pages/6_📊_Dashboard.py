import streamlit as st
import pandas as pd
import os
import plotly.express as px

# --- Configuración de la Página ---
st.set_page_config(page_title="Dashboard de Análisis", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Análisis del Fundo")
st.write("Visualice las tendencias, el estado del cultivo y las alertas críticas.")

# --- Función para Cargar Datos de Forma Segura ---
def cargar_datos(nombre_archivo):
    if os.path.exists(nombre_archivo):
        try:
            return pd.read_excel(nombre_archivo)
        except Exception as e:
            st.error(f"Error al leer el archivo {nombre_archivo}: {e}")
            return None
    return None

# --- Carga de Datos ---
df_plagas = cargar_datos('Monitoreo_Plagas_Detallado.xlsx')
df_fenologia = cargar_datos('Evaluacion_Fenologica_Detallada.xlsx')

# --- Barra Lateral con Filtros ---
st.sidebar.header("Filtros del Dashboard")

# Definir umbral de alerta para plagas
umbral_alerta_plagas = st.sidebar.number_input(
    "Umbral de Alerta para Capturas Totales:",
    min_value=1,
    value=7, # Valor por defecto, el ingeniero puede cambiarlo
    step=1,
    help="Número de capturas totales en una trampa para generar una alerta."
)

# --- Lógica MEJORADA para obtener TODOS los sectores ---
sectores_plagas = []
if df_plagas is not None:
    sectores_plagas = df_plagas['Sector'].unique().tolist()

sectores_fenologia = []
if df_fenologia is not None:
    # Asumiendo que el archivo de fenología también tiene una columna 'Sector'
    if 'Sector' in df_fenologia.columns:
        sectores_fenologia = df_fenologia['Sector'].unique().tolist()

# Combinamos las listas de ambos archivos y eliminamos duplicados
todos_los_sectores = sorted(list(set(sectores_plagas + sectores_fenologia)))

# Si después de todo no hay sectores, usamos una lista por defecto
if not todos_los_sectores:
    todos_los_sectores = ['General']

sector_seleccionado = st.sidebar.selectbox(
    "Seleccione un Sector para Analizar:",
    options=todos_los_sectores
)

st.header(f"Análisis para el Sector: {sector_seleccionado}")
st.divider()

# --- Módulo de Alertas y Umbrales ---
st.subheader("🚨 Alertas Críticas")

if df_plagas is not None:
    df_plagas['Fecha'] = pd.to_datetime(df_plagas['Fecha'])
    ultimos_registros = df_plagas.loc[df_plagas.groupby('Codigo_Trampa')['Fecha'].idxmax()]
    trampas_en_alerta = ultimos_registros[ultimos_registros['Total_Capturas'] >= umbral_alerta_plagas]
    
    if not trampas_en_alerta.empty:
        st.warning(f"¡Atención! Se han detectado {len(trampas_en_alerta)} trampas que superan el umbral de {umbral_alerta_plagas} capturas.")
        alert_cols = st.columns(3)
        col_idx = 0
        for index, row in trampas_en_alerta.iterrows():
            with alert_cols[col_idx % 3]:
                st.error(
                    f"""
                    **Trampa:** {row['Codigo_Trampa']}  
                    **Sector:** {row['Sector']}  
                    **Capturas Totales:** {row['Total_Capturas']}  
                    **Fecha de Conteo:** {row['Fecha'].strftime('%d/%m/%Y')}
                    """
                )
            col_idx += 1
    else:
        st.success("✅ No hay trampas que superen el umbral de alerta. ¡Buen trabajo!")
else:
    st.info("No hay datos de monitoreo de plagas para generar alertas.")

st.divider()

# --- Módulo de Gráficos ---

# Análisis de Monitoreo de Plagas
st.subheader("🪰 Evolución de Capturas de Mosca de la Fruta")
if df_plagas is not None and sector_seleccionado in df_plagas['Sector'].unique():
    df_plagas_sector = df_plagas[df_plagas['Sector'] == sector_seleccionado]
    df_plagas_sector['Fecha'] = pd.to_datetime(df_plagas_sector['Fecha'])
    capturas_por_dia = df_plagas_sector.groupby('Fecha')['Total_Capturas'].sum().reset_index()
    fig_plagas = px.line(capturas_por_dia, x='Fecha', y='Total_Capturas', title=f'Total de Capturas Diarias en el Sector {sector_seleccionado}', markers=True)
    st.plotly_chart(fig_plagas, use_container_width=True)
else:
