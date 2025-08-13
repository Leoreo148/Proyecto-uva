import streamlit as st
import pandas as pd
import os
import plotly.express as px

# --- Configuración de la Página ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Fundo")
st.write("Métricas clave, tendencias y alertas críticas para una visión completa.")

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
df_inventario = cargar_datos('Inventario_Productos.xlsx')

# --- Barra Lateral con Filtros ---
st.sidebar.header("Filtros y Umbrales")
umbral_alerta_plagas = st.sidebar.number_input("Umbral de Alerta de Capturas:", min_value=1, value=7, step=1)
umbral_alerta_oidio = st.sidebar.slider("Umbral de Alerta de Oídio:", min_value=1, max_value=4, value=3)

# --- Lógica para obtener TODOS los sectores ---
sectores_plagas = df_plagas['Sector'].unique().tolist() if df_plagas is not None else []
sectores_fenologia = df_fenologia['Sector'].unique().tolist() if df_fenologia is not None and 'Sector' in df_fenologia.columns else []
sectores_observaciones = df_observaciones['Sector'].unique().tolist() if df_observaciones is not None else []
todos_los_sectores = sorted(list(set(sectores_plagas + sectores_fenologia + sectores_observaciones)))
if not todos_los_sectores:
    todos_los_sectores = ['General']
sector_seleccionado = st.sidebar.selectbox("Seleccione un Sector para Analizar:", options=todos_los_sectores)

st.header(f"Análisis para el Sector: {sector_seleccionado}")
st.divider()

# --- MÉTRICAS CLAVE (KPIs) - OPTIMIZADO PARA MÓVIL ---
st.subheader("📈 Resumen de Métricas Clave")

# Para una mejor visualización en teléfonos, mostramos las métricas verticalmente.
col1, col2, col3 = st.columns(3)

# KPI 1: Trampas de Plagas en Alerta
with col1:
    if df_plagas is not None:
        df_plagas['Fecha'] = pd.to_datetime(df_plagas['Fecha'])
        ultimos_registros_plagas = df_plagas.loc[df_plagas.groupby('Codigo_Trampa')['Fecha'].idxmax()]
        trampas_en_alerta_total = ultimos_registros_plagas[ultimos_registros_plagas['Total_Capturas'] >= umbral_alerta_plagas]
        st.metric(label="Trampas de Plagas en Alerta", value=len(trampas_en_alerta_total))
    else:
        st.metric(label="Trampas de Plagas en Alerta", value="N/A")

# KPI 2: Sectores con Oídio Activo
with col2:
    if df_observaciones is not None:
        df_observaciones['Fecha'] = pd.to_datetime(df_observaciones['Fecha'])
        ultimas_obs_oidio = df_observaciones.loc[df_observaciones.groupby('Sector')['Fecha'].idxmax()]
        sectores_con_oidio = ultimas_obs_oidio[ultimas_obs_oidio['Severidad_Oidio'] > 0]
        st.metric(label="Sectores con Oídio Detectado", value=len(sectores_con_oidio))
    else:
        st.metric(label="Sectores con Oídio Detectado", value="N/A")

# KPI 3: Producto con Menor Stock
with col3:
    if df_inventario is not None and not df_inventario.empty:
        producto_menor_stock = df_inventario.loc[df_inventario['Cantidad_Stock'].idxmin()]
        nombre_prod = producto_menor_stock['Producto']
        stock_prod = producto_menor_stock['Cantidad_Stock']
        unidad_prod = producto_menor_stock['Unidad']
        st.metric(label=f"Producto con Menor Stock", value=f"{stock_prod} {unidad_prod}", help=f"Producto: {nombre_prod}")
    else:
        st.metric(label="Producto con Menor Stock", value="N/A")

st.divider()

# --- CONCLUSIONES AGRONÓMICAS ---
st.subheader("💡 Conclusiones Agronómicas")
col_conc_1, col_conc_2 = st.columns(2)

# Conclusión para Oídio
with col_conc_1:
    with st.container(border=True):
        st.markdown("##### Diagnóstico de Oídio")
        if df_observaciones is not None and sector_seleccionado in df_observaciones['Sector'].unique():
            ultima_obs_oidio = df_observaciones[df_observaciones['Sector'] == sector_seleccionado].sort_values(by='Fecha', ascending=False).iloc[0]
            severidad_actual = ultima_obs_oidio['Severidad_Oidio']
            fecha_obs_oidio = pd.to_datetime(ultima_obs_oidio['Fecha']).strftime('%d/%m/%Y')
            
            if df_fenologia is not None and sector_seleccionado in df_fenologia['Sector'].unique():
                df_fenologia_sector = df_fenologia[df_fenologia['Sector'] == sector_seleccionado]
                ultima_fecha_feno = df_fenologia_sector['Fecha'].max()
                df_ultima_evaluacion = df_fenologia_sector[df_fenologia_sector['Fecha'] == ultima_fecha_feno]
                columnas_estados = ['Punta algodón', 'Punta verde', 'Salida de hojas', 'Hojas extendidas', 'Racimos visibles']
                resumen_fenologia = df_ultima_evaluacion[columnas_estados].sum()
                estado_dominante = resumen_fenologia.idxmax()
                
                mensaje = f"**Severidad actual:** {severidad_actual} (del {fecha_obs_oidio}).\n\n**Estado dominante:** '{estado_dominante}'."
                st.info(mensaje)
            else:
                st.warning("Faltan datos de fenología para un diagnóstico completo.")
        else:
            st.info("Sin datos de oídio para este sector.")

# Conclusión para Plagas
with col_conc_2:
    with st.container(border=True):
        st.markdown("##### Diagnóstico de Mosca de la Fruta")
        if df_plagas is not None and sector_seleccionado in df_plagas['Sector'].unique():
            df_plagas_sector = df_plagas[df_plagas['Sector'] == sector_seleccionado]
            df_plagas_sector['Fecha'] = pd.to_datetime(df_plagas_sector['Fecha'])
            ultimos_registros = df_plagas_sector.loc[df_plagas_sector.groupby('Codigo_Trampa')['Fecha'].idxmax()]
            
            if not ultimos_registros.empty:
                trampa_max_capturas = ultimos_registros.loc[ultimos_registros['Total_Capturas'].idxmax()]
                max_capturas = trampa_max_capturas['Total_Capturas']
                codigo_trampa_max = trampa_max_capturas['Codigo_Trampa']
                
                mensaje = f"La **trampa con mayor actividad** es la **'{codigo_trampa_max}'** con **{max_capturas} capturas**."
                st.info(mensaje)

                if max_capturas >= umbral_alerta_plagas:
                    st.warning(f"Este valor supera el umbral de alerta ({umbral_alerta_plagas}).")
                else:
                    st.success("La presión de la plaga está por debajo del umbral.")
            else:
                st.info("Sin datos de plagas para este sector.")
        else:
            st.info("Sin datos de plagas para este sector.")

st.divider()

# --- ALERTAS CRÍTICAS ---
st.subheader("🚨 Alertas Críticas")
col_oidio, col_plagas = st.columns(2)
with col_oidio:
    st.markdown("##### Alertas de Oídio")
    if df_observaciones is not None and 'Severidad_Oidio' in df_observaciones.columns:
        df_observaciones['Fecha'] = pd.to_datetime(df_observaciones['Fecha'])
        ultimas_obs = df_observaciones.loc[df_observaciones.groupby('Sector')['Fecha'].idxmax()]
        sectores_en_alerta = ultimas_obs[ultimas_obs['Severidad_Oidio'] >= umbral_alerta_oidio]
        if not sectores_en_alerta.empty:
            for index, row in sectores_en_alerta.iterrows():
                st.error(f"**Sector:** {row['Sector']} | **Severidad:** {row['Severidad_Oidio']}")
        else:
            st.success("✅ Sin alertas de oídio.")
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
                st.warning(f"**Trampa:** {row['Codigo_Trampa']} | **Capturas:** {row['Total_Capturas']}")
        else:
            st.success("✅ Sin alertas de plagas.")
    else:
        st.info("No hay datos de plagas.")
st.divider()

# --- GRÁFICOS ---
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
