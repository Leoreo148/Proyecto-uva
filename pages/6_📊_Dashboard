import streamlit as st
import pandas as pd
import os
import plotly.express as px

# --- Configuración de la Página ---
st.set_page_config(page_title="Dashboard de Análisis", page_icon="📊", layout="wide")
st.title("📊 Dashboard de Análisis del Fundo")
st.write("Visualice las tendencias y el estado actual de su cultivo.")

# --- Función para Cargar Datos de Forma Segura ---
def cargar_datos(nombre_archivo):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    return None

# --- Filtros Principales ---
st.sidebar.header("Filtros del Dashboard")
df_plagas = cargar_datos('Monitoreo_Plagas_Detallado.xlsx')
df_fenologia = cargar_datos('Evaluacion_Fenologica_Detallada.xlsx')

# Creamos una lista de sectores disponibles a partir de los datos existentes
if df_plagas is not None:
    sectores_disponibles = df_plagas['Sector'].unique().tolist()
else:
    sectores_disponibles = ['General'] # Valor por defecto si no hay datos

sector_seleccionado = st.sidebar.selectbox(
    "Seleccione un Sector para Analizar:",
    options=sectores_disponibles
)

st.header(f"Análisis para el Sector: {sector_seleccionado}")
st.divider()

# --- Módulo 1: Análisis de Monitoreo de Plagas ---
st.subheader("🪰 Evolución de Capturas de Mosca de la Fruta")

if df_plagas is not None:
    # Filtramos los datos por el sector seleccionado
    df_plagas_sector = df_plagas[df_plagas['Sector'] == sector_seleccionado]
    
    if not df_plagas_sector.empty:
        # Convertimos la fecha a formato datetime para poder graficarla correctamente
        df_plagas_sector['Fecha'] = pd.to_datetime(df_plagas_sector['Fecha'])
        
        # Agrupamos por fecha y sumamos el total de capturas para tener un valor diario
        capturas_por_dia = df_plagas_sector.groupby('Fecha')['Total_Capturas'].sum().reset_index()
        
        # Creamos el gráfico de líneas
        fig_plagas = px.line(
            capturas_por_dia,
            x='Fecha',
            y='Total_Capturas',
            title=f'Total de Capturas Diarias en el Sector {sector_seleccionado}',
            markers=True,
            labels={'Fecha': 'Fecha de Conteo', 'Total_Capturas': 'Número Total de Capturas'}
        )
        st.plotly_chart(fig_plagas, use_container_width=True)
    else:
        st.info(f"No hay registros de monitoreo de plagas para el sector '{sector_seleccionado}'.")
else:
    st.info("Aún no se ha creado el archivo 'Monitoreo_Plagas_Detallado.xlsx'.")

st.divider()

# --- Módulo 2: Análisis de Fenología ---
st.subheader("🌱 Distribución Fenológica Reciente")

if df_fenologia is not None:
    # Filtramos los datos por el sector seleccionado
    df_fenologia_sector = df_fenologia[df_fenologia['Sector'] == sector_seleccionado]
    
    if not df_fenologia_sector.empty:
        # Encontramos la fecha de la última evaluación para ese sector
        ultima_fecha = df_fenologia_sector['Fecha'].max()
        st.write(f"Mostrando la última evaluación realizada el: **{pd.to_datetime(ultima_fecha).strftime('%d/%m/%Y')}**")
        
        # Filtramos los datos para quedarnos solo con la última evaluación
        df_ultima_evaluacion = df_fenologia_sector[df_fenologia_sector['Fecha'] == ultima_fecha]
        
        # Sumamos los conteos de cada estado fenológico
        columnas_estados = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
        resumen_fenologia = df_ultima_evaluacion[columnas_estados].sum()
        
        # Creamos el gráfico de torta (pie chart)
        fig_fenologia = px.pie(
            values=resumen_fenologia.values,
            names=resumen_fenologia.index,
            title=f'Distribución de Estados Fenológicos en el Sector {sector_seleccionado}'
        )
        st.plotly_chart(fig_fenologia, use_container_width=True)
    else:
        st.info(f"No hay registros de evaluación fenológica para el sector '{sector_seleccionado}'.")
else:
    st.info("Aún no se ha creado el archivo 'Evaluacion_Fenologica_Detallada.xlsx'.")
