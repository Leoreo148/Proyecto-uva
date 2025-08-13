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
df_observaciones = cargar_datos('Observaciones_Campo.xlsx')

# --- Barra Lateral con Filtros ---
st.sidebar.header("Filtros y Umbrales del Dashboard")

umbral_alerta_plagas = st.sidebar.number_input(
    "Umbral de Alerta para Capturas Totales:",
    min_value=1, value=7, step=1,
    help="Número de capturas totales en una trampa para generar una alerta."
)

umbral_alerta_oidio = st.sidebar.slider(
    "Umbral de Alerta para Severidad de Oídio:",
    min_value=1, max_value=4, value=3,
    help="Nivel de severidad para generar una alerta de oídio."
)

# --- Lógica para obtener TODOS los sectores ---
sectores_plagas = df_plagas['Sector'].unique().tolist() if df_plagas is not None else []
sectores_fenologia = df_fenologia['Sector'].unique().tolist() if df_fenologia is not None and 'Sector' in df_fenologia.columns else []
sectores_observaciones = df_observaciones['Sector'].unique().tolist() if df_observaciones is not None else []

todos_los_sectores = sorted(list(set(sectores_plagas + sectores_fenologia + sectores_observaciones)))
if not todos_los_sectores:
    todos_los_sectores = ['General']

sector_seleccionado = st.sidebar.selectbox(
    "Seleccione un Sector para Analizar:",
    options=todos_los_sectores
)

st.header(f"Análisis para el Sector: {sector_seleccionado}")
st.divider()

# --- Módulo de Alertas Críticas ---
st.subheader("🚨 Alertas Críticas")

col_oidio, col_plagas = st.columns(2)
with col_oidio:
    st.markdown("##### Alertas de Oídio")
    if df_observaciones is not None:
        # CORRECCIÓN: Verificamos si la columna existe antes de usarla
        if 'Severidad_Oidio' in df_observaciones.columns:
            df_observaciones['Fecha'] = pd.to_datetime(df_observaciones['Fecha'])
            ultimas_obs = df_observaciones.loc[df_observaciones.groupby('Sector')['Fecha'].idxmax()]
            sectores_en_alerta = ultimas_obs[ultimas_obs['Severidad_Oidio'] >= umbral_alerta_oidio]
            
            if not sectores_en_alerta.empty:
                for index, row in sectores_en_alerta.iterrows():
                    st.error(f"**Sector:** {row['Sector']} | **Severidad:** {row['Severidad_Oidio']} | **Fecha:** {row['Fecha'].strftime('%d/%m/%Y')}")
            else:
                st.success("✅ Sin alertas de oídio.")
        else:
            st.error("Error: La columna 'Severidad_Oidio' no se encuentra en 'Observaciones_Campo.xlsx'.")
    else:
        st.info("No hay datos de oídio.")

with col_plagas:
    st.markdown("##### Alertas de Plagas")
    if df_plagas is not None:
        df_plagas['Fecha'] = pd.to_datetime(df_plagas['Fecha'])
        ultimos_registros = df_plagas.loc[df_plagas.groupby('Codigo_Trampa')['Fecha'].idxmax()]
        trampas_en_alerta = ultimos_registros[ultimos_registros['Total_Capturas'] >= umbral_alerta_plagas]
        
        if not trampas_en_alerta.empty:
            for index, row in trampas_en_alerta.iterrows():
                st.warning(f"**Trampa:** {row['Codigo_Trampa']} | **Capturas:** {row['Total_Capturas']} | **Sector:** {row['Sector']}")
        else:
            st.success("✅ Sin alertas de plagas.")
    else:
        st.info("No hay datos de plagas.")

st.divider()

# --- Módulo de Gráficos ---
# (El resto del código se mantiene igual)
st.subheader("🪰 Evolución de Capturas de Mosca de la Fruta")
if df_plagas is not None and sector_seleccionado in df_plagas['Sector'].unique():
    df_plagas_sector = df_plagas[df_plagas['Sector'] == sector_seleccionado]
    df_plagas_sector['Fecha'] = pd.to_datetime(df_plagas_sector['Fecha'])
    capturas_por_dia = df_plagas_sector.groupby('Fecha')['Total_Capturas'].sum().reset_index()
    fig_plagas = px.line(capturas_por_dia, x='Fecha', y='Total_Capturas', title=f'Total de Capturas Diarias en el Sector {sector_seleccionado}', markers=True)
    st.plotly_chart(fig_plagas, use_container_width=True)
else:
    st.info(f"No hay registros de monitoreo de plagas para el sector '{sector_seleccionado}'.")

st.divider()

st.subheader("🌱 Distribución Fenológica Reciente")
if df_fenologia is not None and sector_seleccionado in df_fenologia['Sector'].unique():
    df_fenologia_sector = df_fenologia[df_fenologia['Sector'] == sector_seleccionado]
    ultima_fecha = df_fenologia_sector['Fecha'].max()
    st.write(f"Mostrando la última evaluación realizada el: **{pd.to_datetime(ultima_fecha).strftime('%d/%m/%Y')}**")
    df_ultima_evaluacion = df_fenologia_sector[df_fenologia_sector['Fecha'] == ultima_fecha]
    columnas_estados = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
    resumen_fenologia = df_ultima_evaluacion[columnas_estados].sum()
    fig_fenologia = px.pie(values=resumen_fenologia.values, names=resumen_fenologia.index, title=f'Distribución de Estados Fenológicos en el Sector {sector_seleccionado}')
    st.plotly_chart(fig_fenologia, use_container_width=True)
else:
    st.info(f"No hay registros de evaluación fenológica para el sector '{sector_seleccionado}'.")

