import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta
from supabase import create_client

st.set_page_config(page_title="Clima - Fundo", page_icon="🌤️", layout="wide")

st.title("🌤️ Estación Meteorológica e Índice de Estrés")
st.markdown("Monitorización del clima y su impacto en las plantas (Horas frío, estrés térmico).")

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
            # Traemos los últimos 14 días de datos (suponiendo 1 dato por hora = ~336 datos)
            res = supabase.table("Clima").select("*").order("fecha_hora", desc=True).limit(500).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                df['fecha_hora'] = pd.to_datetime(df['fecha_hora'])
                return df.sort_values('fecha_hora')
        except:
            pass
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def obtener_datos_clima_satelite():
    # Coordenadas aproximadas (Puedes cambiarlas a las exactas de tu fundo)
    lat = -5.19 # Piura, Peru (ejemplo)
    lon = -80.62
    
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m,shortwave_radiation&past_days=14&forecast_days=3&timezone=auto"
    
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        df = pd.DataFrame({
            "fecha_hora": pd.to_datetime(data["hourly"]["time"]),
            "temp_out": data["hourly"]["temperature_2m"],
            "hum_out": data["hourly"]["relative_humidity_2m"],
            "lluvia_mm": data["hourly"]["precipitation"],
            "viento_vel": data["hourly"]["wind_speed_10m"],
            "radiacion_solar": data["hourly"]["shortwave_radiation"]
        })
        return df
    return None

# --- LÓGICA DE DATOS ---
df_clima = obtener_datos_clima_supabase()
origen_datos = "Estación Física (WeatherLink)"

if df_clima.empty:
    st.info("💡 **Aviso:** No se encontraron datos en Supabase. Mostrando datos satelitales en tiempo real de alta precisión (Open-Meteo) temporalmente.")
    df_clima = obtener_datos_clima_satelite()
    origen_datos = "Satélite (Open-Meteo)"

if df_clima is not None and not df_clima.empty:
    st.caption(f"📍 Origen de la información: {origen_datos}")
    
    # --- METRICAS ACTUALES ---
    df_actual = df_clima[df_clima["fecha_hora"] <= datetime.now()].iloc[-1]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Temperatura Actual", f"{df_actual['temp_out']} °C")
    col2.metric("Humedad Relativa", f"{df_actual['hum_out']} %")
    col3.metric("Velocidad Viento", f"{df_actual['viento_vel']} km/h")
    col4.metric("Radiación Solar", f"{df_actual.get('radiacion_solar', 0)} W/m²")
    
    st.markdown("---")
    
    # --- ANALISIS AGRONÓMICO (UVA) ---
    st.subheader("🍇 Análisis de Impacto en Planta (Últimos 14 días)")
    
    df_pasado = df_clima[df_clima["fecha_hora"] < datetime.now()]
    
    # Horas frío (Temp < 7°C, aunque para algunas uvas se usa < 10°C)
    horas_frio = len(df_pasado[df_pasado["temp_out"] < 7.2])
    
    # Horas de estrés por calor (Temp > 35°C)
    horas_estres = len(df_pasado[df_pasado["temp_out"] > 35.0])
    
    # Lluvia acumulada
    lluvia_total = df_pasado["lluvia_mm"].sum()
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.info(f"❄️ **Horas Frío Acumuladas:** {horas_frio} horas\n\n*(Vital para romper la dormancia de la yema)*")
    with c2:
        if horas_estres > 10:
            st.error(f"🔥 **Alerta de Estrés Térmico:** {horas_estres} horas sobre 35°C\n\n*(La planta cierra estomas y detiene el crecimiento. Requiere más riego)*")
        else:
            st.success(f"🔥 **Estrés Térmico:** {horas_estres} horas sobre 35°C\n\n*(Nivel aceptable)*")
    with c3:
        st.info(f"💧 **Precipitación Acumulada:** {lluvia_total:.1f} mm")
        
    st.markdown("---")
    
    # --- GRÁFICOS ---
    st.subheader("📈 Evolución de Temperatura y Humedad")
    fig1 = px.line(df_clima, x="fecha_hora", y=["temp_out", "hum_out"], 
                   labels={"value": "Medición", "variable": "Indicador"},
                   title="Temperatura (°C) y Humedad (%)")
    
    # Línea roja para peligro de estrés
    fig1.add_hline(y=35, line_dash="dot", line_color="red", annotation_text="Peligro Estrés (>35°C)")
    fig1.add_vline(x=datetime.now(), line_dash="dash", line_color="green", annotation_text="AHORA")
    
    st.plotly_chart(fig1, use_container_width=True)
    
    if "radiacion_solar" in df_clima.columns:
        st.subheader("☀️ Radiación Solar (W/m²)")
        fig2 = px.area(df_clima, x="fecha_hora", y="radiacion_solar", color_discrete_sequence=["orange"])
        st.plotly_chart(fig2, use_container_width=True)

else:
    st.error("No hay datos disponibles en este momento.")
