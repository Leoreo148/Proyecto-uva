import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, date
from supabase import create_client
from streamlit_extras.metric_cards import style_metric_cards

# 🚨 CANDADO VIP: SANIDAD Y JEFATURA
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

# Bloqueo: Solo Sanidad (José), Admin (Segundo) y Programador
if st.session_state.get("rol") not in ["Admin", "Sanidad", "Programador", "prom"]:
    st.error("🚫 Acceso denegado. Módulo exclusivo para el área de Sanidad.")
    st.stop()

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard Sanidad", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; }
    .alerta-box { background-color: #ffebee; border-left: 5px solid #f44336; padding: 10px; border-radius: 5px; margin-bottom:10px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. EXTRACCIÓN Y PROCESAMIENTO DE DATOS ---
@st.cache_data(ttl=60)
def cargar_datos_sanidad():
    if not supabase: return pd.DataFrame(), pd.DataFrame()
    
    try:
        # 1. Monitoreo de Mosca
        res_mosca = supabase.table('Monitoreo_Mosca').select("*").execute()
        df_mosca = pd.DataFrame(res_mosca.data)
        if not df_mosca.empty:
            df_mosca['Fecha'] = pd.to_datetime(df_mosca['Fecha']).dt.date
            
        # 2. Evaluaciones Sanitarias (JSONB)
        res_san = supabase.table('Evaluaciones_Sanitarias').select("*").execute()
        df_san_raw = pd.DataFrame(res_san.data)
        
        # PROCESAMIENTO MÁGICO: Desempaquetar el JSON de plagas
        plagas_records = []
        if not df_san_raw.empty:
            for _, row in df_san_raw.iterrows():
                fecha = pd.to_datetime(row['Fecha']).date()
                sector = row['Sector']
                evaluador = row.get('Evaluador', 'N/A')
                datos_p = row.get('Datos_Plagas', [])
                
                if isinstance(datos_p, list):
                    for planta in datos_p:
                        plagas_records.append({
                            'Fecha': fecha,
                            'Sector': sector,
                            'Evaluador': evaluador,
                            'TRIPS': float(planta.get('TRIPS', 0)),
                            'M_BLANCA': float(planta.get('M.BLANCA', 0)),
                            'A_ROJA': float(planta.get('A.ROJA', 0)),
                            'COCHINILLA': float(planta.get('COCHINILLA', 0))
                        })
        
        df_plagas = pd.DataFrame(plagas_records)
        return df_mosca, df_plagas

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_mosca, df_plagas = cargar_datos_sanidad()

# --- 4. FILTROS LATERALES ---
st.sidebar.header("Filtros de Sanidad")
hoy = date.today()
f_inicio = st.sidebar.date_input("Fecha Inicio", hoy - timedelta(days=30))
f_fin = st.sidebar.date_input("Fecha Fin", hoy)

sectores_disp = ['Todos'] + sorted(list(set(df_mosca['Sector'].tolist() + (df_plagas['Sector'].tolist() if not df_plagas.empty else []))))
f_sector = st.sidebar.selectbox("Sector", sectores_disp)

# Aplicar filtros
if not df_mosca.empty:
    mask_m = (df_mosca['Fecha'] >= f_inicio) & (df_mosca['Fecha'] <= f_fin)
    df_mosca_f = df_mosca[mask_m]
    if f_sector != 'Todos': df_mosca_f = df_mosca_f[df_mosca_f['Sector'] == f_sector]
else:
    df_mosca_f = pd.DataFrame()

if not df_plagas.empty:
    mask_p = (df_plagas['Fecha'] >= f_inicio) & (df_plagas['Fecha'] <= f_fin)
    df_plagas_f = df_plagas[mask_p]
    if f_sector != 'Todos': df_plagas_f = df_plagas_f[df_plagas_f['Sector'] == f_sector]
else:
    df_plagas_f = pd.DataFrame()

# --- 5. CABECERA Y KPIs ---
st.title("📊 Dashboard de Presión Sanitaria")
st.write("Monitoreo de umbrales para la toma de decisiones en aplicaciones fitosanitarias.")

m1, m2, m3, m4 = st.columns(4)
style_metric_cards(background_color="#ffffff", border_left_color="#e74c3c")

# KPI 1: Mosca
tot_mosca = df_mosca_f['Ceratitis_capitata'].sum() if not df_mosca_f.empty else 0
m1.metric("🪰 Capturas Ceratitis", f"{tot_mosca}")

# KPI 2: Sector más afectado mosca
peor_sector_mosca = df_mosca_f.groupby('Sector')['Ceratitis_capitata'].sum().idxmax() if tot_mosca > 0 else "Ninguno"
m2.metric("📍 Lote Crítico Mosca", peor_sector_mosca)

# KPI 3 y 4: Plagas Vid
if not df_plagas_f.empty:
    prom_trips = df_plagas_f['TRIPS'].mean()
    prom_aroja = df_plagas_f['A_ROJA'].mean()
else:
    prom_trips, prom_aroja = 0, 0

m3.metric("🐛 Promedio Trips/Planta", f"{prom_trips:.1f}")
m4.metric("🕷️ Promedio Arañita/Planta", f"{prom_aroja:.1f}")

st.divider()

# --- 6. ANÁLISIS DE MOSCA DE LA FRUTA (SENASA) ---
st.subheader("🪰 Monitoreo de Mosca de la Fruta")

c_mosca1, c_mosca2 = st.columns([2, 1])

with c_mosca1:
    if not df_mosca_f.empty:
        # Agrupamos por fecha
        df_m_trend = df_mosca_f.groupby('Fecha')[['Ceratitis_capitata', 'Anastrepha_fraterculus']].sum().reset_index()
        
        fig_mosca = go.Figure()
        fig_mosca.add_trace(go.Scatter(x=df_m_trend['Fecha'], y=df_m_trend['Ceratitis_capitata'], mode='lines+markers', name='C. Capitata', line=dict(color='#e74c3c', width=3)))
        fig_mosca.add_trace(go.Scatter(x=df_m_trend['Fecha'], y=df_m_trend['Anastrepha_fraterculus'], mode='lines+markers', name='A. Fraterculus', line=dict(color='#f39c12', width=2)))
        
        # UMBRAL DE ACCIÓN (Línea roja) - Modificable para tesis
        UMBRAL_MTD = 5 # Ejemplo: 5 capturas
        fig_mosca.add_hline(y=UMBRAL_MTD, line_dash="dot", line_color="red", annotation_text="Umbral de Alerta", annotation_position="top left")
        
        fig_mosca.update_layout(title="Dinámica Poblacional de Mosca", xaxis_title="Fecha", yaxis_title="Individuos Capturados", hovermode="x unified")
        st.plotly_chart(fig_mosca, use_container_width=True)
    else:
        st.info("No hay datos de mosca de la fruta en este rango.")

with c_mosca2:
    st.write("**Alertas de Sectores (Capturas Totales)**")
    if not df_mosca_f.empty:
        df_m_sect = df_mosca_f.groupby('Sector')[['Ceratitis_capitata', 'Anastrepha_fraterculus']].sum().reset_index()
        df_m_sect['Total'] = df_m_sect['Ceratitis_capitata'] + df_m_sect['Anastrepha_fraterculus']
        df_m_sect = df_m_sect[df_m_sect['Total'] > 0].sort_values(by='Total', ascending=False)
        
        for _, row in df_m_sect.iterrows():
            if row['Total'] > UMBRAL_MTD:
                st.markdown(f"<div class='alerta-box'><b>🚨 Sector {row['Sector']}</b>: {row['Total']} capturas (Supera Umbral)</div>", unsafe_allow_html=True)
            else:
                st.markdown(f"✅ **Sector {row['Sector']}**: {row['Total']} capturas")
    else:
        st.write("Sin alertas.")

st.divider()

# --- 7. ANÁLISIS DE PLAGAS EN HOJAS/RACIMOS ---
st.subheader("🍇 Incidencia Promedio de Plagas por Planta")

if not df_plagas_f.empty:
    c_p1, c_p2 = st.columns([1, 2])
    
    # Agrupar datos por sector para mostrar promedios
    df_p_sect = df_plagas_f.groupby('Sector')[['TRIPS', 'M_BLANCA', 'A_ROJA', 'COCHINILLA']].mean().reset_index()
    
    with c_p1:
        st.write("**Selecciona la plaga a evaluar:**")
        plaga_sel = st.radio("Plaga:", ['TRIPS', 'A_ROJA', 'M_BLANCA', 'COCHINILLA'], horizontal=True)
        
        st.write("Resumen Promedio General:")
        st.dataframe(df_p_sect[['Sector', plaga_sel]].sort_values(by=plaga_sel, ascending=False).style.format({plaga_sel: "{:.2f}"}), use_container_width=True, hide_index=True)

    with c_p2:
        # Gráfico de barras por sector
        fig_plagas = px.bar(
            df_p_sect, x='Sector', y=plaga_sel, 
            title=f"Nivel de Infestación Promedio: {plaga_sel}",
            text_auto='.2f', color=plaga_sel, color_continuous_scale="Reds"
        )
        
        # Umbral sugerido
        umbrales_sugeridos = {'TRIPS': 2.0, 'A_ROJA': 1.5, 'M_BLANCA': 1.0, 'COCHINILLA': 0.5}
        umbral_actual = umbrales_sugeridos.get(plaga_sel, 1.0)
        
        fig_plagas.add_hline(y=umbral_actual, line_dash="dash", line_color="black", annotation_text=f"Umbral de Aplicación ({umbral_actual})")
        
        st.plotly_chart(fig_plagas, use_container_width=True)

    # Tendencia temporal
    st.write(f"**Evolución temporal de {plaga_sel}**")
    df_p_trend = df_plagas_f.groupby(['Fecha', 'Sector'])[plaga_sel].mean().reset_index()
    fig_p_trend = px.line(df_p_trend, x='Fecha', y=plaga_sel, color='Sector', markers=True)
    fig_p_trend.add_hline(y=umbral_actual, line_dash="dash", line_color="black")
    st.plotly_chart(fig_p_trend, use_container_width=True)

else:
    st.info("No hay evaluaciones de plagas registradas en este periodo de tiempo.")