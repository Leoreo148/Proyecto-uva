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

if st.session_state.get("rol") not in ["Admin", "Sanidad", "Programador", "prom"]:
    st.error("🚫 Acceso denegado. Módulo exclusivo para el área de Sanidad.")
    st.stop()

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Dashboard Sanidad", page_icon="📊", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; }
    .alerta-box-roja { background-color: #ffebee; border-left: 5px solid #f44336; padding: 12px 15px; border-radius: 5px; margin-bottom:10px; }
    .alerta-box-verde { background-color: #e8f5e9; border-left: 5px solid #4caf50; padding: 12px 15px; border-radius: 5px; margin-bottom:10px; }
    .alerta-box-amarilla { background-color: #fff8e1; border-left: 5px solid #ffc107; padding: 12px 15px; border-radius: 5px; margin-bottom:10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. UMBRALES DE ACCIÓN (líneas rojas agronómicas) ---
UMBRALES = {
    'TRIPS':      3.0,   # individuos/hoja promedio
    'A_ROJA':     5.0,   # individuos/hoja promedio
    'M_BLANCA':   4.0,   # individuos/hoja promedio
    'COCHINILLA': 2.0,   # individuos/planta promedio
    'OIDIO':     10.0,   # % de severidad promedio
    'MILDIU':     5.0,   # % de severidad promedio
    'BOTRYTIS':   3.0,   # grado de avance promedio
}

# --- 4. EXTRACCIÓN Y PROCESAMIENTO DE DATOS ---
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

# --- 5. FILTROS LATERALES ---
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
def filtrar_df(df, f_ini, f_fin, sector):
    if df.empty or 'Fecha' not in df.columns:
        return pd.DataFrame()
    mask = (df['Fecha'] >= f_ini) & (df['Fecha'] <= f_fin)
    df_f = df[mask]
    if sector != 'Todos':
        df_f = df_f[df_f['Sector'] == sector]
    return df_f

df_mosca_f = filtrar_df(df_mosca, f_inicio, f_fin, f_sector)
df_plagas_f = filtrar_df(df_plagas, f_inicio, f_fin, f_sector)
df_enf_f = filtrar_df(df_enfermedades, f_inicio, f_fin, f_sector)

# --- 6. INTERFAZ PRINCIPAL ---
st.title("📊 Dashboard de Presión Sanitaria")
st.write("Monitoreo focalizado, umbrales de acción y tendencias históricas para la toma de decisiones.")

tab_mosca, tab_plagas, tab_enfermedades = st.tabs(["🪰 PANEL MOSCAS", "🐛 PANEL PLAGAS", "🍄 PANEL ENFERMEDADES"])

# ==========================================
# PANEL 1: MOSCAS DE LA FRUTA
# ==========================================
with tab_mosca:
    st.header("Análisis de Mosca de la Fruta")
    
    if not df_mosca.empty:
        # Selector de Modo de Análisis
        modo_analisis = st.radio("🔍 Modo de Visualización:", 
                                 ["📊 Tendencia General (Usa el filtro lateral)", "🎯 Análisis de Trampas (Foco de Infección)"], 
                                 horizontal=True)
        
        tipo_mosca = st.selectbox("Seleccione la especie de Mosca:", ['Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta'])
        
        if modo_analisis == "📊 Tendencia General (Usa el filtro lateral)":
            st.info(f"💡 **Modo Tendencia:** Mostrando evolución de **{f_sector}**. Cambia el sector en el menú de la izquierda.")
            
            # Usamos el dataframe filtrado globalmente (df_mosca_f) que ya obedece al sidebar
            if not df_mosca_f.empty:
                # Ranking general (si estamos viendo "Todos", mostramos cuál es el peor sector)
                if f_sector == 'Todos':
                    ranking_mosca = df_mosca_f.groupby('Sector')[tipo_mosca].sum().reset_index()
                    if not ranking_mosca.empty and ranking_mosca[tipo_mosca].sum() > 0:
                        lote_critico = ranking_mosca.sort_values(by=tipo_mosca, ascending=False).iloc[0]
                        st.markdown(f"""<div class="alerta-box-roja">
                            🚨 <strong>LOTE CRÍTICO PARA {tipo_mosca.upper()}:</strong> Sector <strong>{lote_critico['Sector']}</strong> con <strong>{int(lote_critico[tipo_mosca])}</strong> capturas acumuladas.
                        </div>""", unsafe_allow_html=True)
                
                # Tendencia (Una sola línea sumada)
                df_m_trend = df_mosca_f.groupby('Fecha')[tipo_mosca].sum().reset_index()
                fig_mosca = px.line(df_m_trend, x='Fecha', y=tipo_mosca, markers=True, 
                                    title=f"Evolución Temporal de {tipo_mosca} en {f_sector}")
                fig_mosca.add_hline(y=5, line_dash="dot", line_color="red", annotation_text="Umbral de Alerta")
                fig_mosca.update_layout(height=350)
                st.plotly_chart(fig_mosca, use_container_width=True)
            else:
                st.warning(f"No hay datos de moscas para {f_sector} en estas fechas.")
                
        else:
            st.info("💡 **Análisis de Trampas:** Identifica rápidamente qué trampas exactas están atrayendo a la plaga en un sector específico.")
            
            # Selector de sector específico (ignora 'Todos' porque analizar trampas de todo el fundo es un caos)
            sectores_reales = [s for s in sectores_disp if s != 'Todos']
            sector_trampas = st.selectbox("Seleccione el Sector a analizar:", sectores_reales)
            
            df_mosca_sector = df_mosca[(df_mosca['Fecha'] >= f_inicio) & (df_mosca['Fecha'] <= f_fin) & (df_mosca['Sector'] == sector_trampas)]
            
            if not df_mosca_sector.empty and 'Numero_Trampa' in df_mosca_sector.columns:
                
                # Agrupamos el total de capturas por trampa en ese periodo
                df_rank_t = df_mosca_sector.groupby('Numero_Trampa')[tipo_mosca].sum().reset_index().sort_values(by=tipo_mosca, ascending=False)
                df_rank_t = df_rank_t[df_rank_t[tipo_mosca] > 0] # Solo mostrar trampas con capturas
                
                if not df_rank_t.empty:
                    st.write(f"### 🏆 Top Trampas Críticas en {sector_trampas}")
                    # Tarjetas de resumen en lugar de gráfico de líneas caótico
                    cols = st.columns(min(3, len(df_rank_t)))
                    for i, (idx, row) in enumerate(df_rank_t.head(3).iterrows()):
                        with cols[i]:
                            st.metric(label=f"🚨 Trampa {row['Numero_Trampa']}", value=f"{int(row[tipo_mosca])} moscas")
                    
                    st.divider()
                    st.write(f"**Distribución Horizontal de Capturas (Todas las trampas de {sector_trampas}):**")
                    
                    # Gráfico de barras horizontal para fácil lectura
                    fig_rank_horiz = px.bar(df_rank_t.sort_values(by=tipo_mosca, ascending=True), 
                                            x=tipo_mosca, y='Numero_Trampa', orientation='h',
                                            text=tipo_mosca, color=tipo_mosca, color_continuous_scale="Reds")
                    fig_rank_horiz.update_layout(height=100 + (len(df_rank_t) * 30), showlegend=False, 
                                                 yaxis_type='category', yaxis_title="N° de Trampa", xaxis_title="Total Capturas")
                    st.plotly_chart(fig_rank_horiz, use_container_width=True)
                else:
                    st.success(f"✅ ¡Excelente! Ninguna trampa en el sector {sector_trampas} tiene capturas de {tipo_mosca} en este periodo.")
            else:
                st.warning(f"No hay registros de trampas para el sector {sector_trampas} en este rango de fechas.")
    else:
        st.info("La base de datos de moscas está vacía.")

# ==========================================
# PANEL 2: PLAGAS
# ==========================================
with tab_plagas:
    st.header("Control de Focos de Plagas")
    if not df_plagas_f.empty:
        tipo_plaga = st.selectbox("Seleccione la Plaga a evaluar:", ['TRIPS', 'A_ROJA', 'M_BLANCA', 'COCHINILLA'])
        umbral_plaga = UMBRALES.get(tipo_plaga, 5.0)
        
        # Cálculo del Lote Crítico
        ranking_plaga = df_plagas_f.groupby('Sector')[tipo_plaga].mean().reset_index()
        if not ranking_plaga.empty and ranking_plaga[tipo_plaga].sum() > 0:
            lote_critico_p = ranking_plaga.sort_values(by=tipo_plaga, ascending=False).iloc[0]
            valor_critico = lote_critico_p[tipo_plaga]
            if valor_critico >= umbral_plaga:
                st.markdown(f"""<div class="alerta-box-roja">
                    🚨 <strong>ALERTA: {tipo_plaga}</strong> en Sector <strong>{lote_critico_p['Sector']}</strong> con <strong>{valor_critico:.2f}</strong> individuos/planta (Umbral: {umbral_plaga}).
                    <br>👉 <em>Acción recomendada: Programar aplicación de control inmediata.</em>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="alerta-box-amarilla">
                    🟡 <strong>{tipo_plaga}</strong>: Sector <strong>{lote_critico_p['Sector']}</strong> con <strong>{valor_critico:.2f}</strong> individuos/planta. Por debajo del umbral ({umbral_plaga}).
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="alerta-box-verde">
                ✅ Todo limpio. No hay presión biológica de {tipo_plaga}.
            </div>""", unsafe_allow_html=True)
            
        # ✅ NUEVO: Gráfico temporal de tendencia (reemplaza el bar chart estático)
        cpl1, cpl2 = st.columns(2)
        
        with cpl1:
            st.subheader("📈 Tendencia en el Tiempo")
            df_plaga_trend = df_plagas_f.groupby('Fecha')[tipo_plaga].mean().reset_index()
            fig_plaga_line = px.line(
                df_plaga_trend, x='Fecha', y=tipo_plaga, markers=True,
                title=f"Evolución Promedio de {tipo_plaga}",
                color_discrete_sequence=['#e74c3c']
            )
            fig_plaga_line.add_hline(
                y=umbral_plaga, line_dash="dot", line_color="red",
                annotation_text=f"Umbral de Acción ({umbral_plaga})"
            )
            fig_plaga_line.update_layout(height=360)
            st.plotly_chart(fig_plaga_line, use_container_width=True)
        
        with cpl2:
            st.subheader("📊 Presión por Sector")
            fig_plagas_bar = px.bar(
                ranking_plaga.sort_values(tipo_plaga, ascending=True),
                x=tipo_plaga, y='Sector', orientation='h',
                title=f"Nivel Promedio por Sector: {tipo_plaga}",
                color=tipo_plaga, color_continuous_scale="YlOrRd",
                text=ranking_plaga.sort_values(tipo_plaga, ascending=True)[tipo_plaga].apply(lambda x: f"{x:.2f}")
            )
            fig_plagas_bar.add_vline(
                x=umbral_plaga, line_dash="dash", line_color="red",
                annotation_text="Umbral"
            )
            fig_plagas_bar.update_layout(height=360, showlegend=False)
            st.plotly_chart(fig_plagas_bar, use_container_width=True)
        
        # ✅ NUEVO: Heatmap Sector × Fecha
        with st.expander("🗺️ Mapa de Calor: Presión por Sector y Fecha"):
            df_heat_p = df_plagas_f.groupby(['Fecha', 'Sector'])[tipo_plaga].mean().reset_index()
            if not df_heat_p.empty:
                df_pivot_p = df_heat_p.pivot_table(index='Sector', columns='Fecha', values=tipo_plaga, fill_value=0)
                fig_hm_p = px.imshow(
                    df_pivot_p, aspect='auto', color_continuous_scale='YlOrRd',
                    labels=dict(x='Fecha', y='Sector', color='Promedio'),
                    title=f"Mapa de Intensidad: {tipo_plaga}"
                )
                fig_hm_p.update_layout(height=300)
                st.plotly_chart(fig_hm_p, use_container_width=True)
    else:
        st.info("No hay evaluaciones sanitarias de plagas en estas fechas.")

# ==========================================
# PANEL 3: ENFERMEDADES
# ==========================================
with tab_enfermedades:
    st.header("Monitoreo Fitopatológico (Enfermedades)")
    if not df_enf_f.empty:
        tipo_enf = st.selectbox("Seleccione la Enfermedad:", ['OIDIO', 'MILDIU', 'BOTRYTIS'])
        umbral_enf = UMBRALES.get(tipo_enf, 5.0)
        unidad = "% de severidad" if tipo_enf in ['OIDIO', 'MILDIU'] else "grado de avance"
        
        # Cálculo del Lote Crítico
        ranking_enf = df_enf_f.groupby('Sector')[tipo_enf].mean().reset_index()
        if not ranking_enf.empty and ranking_enf[tipo_enf].sum() > 0:
            lote_critico_e = ranking_enf.sort_values(by=tipo_enf, ascending=False).iloc[0]
            valor_critico_e = lote_critico_e[tipo_enf]
            if valor_critico_e >= umbral_enf:
                st.markdown(f"""<div class="alerta-box-roja">
                    🍄 <strong>ALERTA: {tipo_enf}</strong> en Sector <strong>{lote_critico_e['Sector']}</strong> con <strong>{valor_critico_e:.2f} {unidad}</strong> (Umbral: {umbral_enf}).
                    <br>👉 <em>Acción recomendada: Aplicación curativa/protectante urgente.</em>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""<div class="alerta-box-amarilla">
                    🟡 <strong>{tipo_enf}</strong>: Sector <strong>{lote_critico_e['Sector']}</strong> con <strong>{valor_critico_e:.2f} {unidad}</strong>. Por debajo del umbral ({umbral_enf}).
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="alerta-box-verde">
                ☀️ Condiciones óptimas. No se detectan síntomas de {tipo_enf}.
            </div>""", unsafe_allow_html=True)
                
        # ✅ NUEVO: Gráfico temporal + barras lado a lado
        ce1, ce2 = st.columns(2)
        
        with ce1:
            st.subheader("📈 Tendencia en el Tiempo")
            df_enf_trend = df_enf_f.groupby('Fecha')[tipo_enf].mean().reset_index()
            fig_enf_line = px.line(
                df_enf_trend, x='Fecha', y=tipo_enf, markers=True,
                title=f"Evolución de {tipo_enf} ({unidad})",
                color_discrete_sequence=['#8e44ad']
            )
            fig_enf_line.add_hline(
                y=umbral_enf, line_dash="dot", line_color="red",
                annotation_text=f"Umbral de Acción ({umbral_enf})"
            )
            fig_enf_line.update_layout(height=360)
            st.plotly_chart(fig_enf_line, use_container_width=True)
        
        with ce2:
            st.subheader("📊 Presión por Sector")
            fig_enf_bar = px.bar(
                ranking_enf.sort_values(tipo_enf, ascending=True),
                x=tipo_enf, y='Sector', orientation='h',
                title=f"Nivel Promedio por Sector: {tipo_enf}",
                color=tipo_enf, color_continuous_scale="Purples",
                text=ranking_enf.sort_values(tipo_enf, ascending=True)[tipo_enf].apply(lambda x: f"{x:.2f}")
            )
            fig_enf_bar.add_vline(
                x=umbral_enf, line_dash="dash", line_color="red",
                annotation_text="Umbral"
            )
            fig_enf_bar.update_layout(height=360, showlegend=False)
            st.plotly_chart(fig_enf_bar, use_container_width=True)
        
        # ✅ NUEVO: Heatmap Sector × Fecha
        with st.expander("🗺️ Mapa de Calor: Presión por Sector y Fecha"):
            df_heat_e = df_enf_f.groupby(['Fecha', 'Sector'])[tipo_enf].mean().reset_index()
            if not df_heat_e.empty:
                df_pivot_e = df_heat_e.pivot_table(index='Sector', columns='Fecha', values=tipo_enf, fill_value=0)
                fig_hm_e = px.imshow(
                    df_pivot_e, aspect='auto', color_continuous_scale='BuPu',
                    labels=dict(x='Fecha', y='Sector', color=unidad),
                    title=f"Mapa de Intensidad: {tipo_enf}"
                )
                fig_hm_e.update_layout(height=300)
                st.plotly_chart(fig_hm_e, use_container_width=True)
    else:
        st.info("Base de datos de enfermedades vacía o sin datos en el rango seleccionado.")