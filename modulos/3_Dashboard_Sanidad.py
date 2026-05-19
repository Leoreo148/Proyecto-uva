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
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    try:
        # 1. Monitoreo de Mosca
        res_mosca = supabase.table('Monitoreo_Mosca').select("*").execute()
        df_mosca = pd.DataFrame(res_mosca.data)
        if not df_mosca.empty:
            df_mosca['Fecha'] = pd.to_datetime(df_mosca['Fecha']).dt.date
            
        # 2. Evaluaciones Sanitarias (JSONB)
        res_san = supabase.table('Evaluaciones_Sanitarias').select("*").execute()
        df_san_raw = pd.DataFrame(res_san.data)
        
        plagas_records = []
        enfermedades_records = []
        
        if not df_san_raw.empty:
            for _, row in df_san_raw.iterrows():
                fecha = pd.to_datetime(row['Fecha']).date()
                sector = row['Sector']
                evaluador = row.get('Evaluador', 'N/A')
                
                # Desempaquetar Plagas
                datos_p = row.get('Datos_Plagas', [])
                if isinstance(datos_p, list):
                    for planta in datos_p:
                        plagas_records.append({
                            'Fecha': fecha, 'Sector': sector, 'Evaluador': evaluador,
                            'TRIPS': float(planta.get('TRIPS', 0)),
                            'M_BLANCA': float(planta.get('M.BLANCA', 0)),
                            'A_ROJA': float(planta.get('A.ROJA', 0)),
                            'COCHINILLA': float(planta.get('COCHINILLA', 0))
                        })
                
                # Desempaquetar Enfermedades
                datos_e = row.get('Datos_Enfermedades', [])
                if isinstance(datos_e, list):
                    for planta in datos_e:
                        enfermedades_records.append({
                            'Fecha': fecha, 'Sector': sector, 'Evaluador': evaluador,
                            'OIDIO': float(planta.get('OIDIO %', 0)),
                            'MILDIU': float(planta.get('MILDIU %', 0)),
                            'BOTRYTIS': float(planta.get('BOTRYTIS', 0))
                        })
        
        return df_mosca, pd.DataFrame(plagas_records), pd.DataFrame(enfermedades_records)

    except Exception as e:
        st.error(f"Error cargando datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_mosca, df_plagas, df_enfermedades = cargar_datos_sanidad()

# --- 4. FILTROS LATERALES ---
st.sidebar.header("Filtros de Sanidad")
hoy = date.today()
f_inicio = st.sidebar.date_input("Fecha Inicio", hoy - timedelta(days=30))
f_fin = st.sidebar.date_input("Fecha Fin", hoy)

sectores_disp = ['Todos'] + sorted(list(set(
    (df_mosca['Sector'].tolist() if not df_mosca.empty else []) + 
    (df_plagas['Sector'].tolist() if not df_plagas.empty else [])
)))
f_sector = st.sidebar.selectbox("Sector", sectores_disp)

# Aplicar filtros temporales y de sector
if not df_mosca.empty and 'Fecha' in df_mosca.columns:
    mask_m = (df_mosca['Fecha'] >= f_inicio) & (df_mosca['Fecha'] <= f_fin)
    df_mosca_f = df_mosca[mask_m]
    if f_sector != 'Todos': df_mosca_f = df_mosca_f[df_mosca_f['Sector'] == f_sector]
else:
    df_mosca_f = pd.DataFrame()

if not df_plagas.empty and 'Fecha' in df_plagas.columns:
    mask_p = (df_plagas['Fecha'] >= f_inicio) & (df_plagas['Fecha'] <= f_fin)
    df_plagas_f = df_plagas[mask_p]
    if f_sector != 'Todos': df_plagas_f = df_plagas_f[df_plagas_f['Sector'] == f_sector]
else:
    df_plagas_f = pd.DataFrame()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("📊 Dashboard de Presión Sanitaria")
st.write("Monitoreo focalizado y umbrales críticos para la toma de decisiones.")

tab_mosca, tab_plagas, tab_enfermedades = st.tabs(["🪰 PANEL MOSCAS", "🐛 PANEL PLAGAS", "🍄 PANEL ENFERMEDADES"])

# ==========================================
# PANEL 1: MOSCAS DE LA FRUTA
# ==========================================
with tab_mosca:
    st.header("Análisis de Mosca de la Fruta")
    if not df_mosca_f.empty:
        tipo_mosca = st.selectbox("Seleccione la especie de Mosca:", ['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta'])
        
        # Cálculo del Lote Crítico
        ranking_mosca = df_mosca_f.groupby('Sector')[tipo_mosca].sum().reset_index()
        if not ranking_mosca.empty and ranking_mosca[tipo_mosca].sum() > 0:
            lote_critico = ranking_mosca.sort_values(by=tipo_mosca, ascending=False).iloc[0]
            st.error(f"🚨 **LOTE CRÍTICO PARA {tipo_mosca.upper()}:** Sector **{lote_critico['Sector']}** con **{int(lote_critico[tipo_mosca])}** capturas acumuladas.")
        else:
            st.success(f"✅ No se registran capturas de {tipo_mosca} en el periodo seleccionado.")
            
        # Gráfico descriptivo
        df_m_trend = df_mosca_f.groupby('Fecha')[tipo_mosca].sum().reset_index()
        fig_mosca = px.line(df_m_trend, x='Fecha', y=tipo_mosca, markers=True, title=f"Evolución Temporal de {tipo_mosca}")
        fig_mosca.add_hline(y=5, line_dash="dot", line_color="red", annotation_text="Umbral de Alerta")
        st.plotly_chart(fig_mosca, use_container_width=True)
    else:
        st.info("No hay datos de trampas de mosca en este rango de fechas.")

# ==========================================
# PANEL 2: PLAGAS
# ==========================================
with tab_plagas:
    st.header("Control de Focos de Plagas")
    if not df_plagas_f.empty:
        tipo_plaga = st.selectbox("Seleccione la Plaga a evaluar:", ['TRIPS', 'A_ROJA', 'M_BLANCA', 'COCHINILLA'])
        
        # Cálculo del Lote Crítico
        ranking_plaga = df_plagas_f.groupby('Sector')[tipo_plaga].mean().reset_index()
        if not ranking_plaga.empty and ranking_plaga[tipo_plaga].sum() > 0:
            lote_critico_p = ranking_plaga.sort_values(by=tipo_plaga, ascending=False).iloc[0]
            st.error(f"🚨 **LOTE CRÍTICO PARA {tipo_plaga}:** Sector **{lote_critico_p['Sector']}** con un promedio de **{lote_critico_p[tipo_plaga]:.2f}** individuos/planta.")
        else:
            st.success(f"✅ Todo limpio. No hay presión biológica de {tipo_plaga}.")
            
        # Gráfico
        fig_plagas = px.bar(ranking_plaga, x='Sector', y=tipo_plaga, title=f"Nivel de Infestación Promedio: {tipo_plaga}", color=tipo_plaga, color_continuous_scale="Reds")
        st.plotly_chart(fig_plagas, use_container_width=True)
    else:
        st.info("No hay evaluaciones sanitarias de plagas en estas fechas.")

# ==========================================
# PANEL 3: ENFERMEDADES
# ==========================================
with tab_enfermedades:
    st.header("Monitoreo Fitopatológico (Enfermedades)")
    if not df_enfermedades.empty:
        df_enf_f = df_enfermedades[(df_enfermedades['Fecha'] >= f_inicio) & (df_enfermedades['Fecha'] <= f_fin)]
        if f_sector != 'Todos': df_enf_f = df_enf_f[df_enf_f['Sector'] == f_sector]
        
        if not df_enf_f.empty:
            tipo_enf = st.selectbox("Seleccione la Enfermedad:", ['OIDIO', 'MILDIU', 'BOTRYTIS'])
            
            # Cálculo del Lote Crítico
            ranking_enf = df_enf_f.groupby('Sector')[tipo_enf].mean().reset_index()
            if not ranking_enf.empty and ranking_enf[tipo_enf].sum() > 0:
                lote_critico_e = ranking_enf.sort_values(by=tipo_enf, ascending=False).iloc[0]
                unidad = "% de severidad" if tipo_enf in ['OIDIO', 'MILDIU'] else " grado de avance"
                st.error(f"🍄 **LOTE CRÍTICO PARA {tipo_enf}:** Sector **{lote_critico_e['Sector']}** con **{lote_critico_e[tipo_enf]:.2f}{unidad}** promedio.")
            else:
                st.success(f"☀️ Condiciones óptimas. No se detectan síntomas de {tipo_enf}.")
                
            # Gráfico
            fig_enf = px.bar(ranking_enf, x='Sector', y=tipo_enf, title=f"Presión Promedio de {tipo_enf}", color=tipo_enf, color_continuous_scale="Purples")
            st.plotly_chart(fig_enf, use_container_width=True)
        else:
            st.info("No hay evaluaciones fitopatológicas en el rango seleccionado.")
    else:
        st.info("Base de datos de enfermedades vacía.")