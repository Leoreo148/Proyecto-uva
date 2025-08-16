import streamlit as st
import pandas as pd
import os
import plotly.express as px
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard General", page_icon="📊", layout="wide")
st.title("📊 Dashboard General del Fundo")
st.write("Métricas clave de inventario, operaciones y estado del cultivo para una visión completa.")

# --- FUNCIONES DE CARGA Y CÁLCULO ---
@st.cache_data
def cargar_datos(nombre_archivo, columnas_fecha=None):
    if not os.path.exists(nombre_archivo): return None
    try:
        df = pd.read_excel(nombre_archivo)
        if columnas_fecha:
            for col in columnas_fecha:
                if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except Exception as e:
        st.error(f"Error al leer el archivo {nombre_archivo}: {e}")
        return None

@st.cache_data
def cargar_hoja_especifica(nombre_archivo, nombre_hoja, columnas_fecha=None):
    if not os.path.exists(nombre_archivo): return None
    try:
        df = pd.read_excel(nombre_archivo, sheet_name=nombre_hoja)
        if columnas_fecha:
            for col in columnas_fecha:
                if col in df.columns: df[col] = pd.to_datetime(df[col], errors='coerce')
        return df
    except ValueError: return None
    except Exception as e:
        st.error(f"Error al leer la hoja '{nombre_hoja}' de {nombre_archivo}: {e}")
        return None

def calcular_stock(df_ingresos, df_salidas):
    if df_ingresos is None or df_ingresos.empty:
        return pd.DataFrame(columns=['Codigo_Lote', 'Stock_Restante', 'Valor_Lote', 'Fecha_Vencimiento', 'Codigo_Producto'])
    
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
    
    if 'Precio_Unitario' not in stock_lotes_detallado.columns: stock_lotes_detallado['Precio_Unitario'] = 0
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    return stock_lotes_detallado

# --- CARGA DE TODOS LOS DATOS ---
df_kardex_productos = cargar_hoja_especifica('kardex_fundo.xlsx', 'Productos')
df_kardex_ingresos = cargar_hoja_especifica('kardex_fundo.xlsx', 'Ingresos', columnas_fecha=['Fecha', 'Fecha_Vencimiento'])
df_kardex_salidas = cargar_hoja_especifica('kardex_fundo.xlsx', 'Salidas', columnas_fecha=['Fecha'])
df_raleo = cargar_datos('Registro_Raleo.xlsx', columnas_fecha=['Fecha'])
df_horas_tractor = cargar_datos('Registro_Horas_Tractor.xlsx', columnas_fecha=['Fecha'])
df_ordenes = cargar_datos('Ordenes_de_Trabajo.xlsx', columnas_fecha=['Fecha_Programada', 'Aplicacion_Completada_Fecha'])
df_baya = cargar_datos('Registro_Diametro_Baya_Detallado.xlsx', columnas_fecha=['Fecha'])
df_mosca = cargar_datos('Monitoreo_Mosca_Fruta.xlsx', columnas_fecha=['Fecha'])

df_stock_lotes = calcular_stock(df_kardex_ingresos, df_kardex_salidas)

# --- BARRA LATERAL ---
st.sidebar.header("Filtros del Dashboard")
today = datetime.now().date()
fecha_inicio = st.sidebar.date_input("Fecha de Inicio", today - timedelta(days=30))
fecha_fin = st.sidebar.date_input("Fecha de Fin", today)

# --- FILTRADO DE DATOS ---
df_raleo_filtrado = df_raleo[(df_raleo['Fecha'].dt.date >= fecha_inicio) & (df_raleo['Fecha'].dt.date <= fecha_fin)] if df_raleo is not None else pd.DataFrame()
df_horas_filtrado = df_horas_tractor[(df_horas_tractor['Fecha'].dt.date >= fecha_inicio) & (df_horas_tractor['Fecha'].dt.date <= fecha_fin)] if df_horas_tractor is not None else pd.DataFrame()
df_ordenes_filtrado = df_ordenes[(df_ordenes['Fecha_Programada'].dt.date >= fecha_inicio) & (df_ordenes['Fecha_Programada'].dt.date <= fecha_fin)] if df_ordenes is not None else pd.DataFrame()

# --- VISTA PRINCIPAL ---
st.header("Resumen General")

# --- KPIs ---
kpi_cols = st.columns(6)

with kpi_cols[0]:
    valor_total_inventario = df_stock_lotes['Valor_Lote'].sum() if not df_stock_lotes.empty else 0
    st.metric("💰 Valor Inventario", f"S/ {valor_total_inventario:,.2f}")

with kpi_cols[1]:
    ordenes_activas = len(df_ordenes[df_ordenes['Status'] != 'Completada']) if df_ordenes is not None else 0
    st.metric("🛠️ Órdenes Activas", f"{ordenes_activas}")

with kpi_cols[2]:
    horas_totales = df_horas_filtrado['Total_Horas'].sum() if not df_horas_filtrado.empty else 0
    st.metric(f"🚜 Horas Tractor (Período)", f"{horas_totales:,.1f} h")

with kpi_cols[3]:
    diametro_promedio = 0
    if df_baya is not None and not df_baya.empty and 'Fecha' in df_baya.columns:
        ultima_fecha_baya = df_baya['Fecha'].max()
        df_ultima_medicion = df_baya[df_baya['Fecha'] == ultima_fecha_baya]
        columnas_medicion = [col for col in df_ultima_medicion.columns if 'Racimo' in col]
        if columnas_medicion:
            valores = df_ultima_medicion[columnas_medicion].to_numpy().flatten()
            diametro_promedio = valores[valores > 0].mean() if len(valores[valores > 0]) > 0 else 0
    st.metric("🍇 Diámetro Baya (mm)", f"{diametro_promedio:.2f}")

with kpi_cols[4]:
    umbral_mosca = st.number_input("Umbral Capturas:", min_value=1, value=7, step=1, key="umbral_kpi")
    sectores_en_alerta = 0
    if df_mosca is not None and not df_mosca.empty and 'Fecha' in df_mosca.columns:
        df_mosca['Total_Capturas'] = df_mosca[['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']].sum(axis=1)
        df_ultimas_moscas = df_mosca.loc[df_mosca.groupby('Numero_Trampa')['Fecha'].idxmax()]
        trampas_en_alerta = df_ultimas_moscas[df_ultimas_moscas['Total_Capturas'] >= umbral_mosca]
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

# --- GRÁFICOS ---
st.header("Análisis Visual")
gcol1, gcol2 = st.columns(2)

with gcol1:
    st.subheader("Valor de Inventario por Tipo")
    if df_kardex_productos is not None and not df_stock_lotes.empty:
        df_valor_tipo = pd.merge(df_stock_lotes, df_kardex_productos, left_on='Codigo_Producto', right_on='Codigo', how='left')
        df_valor_tipo = df_valor_tipo.groupby('Tipo_Accion')['Valor_Lote'].sum().reset_index()
        fig_pie = px.pie(df_valor_tipo, values='Valor_Lote', names='Tipo_Accion', title="Distribución del Valor en Almacén", hole=.3)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No hay datos de inventario para mostrar.")

with gcol2:
    st.subheader("Evolución del Diámetro de Baya")
    if df_baya is not None and not df_baya.empty and 'Fecha' in df_baya.columns:
        df_baya_filtrado = df_baya[(df_baya['Fecha'].dt.date >= fecha_inicio) & (df_baya['Fecha'].dt.date <= fecha_fin)]
        if not df_baya_filtrado.empty:
            columnas_medicion = [col for col in df_baya_filtrado.columns if 'Racimo' in col]
            if columnas_medicion:
                df_baya_filtrado['Diametro_Prom_Planta'] = df_baya_filtrado[columnas_medicion].mean(axis=1)
                df_tendencia_baya = df_baya_filtrado.groupby(['Fecha', 'Sector'])['Diametro_Prom_Planta'].mean().reset_index()
                fig_baya = px.line(df_tendencia_baya, x='Fecha', y='Diametro_Prom_Planta', color='Sector', title='Crecimiento Promedio de Baya por Sector', markers=True, labels={'Diametro_Prom_Planta': 'Diámetro (mm)'})
                st.plotly_chart(fig_baya, use_container_width=True)
        else:
            st.info("No hay datos de diámetro de baya para el rango de fechas seleccionado.")
    else:
        st.info("Aún no se han registrado mediciones de diámetro de baya.")
