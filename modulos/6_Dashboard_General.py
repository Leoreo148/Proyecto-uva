import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import plotly.express as px
from supabase import create_client

# 🚨 CANDADO VIP: EXCLUSIVO PARA JEFATURA
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

# Bloqueo estricto: Solo el Ing. Segundo (Admin) y tú (Programador/'prom')
if st.session_state.get("rol") not in ["Admin", "Programador", "prom"]:
    st.error("🚫 Acceso denegado. Este panel táctico es exclusivo para la Jefatura del Fundo.")
    st.stop()

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Dashboard Maestro - Project Uva", page_icon="🏢", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f0f4f8; }
    .kpi-card {
        background-color: #ffffff;
        padding: 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        border-left: 5px solid #2ecc71;
        margin-bottom: 20px;
    }
    .kpi-rojo { border-left-color: #e74c3c; }
    .kpi-azul { border-left-color: #3498db; }
    .kpi-amarillo { border-left-color: #f1c40f; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. EXTRACCIÓN DE DATOS GLOBALES (Caché de 5 mins para rendimiento) ---
@st.cache_data(ttl=300)
def cargar_datos_maestros_v2():
    hoy = date.today()
    hace_30_dias = hoy - timedelta(days=30)
    
    # Manejo de errores individual por tabla para evitar que el dashboard caiga completo
    def fetch_table(table_name):
        try:
            return pd.DataFrame(supabase.table(table_name).select("*").execute().data)
        except:
            return pd.DataFrame()

    df_mosca = fetch_table('Monitoreo_Mosca')
    df_raleo = fetch_table('Control_Raleo')
    df_ots = fetch_table('Ordenes_de_Trabajo')
    df_diam = fetch_table('Diametro_Baya')
    df_feno = fetch_table('Evaluaciones_Fenologicas')
    df_clima = fetch_table('Clima')
    
    # Procesamiento básico si hay datos
    if not df_mosca.empty: df_mosca['Fecha'] = pd.to_datetime(df_mosca['Fecha'])
    if not df_raleo.empty: df_raleo['Fecha'] = pd.to_datetime(df_raleo['Fecha'])
    if not df_ots.empty: df_ots['Fecha_Programada'] = pd.to_datetime(df_ots['Fecha_Programada'])
    if not df_diam.empty: df_diam['Fecha'] = pd.to_datetime(df_diam['Fecha'])
    if not df_feno.empty: df_feno['Fecha'] = pd.to_datetime(df_feno['Fecha'])
    
    return df_mosca, df_raleo, df_ots, df_diam, df_feno, df_clima

df_mosca, df_raleo, df_ots, df_diam, df_feno, df_clima = cargar_datos_maestros_v2()

# --- 4. CÁLCULO DE KPIs ---
TARIFA_POR_RACIMO = 0.07

# KPI Mosca (Últimos 7 días)
alertas_mosca = 0
if not df_mosca.empty:
    recientes_mosca = df_mosca[df_mosca['Fecha'] >= pd.Timestamp(date.today() - timedelta(days=7))]
    alertas_mosca = recientes_mosca['Ceratitis_capitata'].sum()

# KPI Raleo y Costos
costo_total_raleo = 0
if not df_raleo.empty:
    costo_total_raleo = (df_raleo['Racimos_Reales'].sum() * TARIFA_POR_RACIMO)

# KPI Sanidad/Mezclas (Costos)
inversion_sanidad = 0
ots_pendientes = 0
if not df_ots.empty:
    ots_pendientes = len(df_ots[df_ots['Status'] == 'En Preparación'])
    finalizadas = df_ots[df_ots['Status'] == 'Finalizada']
    for _, ot in finalizadas.iterrows():
        dt = ot.get('Datos_Tecnicos', {})
        if isinstance(dt, dict):
            inversion_sanidad += dt.get('Costo_Estimado_Total', 0)

# KPI Diámetro Baya
promedio_baya_global = 0
if not df_diam.empty:
    # Obtener el promedio de la última fecha registrada
    ultima_fecha = df_diam['Fecha'].max()
    df_ultimo_diam = df_diam[df_diam['Fecha'] == ultima_fecha]
    # Calculamos el promedio de todas las columnas que no sean texto
    cols_numericas = df_ultimo_diam.select_dtypes(include='number').columns
    if not cols_numericas.empty:
        promedio_baya_global = df_ultimo_diam[cols_numericas].mean().mean()

# KPI Clima
temp_actual = "N/A"
if not df_clima.empty:
    df_clima['fecha_hora'] = pd.to_datetime(df_clima['fecha_hora'])
    ultimo_clima = df_clima.sort_values(by='fecha_hora', ascending=False).iloc[0]
    temp_actual = f"{ultimo_clima['temp_out']} °C"

# --- 5. INTERFAZ TÁCTICA ---
st.title("🏢 Panel de Control Estratégico")
st.write(f"Resumen operativo y financiero actualizado al **{datetime.now().strftime('%d/%m/%Y %H:%M')}**")

# FILA 1: TARJETAS DE MÉTRICAS (KPIs)
col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
        <div class="kpi-card kpi-rojo">
            <h4 style="margin:0; color:#7f8c8d; font-size:14px;">🪰 Alertas Mosca (7D)</h4>
            <h2 style="margin:0; color:#2c3e50;">{alertas_mosca} <span style="font-size:14px;">capturas</span></h2>
        </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
        <div class="kpi-card kpi-azul">
            <h4 style="margin:0; color:#7f8c8d; font-size:14px;">💰 Inversión Sanidad</h4>
            <h2 style="margin:0; color:#2c3e50;">S/ {inversion_sanidad:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
        <div class="kpi-card">
            <h4 style="margin:0; color:#7f8c8d; font-size:14px;">✂️ Inversión Mano Obra (Raleo)</h4>
            <h2 style="margin:0; color:#2c3e50;">S/ {costo_total_raleo:,.2f}</h2>
        </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
        <div class="kpi-card kpi-amarillo">
            <h4 style="margin:0; color:#7f8c8d; font-size:14px;">📏 Calibre Promedio Actual</h4>
            <h2 style="margin:0; color:#2c3e50;">{promedio_baya_global:.2f} <span style="font-size:14px;">mm</span></h2>
        </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
        <div class="kpi-card" style="border-left-color: #9b59b6;">
            <h4 style="margin:0; color:#7f8c8d; font-size:14px;">🌤️ Temp. Fundo</h4>
            <h2 style="margin:0; color:#2c3e50;">{temp_actual}</h2>
        </div>
    """, unsafe_allow_html=True)

st.divider()

# FILA 2: GRÁFICOS Y ANÁLISIS CRUZADO
c_chart1, c_chart2 = st.columns([2, 1])

with c_chart1:
    st.subheader("📈 Avance de Raleo vs Costo Diario")
    if not df_raleo.empty:
        df_raleo_diario = df_raleo.groupby('Fecha').agg(
            Racimos=('Racimos_Reales', 'sum')
        ).reset_index()
        df_raleo_diario['Inversión (S/)'] = df_raleo_diario['Racimos'] * TARIFA_POR_RACIMO
        
        fig_raleo = px.bar(
            df_raleo_diario, x='Fecha', y='Inversión (S/)', 
            text_auto='.2s', title='Inversión Diaria en Raleo',
            color_discrete_sequence=['#2ecc71']
        )
        st.plotly_chart(fig_raleo, use_container_width=True)
    else:
        st.info("Aún no hay datos suficientes de raleo para graficar.")

with c_chart2:
    st.subheader("🚜 Cuello de Botella Logístico")
    if not df_ots.empty:
        df_status = df_ots['Status'].value_counts().reset_index()
        df_status.columns = ['Estado', 'Cantidad']
        fig_ots = px.pie(
            df_status, values='Cantidad', names='Estado',
            hole=0.5, title='Estado de Órdenes de Trabajo',
            color='Estado',
            color_discrete_map={'En Preparación':'#f39c12', 'Finalizada':'#27ae60', 'Anulada':'#e74c3c'}
        )
        st.plotly_chart(fig_ots, use_container_width=True)
        if ots_pendientes > 0:
            st.warning(f"⚠️ Almacén tiene {ots_pendientes} órdenes pendientes de despachar.")
    else:
        st.info("No hay órdenes de trabajo programadas.")

# FILA 3: ALERTAS TEMPRANAS
st.subheader("🚨 Alertas Críticas de Campo")
col_alert1, col_alert2 = st.columns(2)

with col_alert1:
    st.markdown("**🪰 Sectores con Mayor Presencia de Ceratitis (Histórico)**")
    if not df_mosca.empty:
        df_mosca_alert = df_mosca.groupby('Sector')['Ceratitis_capitata'].sum().reset_index().sort_values(by='Ceratitis_capitata', ascending=False)
        df_mosca_alert = df_mosca_alert[df_mosca_alert['Ceratitis_capitata'] > 0].head(5)
        if not df_mosca_alert.empty:
            st.dataframe(df_mosca_alert, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No se han reportado capturas de mosca.")
    else:
        st.write("Sin datos de monitoreo.")

with col_alert2:
    st.markdown("**📋 Últimas Aplicaciones de Sanidad Finalizadas**")
    if not df_ots.empty:
        df_ots_fin = df_ots[df_ots['Status'] == 'Finalizada'].sort_values(by='Fecha_Programada', ascending=False).head(5)
        if not df_ots_fin.empty:
            df_mostrar = df_ots_fin[['Fecha_Programada', 'Sector_Aplicacion', 'Objetivo']]
            df_mostrar.columns = ['Fecha', 'Sector', 'Objetivo']
            st.dataframe(df_mostrar, use_container_width=True, hide_index=True)
        else:
            st.info("No hay aplicaciones finalizadas recientes.")
    else:
        st.write("Sin datos de órdenes de trabajo.")

st.divider()

# FILA 4: CRECIMIENTO Y DESARROLLO (NUEVO)
st.subheader("🌱 Crecimiento y Desarrollo")
col_crec1, col_crec2 = st.columns(2)

with col_crec1:
    st.markdown("**📏 Evolución del Diámetro de Baya (mm)**")
    if not df_diam.empty:
        # Extraemos las columnas numéricas de medición
        cols_medicion = [c for c in df_diam.columns if c.startswith('Racimo_')]
        if cols_medicion:
            # Calculamos el promedio de la planta en esa fila
            df_diam['Promedio_Planta'] = df_diam[cols_medicion].mean(axis=1)
            # Agrupamos por Fecha y Sector
            df_diam_hist = df_diam.groupby(['Fecha', 'Sector'])['Promedio_Planta'].mean().reset_index()
            
            fig_diam = px.line(
                df_diam_hist, x='Fecha', y='Promedio_Planta', color='Sector',
                markers=True, title="Crecimiento de Baya por Sector"
            )
            fig_diam.update_layout(yaxis_title="Diámetro Promedio (mm)", xaxis_title="")
            st.plotly_chart(fig_diam, use_container_width=True)
        else:
            st.info("Formato de datos de diámetro no reconocido.")
    else:
        st.info("Aún no hay mediciones de Diámetro de Baya.")

with col_crec2:
    st.markdown("**🌿 Último Estado Fenológico**")
    if not df_feno.empty:
        # Solo tomamos la evaluación más reciente por sector
        ultima_fecha = df_feno['Fecha'].max()
        df_feno_reciente = df_feno[df_feno['Fecha'] == ultima_fecha]
        
        # Columnas de fenología
        cols_feno = ['Punta_algodon', 'Punta_verde', 'Salida_de_hojas', 'Hojas_extendidas', 'Racimos_visibles']
        df_feno_resumen = df_feno_reciente.groupby('Sector')[cols_feno].sum().reset_index()
        
        # Transformar para plotly (Melt)
        df_feno_melt = df_feno_resumen.melt(id_vars=['Sector'], value_vars=cols_feno, var_name='Etapa', value_name='Conteo')
        
        fig_feno = px.bar(
            df_feno_melt, x='Sector', y='Conteo', color='Etapa',
            title=f"Estado Fenológico (Al {ultima_fecha.strftime('%d/%m/%Y')})",
            barmode='stack',
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_feno.update_layout(xaxis_title="Sector", yaxis_title="Cantidad de Plantas")
        st.plotly_chart(fig_feno, use_container_width=True)
    else:
        st.info("Aún no hay evaluaciones fenológicas registradas.")