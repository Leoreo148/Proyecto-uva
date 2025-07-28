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

# Creamos una lista de sectores disponibles a partir de los datos existentes
if df_plagas is not None:
    sectores_disponibles = sorted(df_plagas['Sector'].unique().tolist())
else:
    sectores_disponibles = ['General']

sector_seleccionado = st.sidebar.selectbox(
    "Seleccione un Sector para Analizar:",
    options=sectores_disponibles
)

st.header(f"Análisis para el Sector: {sector_seleccionado}")
st.divider()

# --- Módulo NUEVO: Alertas y Umbrales ---
st.subheader("🚨 Alertas Críticas")

if df_plagas is not None:
    # Nos aseguramos que la columna Fecha sea de tipo datetime
    df_plagas['Fecha'] = pd.to_datetime(df_plagas['Fecha'])
    
    # Encontramos el último registro para CADA trampa
    ultimos_registros = df_plagas.loc[df_plagas.groupby('Codigo_Trampa')['Fecha'].idxmax()]
    
    # Filtramos las trampas que superan el umbral
    trampas_en_alerta = ultimos_registros[ultimos_registros['Total_Capturas'] >= umbral_alerta_plagas]
    
    if not trampas_en_alerta.empty:
        st.warning(f"¡Atención! Se han detectado {len(trampas_en_alerta)} trampas que superan el umbral de {umbral_alerta_plagas} capturas.")
        
        # Mostramos las alertas en columnas para que se vea más ordenado
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


# --- Módulo de Gráficos (El código anterior, sin cambios mayores) ---

# Análisis de Monitoreo de Plagas
st.subheader("🪰 Evolución de Capturas de Mosca de la Fruta")
if df_plagas is not None and not df_plagas[df_plagas['Sector'] == sector_seleccionado].empty:
    df_plagas_sector = df_plagas[df_plagas['Sector'] == sector_seleccionado]
    df_plagas_sector['Fecha'] = pd.to_datetime(df_plagas_sector['Fecha'])
    capturas_por_dia = df_plagas_sector.groupby('Fecha')['Total_Capturas'].sum().reset_index()
    fig_plagas = px.line(capturas_por_dia, x='Fecha', y='Total_Capturas', title=f'Total de Capturas Diarias en el Sector {sector_seleccionado}', markers=True)
    st.plotly_chart(fig_plagas, use_container_width=True)
else:
    st.info(f"No hay registros de monitoreo de plagas para el sector '{sector_seleccionado}'.")

st.divider()

# Análisis de Fenología
st.subheader("🌱 Distribución Fenológica Reciente")
if df_fenologia is not None and not df_fenologia[df_fenologia['Sector'] == sector_seleccionado].empty:
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
