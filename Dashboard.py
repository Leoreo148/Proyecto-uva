import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from supabase import create_client

# --- LIBRERÍAS PRO ---
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Dashboard Maestro", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS CENTRALIZADA ---
@st.cache_data(ttl=300)
def cargar_todo():
    if not supabase: return {}
    
    tablas = ["Productos", "Ingresos", "Salidas", "Registro_Horas_Tractor", "Maquinaria", "Personal", "Ordenes_de_Trabajo"]
    dfs = {}
    for t in tablas:
        try:
            res = supabase.table(t).select("*").execute()
            dfs[t] = pd.DataFrame(res.data)
        except:
            dfs[t] = pd.DataFrame()
    return dfs

data = cargar_todo()

# --- 4. CEREBRO MATEMÁTICO (STOCK Y COSTOS) ---
def procesar_kardex_dashboard(dfs):
    df_p = dfs.get("Productos", pd.DataFrame())
    df_i = dfs.get("Ingresos", pd.DataFrame())
    df_s = dfs.get("Salidas", pd.DataFrame())
    
    if df_i.empty: return pd.DataFrame()

    # Calcular salidas por Ingreso_ID
    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_balance = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada'] - df_balance['Cantidad_Usada']
    else:
        df_balance = df_i.copy()
        df_balance['Stock_Lote'] = df_balance['Cantidad_Ingresada']

    # Merge con Productos para traer Categoría (Tipo_Accion)
    df_final = pd.merge(df_balance, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    df_final['Valorizado_PEN'] = df_final['Stock_Lote'] * df_final['Precio_Unitario_PEN'].fillna(0)
    
    # Anti-Bug de Fechas
    hoy = pd.Timestamp(date.today())
    df_final['Venc_Date'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
    df_final['Dias_para_Vencer'] = (df_final['Venc_Date'] - hoy).dt.days
    df_final.loc[df_final['Venc_Date'].isnull() | (df_final['Venc_Date'].dt.year < 2000), 'Dias_para_Vencer'] = 999
    
    return df_final

df_kardex = procesar_kardex_dashboard(data)

# --- 5. CABECERA ---
with stylable_container(key="title_panel", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("📊 Dashboard General del Fundo")
    st.write(f"Estado de operaciones al {datetime.now().strftime('%d/%m/%Y %H:%M')}")

# --- 6. KPIs PRINCIPALES ---
st.write("")
m1, m2, m3, m4 = st.columns(4)
style_metric_cards(border_left_color="#1e3d33")

if not df_kardex.empty:
    m1.metric("💰 Valor Almacén", f"S/ {df_kardex['Valorizado_PEN'].sum():,.2f}")
    m2.metric("⚠️ Lotes por Vencer (<30d)", len(df_kardex[(df_kardex['Dias_para_Vencer'] < 30) & (df_kardex['Stock_Lote'] > 0)]))

df_h = data.get("Registro_Horas_Tractor", pd.DataFrame())
if not df_h.empty:
    # Horas de los últimos 7 días
    h7 = pd.to_datetime(df_h['Fecha']) >= (datetime.now() - timedelta(days=7))
    m3.metric("🚜 Horas Tractor (7d)", f"{df_h[h7]['Total_Horas'].sum():,.1f} h")

df_ot = data.get("Ordenes_de_Trabajo", pd.DataFrame())
if not df_ot.empty:
    pendientes = len(df_ot[df_ot['Status'] != 'Aplicada en Campo'])
    m4.metric("📝 Órdenes en Curso", pendientes)

# --- 7. ANÁLISIS GRÁFICO ---
st.divider()
c_graf1, c_graf2 = st.columns(2)

with c_graf1:
    with st.container(border=True):
        st.subheader("📦 Distribución del Almacén")
        if not df_kardex.empty:
            df_pie = df_kardex.groupby('Tipo_Accion')['Valorizado_PEN'].sum().reset_index()
            fig_pie = px.pie(df_pie, values='Valorizado_PEN', names='Tipo_Accion', 
                             color_discrete_sequence=px.colors.qualitative.Prism,
                             hole=0.4, title="Valorización por Categoría")
            st.plotly_chart(fig_pie, use_container_width=True)

with c_graf2:
    with st.container(border=True):
        st.subheader("📉 Productos más consumidos (30d)")
        df_salidas = data.get("Salidas", pd.DataFrame())
        df_prod = data.get("Productos", pd.DataFrame())
        if not df_salidas.empty and not df_prod.empty:
            # Unir salidas con ingresos para saber qué producto es
            df_i = data.get("Ingresos", pd.DataFrame())
            df_s_join = pd.merge(df_salidas, df_i[['id', 'Codigo_Producto']], left_on='Ingreso_ID', right_on='id')
            df_s_join = pd.merge(df_s_join, df_prod[['Codigo', 'Producto']], left_on='Codigo_Producto', right_on='Codigo')
            
            top_cons = df_s_join.groupby('Producto')['Cantidad_Usada'].sum().sort_values(ascending=False).head(10).reset_index()
            fig_bar = px.bar(top_cons, x='Cantidad_Usada', y='Producto', orientation='h',
                             title="Top 10 Insumos Aplicados", color_discrete_sequence=['#2ecc71'])
            st.plotly_chart(fig_bar, use_container_width=True)

# --- 8. ESTADO DE MAQUINARIA ---
st.divider()
st.subheader("🚜 Rendimiento de Maquinaria")
df_maq = data.get("Maquinaria", pd.DataFrame())

if not df_h.empty and not df_maq.empty:
    df_h_maq = pd.merge(df_h, df_maq, left_on='maquinaria_id', right_on='id', how='left')
    res_maq = df_h_maq.groupby('nombre')['Total_Horas'].sum().reset_index()
    
    cols = st.columns(len(res_maq) if len(res_maq) > 0 else 1)
    for i, row in res_maq.iterrows():
        with cols[i % len(cols)]:
            st.write(f"**{row['nombre']}**")
            st.caption(f"Total: {row['Total_Horas']:.1f} horas acumuladas")
            # Simulación de barra de mantenimiento (cada 250h)
            progreso = (row['Total_Horas'] % 250) / 250
            st.progress(min(progreso, 1.0))
            if progreso > 0.9:
                st.warning("⚠️ Requiere Mantenimiento")