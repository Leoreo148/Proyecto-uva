import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Fundo")
st.write("Métricas clave de inventario, operaciones y estado del cultivo para una visión completa.")

# --- FUNCIONES DE CARGA DE DATOS ---
@st.cache_data
def cargar_datos(nombre_archivo, columnas_fecha=None):
    if not os.path.exists(nombre_archivo):
        return None
    try:
        df = pd.read_excel(nombre_archivo)
        if columnas_fecha:
            for col in columnas_fecha:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo {nombre_archivo}: {e}")
        return None

# --- CARGA DE TODOS LOS DATOS RELEVANTES ---
df_baya = cargar_datos('Registro_Diametro_Baya_Detallado.xlsx', columnas_fecha=['Fecha'])
df_mosca = cargar_datos('Monitoreo_Mosca_Fruta.xlsx', columnas_fecha=['Fecha'])
# (Aquí se cargarían los otros dataframes si se necesitaran)

# --- BARRA LATERAL CON FILTROS ---
st.sidebar.header("Filtros del Dashboard")
today = datetime.now().date()
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=60))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# --- VISTA PRINCIPAL DEL DASHBOARD ---
st.header("Resumen del Cultivo")
col1, col2, col3 = st.columns(3)

# KPI 1: Diámetro Promedio de Baya
with col1:
    diametro_promedio = 0
    # --- !! AJUSTE CLAVE: Verificamos que la columna 'Fecha' exista !! ---
    if df_baya is not None and not df_baya.empty and 'Fecha' in df_baya.columns:
        ultima_fecha = df_baya['Fecha'].max()
        df_ultima_medicion = df_baya[df_baya['Fecha'] == ultima_fecha]
        columnas_medicion = [col for col in df_ultima_medicion.columns if 'Racimo' in col]
        if columnas_medicion: # Asegurarse de que existan columnas de medición
            valores = df_ultima_medicion[columnas_medicion].to_numpy().flatten()
            valores_no_cero = valores[valores > 0]
            if len(valores_no_cero) > 0:
                diametro_promedio = valores_no_cero.mean()
    st.metric("🍇 Diámetro Promedio (mm)", f"{diametro_promedio:.2f}")

# KPI 2: Sectores en Alerta por Mosca de la Fruta
with col2:
    sectores_en_alerta = 0
    umbral_mosca = st.number_input("Umbral de Alerta de Capturas:", min_value=1, value=7, step=1)
    if df_mosca is not None and not df_mosca.empty and 'Fecha' in df_mosca.columns:
        df_mosca['Total_Capturas'] = df_mosca[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum(axis=1)
        df_ultimas_moscas = df_mosca.loc[df_mosca.groupby('Numero_Trampa')['Fecha'].idxmax()]
        trampas_en_alerta = df_ultimas_moscas[df_ultimas_moscas['Total_Capturas'] >= umbral_mosca]
        sectores_en_alerta = trampas_en_alerta['Sector'].nunique()
    st.metric("🪰 Sectores en Alerta (Mosca)", f"{sectores_en_alerta} Sectores")

st.divider()

# --- GRÁFICOS DE ANÁLISIS ---
st.header("Análisis Visual del Cultivo")
gcol1, gcol2 = st.columns(2)

with gcol1:
    st.subheader("🌱 Evolución del Diámetro de Baya")
    # --- !! AJUSTE CLAVE: Verificamos que la columna 'Fecha' exista !! ---
    if df_baya is not None and not df_baya.empty and 'Fecha' in df_baya.columns:
        df_baya_filtrado = df_baya[(df_baya['Fecha'].dt.date >= fecha_inicio) & (df_baya['Fecha'].dt.date <= fecha_fin)]
        if not df_baya_filtrado.empty:
            columnas_medicion = [col for col in df_baya_filtrado.columns if 'Racimo' in col]
            if columnas_medicion:
                df_baya_filtrado['Diametro_Prom_Planta'] = df_baya_filtrado[columnas_medicion].mean(axis=1)
                df_tendencia_baya = df_baya_filtrado.groupby(['Fecha', 'Sector'])['Diametro_Prom_Planta'].mean().reset_index()
                
                fig_baya = px.line(
                    df_tendencia_baya, x='Fecha', y='Diametro_Prom_Planta', color='Sector',
                    title='Crecimiento Promedio de Baya por Sector', markers=True,
                    labels={'Fecha': 'Fecha', 'Diametro_Prom_Planta': 'Diámetro Promedio (mm)', 'Sector': 'Sector'}
                )
                st.plotly_chart(fig_baya, use_container_width=True)
            else:
                st.info("No se encontraron columnas de medición en los datos.")
        else:
            st.info("No hay datos de diámetro de baya en el rango de fechas seleccionado.")
    else:
        st.info("Aún no se han registrado mediciones de diámetro de baya o el archivo tiene un formato antiguo.")

with gcol2:
    st.subheader("🪰 Capturas de Mosca por Sector (Últimos 7 días)")
    if df_mosca is not None and not df_mosca.empty and 'Fecha' in df_mosca.columns:
        df_mosca_reciente = df_mosca[df_mosca['Fecha'].dt.date >= (today - timedelta(days=7))]
        if not df_mosca_reciente.empty:
            df_mosca_reciente['Total_Capturas'] = df_mosca_reciente[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum(axis=1)
            capturas_sector = df_mosca_reciente.groupby('Sector')['Total_Capturas'].sum().reset_index().sort_values(by='Total_Capturas', ascending=False)
            
            fig_mosca = px.bar(
                capturas_sector, x='Sector', y='Total_Capturas',
                title='Total de Capturas en la Última Semana', text='Total_Capturas',
                labels={'Sector': 'Sector', 'Total_Capturas': 'Nº de Capturas'}
            )
            st.plotly_chart(fig_mosca, use_container_width=True)
        else:
            st.info("No se han registrado capturas de mosca en los últimos 7 días.")
    else:
        st.info("Aún no se han registrado monitoreos de mosca de la fruta o el archivo tiene un formato antiguo.")
