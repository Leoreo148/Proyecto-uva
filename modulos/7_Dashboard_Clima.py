import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
from supabase import create_client

# 🚨 1. CANDADO DE SEGURIDAD (Portero)
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal antes de acceder a este módulo.")
    st.stop()

st.set_page_config(page_title="Clima - Fundo", page_icon="🌤️", layout="wide")
st.title("🌤️ Estación Meteorológica e Índice de Estrés")
st.markdown("Monitorización del clima, DPV y radar predictivo de riesgo sanitario.")

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except:
        return None

supabase = init_supabase()

def obtener_datos_clima_supabase():
    if supabase:
        try:
            res = supabase.table("clima").select("*").order("fecha_hora", desc=True).limit(500).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['fecha_hora'] = pd.to_datetime(df['fecha_hora'])
                return df.sort_values('fecha_hora')
        except Exception as e:
            st.sidebar.warning(f"⚠️ Supabase Clima: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def _fetch_open_meteo():
    lat, lon = -7.156903, -79.445073
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,shortwave_radiation"
        f"&past_days=14&forecast_days=3&timezone=auto"
    )
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            return pd.DataFrame({
                "fecha_hora":     pd.to_datetime(data["hourly"]["time"]),
                "temp_out":       data["hourly"]["temperature_2m"],
                "hum_out":        data["hourly"]["relative_humidity_2m"],
                "lluvia_mm":      data["hourly"]["precipitation"],
                "viento_vel":     data["hourly"]["wind_speed_10m"],
                "radiacion_solar":data["hourly"]["shortwave_radiation"],
            })
        elif r.status_code == 429:
            # Límite diario excedido — NO limpiar caché para no gastar más peticiones
            st.sidebar.warning("⏳ Límite diario de Open-Meteo alcanzado. Datos del satélite disponibles mañana.")
        else:
            st.sidebar.error(f"Error Open-Meteo: {r.status_code}")
    except Exception as e:
        st.sidebar.error(f"Error de red API Clima: {e}")
    return pd.DataFrame()

def obtener_datos_clima_satelite():
    df = _fetch_open_meteo()
    # Solo limpiar caché si el error NO es 429 (límite de cuota)
    if df.empty:
        try:
            r_check = requests.get("https://api.open-meteo.com/v1/forecast?latitude=-7.156903&longitude=-79.445073&hourly=temperature_2m&past_days=1&forecast_days=1&timezone=auto", timeout=5)
            if r_check.status_code != 429:
                _fetch_open_meteo.clear()  # Solo limpiar si NO es problema de cuota
        except:
            pass
    return df

# ─────────────────────────────────────────────
# 3. FUNCIÓN DPV (Déficit de Presión de Vapor)
# ─────────────────────────────────────────────
def calcular_dpv(temp_c, hr_pct):
    """
    DPV (kPa) = Presión de vapor saturante × (1 − HR/100)
    Referencia: Allen et al. (1998), FAO-56.
    Rango: 
      <0.4  → Zona húmeda (riesgo Botrytis/Oidio)
      0.4-0.8 → Óptimo bajo (crecimiento activo con riesgo)
      0.8-1.6 → Óptimo vitícola ✅
      1.6-2.5 → Estrés hídrico leve ⚠️
      >2.5  → Estrés severo (estomas cerrados) 🔥
    """
    svp = 0.6108 * np.exp(17.27 * temp_c / (temp_c + 237.3))
    return svp * (1 - hr_pct / 100)

def zona_dpv(dpv):
    if dpv < 0.4:   return "🌧️ Zona Húmeda"
    if dpv < 0.8:   return "🌿 Óptimo Bajo"
    if dpv < 1.6:   return "✅ Óptimo"
    if dpv < 2.5:   return "⚠️ Estrés Leve"
    return "🔥 Estrés Severo"

# ─────────────────────────────────────────────
# 4. FUNCIÓN RADAR DE RIESGO DE PLAGAS
# ─────────────────────────────────────────────
def calcular_riesgo_plagas(df_pasado):
    """
    Calcula índices de riesgo para las 3 plagas/enfermedades clave.
    Devuelve un dict con puntaje 0-100 y nivel de alerta.
    """
    if df_pasado.empty:
        return {}

    temp  = df_pasado['temp_out']
    hr    = df_pasado['hum_out']
    dpv   = df_pasado['dpv']
    n     = len(df_pasado)

    # --- OIDIO (Uncinula necator) ---
    # Favorable: 20-30°C y HR > 60% y DPV < 1.2
    h_oidio = ((temp >= 20) & (temp <= 30) & (hr > 60) & (dpv < 1.2)).sum()
    riesgo_oidio = min(100, round(h_oidio / n * 200))

    # --- BOTRYTIS (Botrytis cinerea) ---
    # Favorable: 15-25°C y HR > 85%
    h_bot = ((temp >= 15) & (temp <= 25) & (hr > 85)).sum()
    riesgo_botrytis = min(100, round(h_bot / n * 250))

    # --- ARAÑITA ROJA (Tetranychus urticae) ---
    # Favorable: T > 28°C y HR < 50% (condiciones secas y calurosas)
    h_ara = ((temp > 28) & (hr < 50)).sum()
    riesgo_aranita = min(100, round(h_ara / n * 300))

    def nivel(pct):
        if pct < 20:  return "🟢 Bajo"
        if pct < 50:  return "🟡 Moderado"
        if pct < 75:  return "🟠 Alto"
        return "🔴 Crítico"

    return {
        "Oidio":         {"pct": riesgo_oidio,    "nivel": nivel(riesgo_oidio)},
        "Botrytis":      {"pct": riesgo_botrytis, "nivel": nivel(riesgo_botrytis)},
        "Arañita Roja":  {"pct": riesgo_aranita,  "nivel": nivel(riesgo_aranita)},
    }

# ─────────────────────────────────────────────
# CARGA DE DATOS + DIAGNÓSTICO
# ─────────────────────────────────────────────
df_clima = obtener_datos_clima_supabase()
origen_datos = "Estación Física (WeatherLink)"

if df_clima.empty:
    # Fallback a satélite
    df_clima = obtener_datos_clima_satelite()
    origen_datos = "Satélite (Open-Meteo)"

if df_clima is None or df_clima.empty:
    st.error("❌ No hay datos climáticos disponibles en este momento.")
    st.info("💡 **Posibles causas:** La tabla `clima` en Supabase está vacía, o el límite diario de la API de satélites (Open-Meteo) fue excedido. Vuelve a intentarlo mañana o sube datos manualmente a Supabase.")
    
    # --- DIAGNÓSTICO DETALLADO ---
    with st.expander("🔬 Ver Diagnóstico Técnico"):
        st.write("**Probando Supabase...**")
        try:
            res = supabase.table("Clima").select("*").limit(1).execute()
            if res.data:
                st.success(f"✅ Supabase tiene datos: {res.data[0]}")
            else:
                st.warning("⚠️ Supabase conecta bien pero la tabla 'Clima' está VACÍA.")
        except Exception as e:
            st.error(f"❌ Error en Supabase: {e}")

        st.write("**Probando Open-Meteo (satélite)...**")
        try:
            import requests as req
            r = req.get(
                "https://api.open-meteo.com/v1/forecast"
                "?latitude=-7.156903&longitude=-79.445073"
                "&hourly=temperature_2m,relative_humidity_2m&past_days=1&forecast_days=1&timezone=auto",
                timeout=10
            )
            st.write(f"HTTP Status: `{r.status_code}`")
            if r.status_code == 200:
                st.success(f"✅ Open-Meteo responde OK. Primeros datos: `{str(r.json()['hourly']['time'][:3])}`")
            else:
                st.error(f"❌ Open-Meteo devuelve error: `{r.text[:300]}`")
        except Exception as e:
            st.error(f"❌ No se puede alcanzar Open-Meteo: `{e}`")
    st.stop()

# Calcular DPV en todo el dataframe
df_clima['dpv'] = calcular_dpv(df_clima['temp_out'], df_clima['hum_out']).round(3)

st.caption(f"📍 Origen: {origen_datos}")

# ─────────────────────────────────────────────
# FILTROS DE FECHA
# ─────────────────────────────────────────────
st.markdown("### 🔎 Filtro de Tiempo")
fecha_min = df_clima["fecha_hora"].min().date()
fecha_max = df_clima["fecha_hora"].max().date()

rango = st.date_input(
    "Selecciona el rango de fechas:",
    value=(fecha_min, fecha_max),
    min_value=fecha_min,
    max_value=fecha_max,
)

if isinstance(rango, (list, tuple)) and len(rango) == 2:
    f_ini, f_fin = rango
else:
    f_ini = f_fin = rango[0] if isinstance(rango, (list, tuple)) else rango

mask       = (df_clima['fecha_hora'].dt.date >= f_ini) & (df_clima['fecha_hora'].dt.date <= f_fin)
df_filtrado = df_clima.loc[mask]

if df_filtrado.empty:
    st.warning("No hay datos en el rango seleccionado.")
    st.stop()

# ─────────────────────────────────────────────
# MÉTRICAS ACTUALES
# ─────────────────────────────────────────────
df_actual = df_clima[df_clima["fecha_hora"] <= datetime.now()]
if df_actual.empty:
    df_actual = df_clima.iloc[[-1]]
else:
    df_actual = df_actual.iloc[[-1]]

row = df_actual.iloc[0]
dpv_actual = row['dpv']

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("🌡️ Temperatura", f"{row['temp_out']} °C")
col2.metric("💧 Humedad", f"{row['hum_out']} %")
col3.metric("💨 Viento", f"{row['viento_vel']} km/h")
col4.metric("☀️ Radiación", f"{row.get('radiacion_solar', 0):.0f} W/m²")
col5.metric("🌬️ DPV Actual", f"{dpv_actual:.2f} kPa", zona_dpv(dpv_actual), delta_color="off")

st.markdown("---")

# ─────────────────────────────────────────────
# ANÁLISIS AGRONÓMICO
# ─────────────────────────────────────────────
st.subheader("🍇 Análisis de Impacto en Planta (Periodo Seleccionado)")
df_pasado = df_filtrado[df_filtrado["fecha_hora"] < datetime.now()].copy()

# 2. ✅ HORAS DE RIESGO SANITARIO (reemplaza "Horas Frío" que nunca ocurre en Trujillo)
# Pacanguilla está en la costa norte de Perú — la temperatura nunca baja de 7°C.
# En cambio, las noches húmedas (HR > 80%) en el rango térmico de hongos SÍ son frecuentes.
horas_riesgo_sanitario = ((df_pasado['hum_out'] > 80) & 
                           (df_pasado['temp_out'] >= 15) & 
                           (df_pasado['temp_out'] <= 30)).sum()

horas_estres   = (df_pasado["temp_out"] > 35).sum()
lluvia_total   = df_pasado["lluvia_mm"].sum()
horas_dpv_opt  = ((df_pasado['dpv'] >= 0.8) & (df_pasado['dpv'] <= 1.6)).sum()

c1, c2, c3, c4 = st.columns(4)

with c1:
    if horas_riesgo_sanitario > 48:
        st.error(f"🍄 **Noches de Riesgo Fúngico:** {horas_riesgo_sanitario} hrs\n\n*(HR>80% en zona térmica de Oidio/Botrytis. Revisar programa de aplicaciones)*")
    elif horas_riesgo_sanitario > 12:
        st.warning(f"🍄 **Noches de Riesgo Fúngico:** {horas_riesgo_sanitario} hrs\n\n*(Vigilar. Monitorear signos de Oidio/Botrytis en campo)*")
    else:
        st.success(f"🍄 **Noches de Riesgo Fúngico:** {horas_riesgo_sanitario} hrs\n\n*(Nivel aceptable)*")
with c2:
    if horas_estres > 10:
        st.error(f"🔥 **Estrés Térmico:** {horas_estres} hrs > 35°C\n\n*(Planta cierra estomas. Más riego)*")
    else:
        st.success(f"🔥 **Estrés Térmico:** {horas_estres} hrs > 35°C\n\n*(Nivel aceptable)*")
with c3:
    st.info(f"💧 **Precipitación:** {lluvia_total:.1f} mm acumulado")
with c4:
    st.info(f"✅ **Horas DPV Óptimo:** {horas_dpv_opt} hrs\n\n*(DPV 0.8–1.6 kPa: condiciones ideales de crecimiento)*")

st.markdown("---")

# ─────────────────────────────────────────────
# 4. RADAR PREDICTIVO DE PLAGAS
# ─────────────────────────────────────────────
st.subheader("🎯 Radar Predictivo de Riesgo Sanitario")
st.caption("Basado en las condiciones climáticas del periodo seleccionado vs. las condiciones favorables para cada plaga.")

riesgos = calcular_riesgo_plagas(df_pasado)

if riesgos:
    rc1, rc2, rc3 = st.columns(3)
    for col, (plaga, datos) in zip([rc1, rc2, rc3], riesgos.items()):
        pct   = datos['pct']
        nivel = datos['nivel']
        color = "#e74c3c" if pct >= 75 else "#e67e22" if pct >= 50 else "#f1c40f" if pct >= 20 else "#2ecc71"

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct,
            title={"text": plaga, "font": {"size": 16}},
            number={"suffix": "%", "font": {"size": 24}},
            gauge={
                "axis": {"range": [0, 100]},
                "bar": {"color": color},
                "steps": [
                    {"range": [0,  20], "color": "#d5f5e3"},
                    {"range": [20, 50], "color": "#fef9e7"},
                    {"range": [50, 75], "color": "#fdebd0"},
                    {"range": [75,100], "color": "#fadbd8"},
                ],
                "threshold": {"line": {"color": "black", "width": 2}, "thickness": 0.75, "value": 75}
            }
        ))
        fig_gauge.update_layout(height=220, margin=dict(t=30, b=10, l=20, r=20))
        col.plotly_chart(fig_gauge, use_container_width=True)
        col.markdown(f"<center><b>{nivel}</b></center>", unsafe_allow_html=True)

st.markdown("---")

# ─────────────────────────────────────────────
# GRÁFICO DPV (reemplaza el gráfico T+HR básico)
# ─────────────────────────────────────────────
st.subheader("🌬️ Evolución del DPV (Déficit de Presión de Vapor)")
st.caption("DPV < 0.4 kPa → riesgo fúngico | DPV 0.8–1.6 → óptimo vitícola | DPV > 2.5 → estrés severo")

fig_dpv = go.Figure()
fig_dpv.add_trace(go.Scatter(
    x=df_filtrado['fecha_hora'], y=df_filtrado['dpv'],
    mode='lines', name='DPV (kPa)',
    line=dict(color='#8e44ad', width=2),
    fill='tozeroy', fillcolor='rgba(142,68,173,0.1)'
))
fig_dpv.add_hline(y=0.4,  line_dash="dot",  line_color="blue",   annotation_text="Límite húmedo (0.4)")
fig_dpv.add_hline(y=1.6,  line_dash="dash", line_color="orange", annotation_text="Inicio estrés (1.6)")
fig_dpv.add_hline(y=2.5,  line_dash="dot",  line_color="red",    annotation_text="Estrés severo (2.5)")
ahora_ms = datetime.now().timestamp() * 1000
fig_dpv.add_vline(x=ahora_ms, line_dash="dash", line_color="green", annotation_text="AHORA")
fig_dpv.update_layout(yaxis_title="DPV (kPa)", xaxis_title="Fecha/Hora", height=350)
st.plotly_chart(fig_dpv, use_container_width=True)

# Gráfico T + HR de respaldo (ahora secundario)
with st.expander("📊 Ver gráfico Temperatura + Humedad (detalle)"):
    fig1 = px.line(df_filtrado, x="fecha_hora", y=["temp_out", "hum_out"],
                   labels={"value": "Medición", "variable": "Indicador"},
                   title="Temperatura (°C) y Humedad Relativa (%)")
    fig1.add_hline(y=35, line_dash="dot", line_color="red",  annotation_text="Peligro Estrés (>35°C)")
    fig1.add_hline(y=80, line_dash="dot", line_color="blue", annotation_text="Riesgo Fúngico HR (>80%)")
    fig1.add_vline(x=ahora_ms, line_dash="dash", line_color="green")
    st.plotly_chart(fig1, use_container_width=True)

if "radiacion_solar" in df_filtrado.columns:
    st.subheader("☀️ Radiación Solar (W/m²)")
    fig2 = px.area(df_filtrado, x="fecha_hora", y="radiacion_solar", color_discrete_sequence=["orange"])
    st.plotly_chart(fig2, use_container_width=True)
