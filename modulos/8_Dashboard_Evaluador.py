import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta, timezone
from supabase import create_client

# Zona horaria de Perú (UTC-5, sin horario de verano)
ZONA_PERU = timezone(timedelta(hours=-5))

# 🚨 CANDADO DE SEGURIDAD
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

# Solo el Evaluador (y Programador para soporte técnico) ven este panel
if st.session_state.get("rol") not in ["Evaluador", "Programador"]:
    st.error("🚫 Acceso denegado. Este es el panel exclusivo del Evaluador de Campo.")
    st.stop()

st.set_page_config(page_title="Mi Panel - Evaluador", page_icon="🎯", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0f0f1a; }
    .tarea-urgente {
        background: linear-gradient(135deg, #ff416c, #ff4b2b);
        color: white; padding: 20px; border-radius: 14px; margin-bottom: 12px;
        box-shadow: 0 6px 20px rgba(255, 65, 108, 0.4);
        border-left: 5px solid #fff;
    }
    .tarea-importante {
        background: linear-gradient(135deg, #f7971e, #ffd200);
        color: #1a1a2e; padding: 20px; border-radius: 14px; margin-bottom: 12px;
        box-shadow: 0 6px 20px rgba(247, 151, 30, 0.3);
        border-left: 5px solid #fff;
    }
    .tarea-normal {
        background: linear-gradient(135deg, #11998e, #38ef7d);
        color: #1a1a2e; padding: 20px; border-radius: 14px; margin-bottom: 12px;
        box-shadow: 0 6px 20px rgba(17, 153, 142, 0.3);
        border-left: 5px solid #fff;
    }
    .tarea-completada {
        background: linear-gradient(135deg, #2c3e50, #4ca1af);
        color: #ccc; padding: 16px; border-radius: 14px; margin-bottom: 8px;
        opacity: 0.6; text-decoration: line-through;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 20px; border-radius: 14px; text-align: center;
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.3);
    }
    .stat-card h2 { margin: 0; font-size: 2.5em; }
    .stat-card p { margin: 5px 0 0 0; opacity: 0.8; }
    .saludo-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        font-size: 2em; font-weight: 800; margin-bottom: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE TAREAS ---
@st.cache_data(ttl=15)  # Refresco cada 15 seg para campo
def cargar_mis_tareas():
    try:
        res = supabase.table('Tareas_Evaluador').select("*").order('Fecha', desc=True).limit(50).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except:
        return pd.DataFrame()

# --- INTERFAZ ---
nombre_user = st.session_state.get("nombre", "Evaluador")
ahora_peru = datetime.now(ZONA_PERU)
hora_actual = ahora_peru.hour
if hora_actual < 12:
    saludo = "☀️ Buenos días"
elif hora_actual < 18:
    saludo = "🌤️ Buenas tardes"
else:
    saludo = "🌙 Buenas noches"

st.markdown(f'<div class="saludo-header">{saludo}, {nombre_user}</div>', unsafe_allow_html=True)
st.caption(f"📅 {ahora_peru.strftime('%A %d de %B, %Y')} — Tu panel de tareas del día")
st.divider()

df_tareas = cargar_mis_tareas()

# Filtrar tareas de hoy (usando fecha de Perú)
hoy_str = str(ahora_peru.date())
if not df_tareas.empty:
    df_hoy = df_tareas[df_tareas['Fecha'] == hoy_str].copy()
    df_pendientes = df_hoy[df_hoy['Estado'] == 'Pendiente'] if not df_hoy.empty else pd.DataFrame()
    df_completadas_hoy = df_hoy[df_hoy['Estado'] == 'Completada'] if not df_hoy.empty else pd.DataFrame()
else:
    df_hoy = pd.DataFrame()
    df_pendientes = pd.DataFrame()
    df_completadas_hoy = pd.DataFrame()

# --- MÉTRICAS RÁPIDAS ---
total_pendientes = len(df_pendientes)
total_completadas = len(df_completadas_hoy)
total_hoy = len(df_hoy)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"""<div class="stat-card">
        <h2>{'🎉' if total_pendientes == 0 else total_pendientes}</h2>
        <p>{'¡Sin tareas!' if total_pendientes == 0 else 'Tareas Pendientes'}</p>
    </div>""", unsafe_allow_html=True)
with c2:
    st.markdown(f"""<div class="stat-card">
        <h2>{total_completadas}</h2>
        <p>Completadas Hoy</p>
    </div>""", unsafe_allow_html=True)
with c3:
    progreso = int((total_completadas / total_hoy * 100) if total_hoy > 0 else 0)
    st.markdown(f"""<div class="stat-card">
        <h2>{progreso}%</h2>
        <p>Progreso del Día</p>
    </div>""", unsafe_allow_html=True)

st.divider()

# --- TAREAS PENDIENTES ---
if total_pendientes > 0:
    st.subheader(f"⏳ Tareas Pendientes para Hoy ({total_pendientes})")
    
    # Ordenar por prioridad (Urgente primero)
    orden_prioridad = {"🔴 Urgente": 0, "🟡 Importante": 1, "🟢 Normal": 2}
    df_pendientes['_orden'] = df_pendientes['Prioridad'].map(orden_prioridad).fillna(3)
    df_pendientes = df_pendientes.sort_values('_orden')
    
    for _, tarea in df_pendientes.iterrows():
        prioridad = tarea.get('Prioridad', '🟢 Normal')
        if '🔴' in str(prioridad):
            css_class = "tarea-urgente"
        elif '🟡' in str(prioridad):
            css_class = "tarea-importante"
        else:
            css_class = "tarea-normal"
        
        modulo = tarea.get('Modulo', '')
        sector = tarea.get('Sector', '')
        instrucciones = tarea.get('Instrucciones', '')
        asigno = tarea.get('Asignado_por', '')
        
        st.markdown(f"""
        <div class="{css_class}">
            <strong style="font-size: 1.2em;">{modulo}</strong><br>
            📍 Sector: <strong>{sector}</strong> &nbsp;|&nbsp; ⚡ {prioridad} &nbsp;|&nbsp; 👤 {asigno}<br>
            {f'📝 <em>{instrucciones}</em>' if instrucciones else ''}
        </div>
        """, unsafe_allow_html=True)
        
        # Botón para marcar como completada
        if st.button(f"✅ Marcar como COMPLETADA", key=f"done_{tarea.get('id', '')}"):
            try:
                supabase.table('Tareas_Evaluador').update({
                    "Estado": "Completada",
                    "Completada_a": datetime.now().isoformat()
                }).eq('id', tarea['id']).execute()
                st.success(f"🎉 ¡Tarea completada! Buen trabajo.")
                cargar_mis_tareas.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
        
        st.write("")  # Espaciador

elif total_hoy > 0:
    st.success("🎉 **¡Felicidades!** Has completado todas las tareas del día. Puedes irte tranquilo.")
else:
    st.info("📭 No tienes tareas asignadas para hoy. Consulta con el Ingeniero o el Jefe de Sanidad.")

# --- TAREAS COMPLETADAS (colapsadas) ---
if not df_completadas_hoy.empty:
    with st.expander(f"✅ Tareas Completadas Hoy ({len(df_completadas_hoy)})"):
        for _, t in df_completadas_hoy.iterrows():
            st.markdown(f"""
            <div class="tarea-completada">
                ✅ {t.get('Modulo', '')} — Sector {t.get('Sector', '')} | 👤 Asignó: {t.get('Asignado_por', '')}
            </div>
            """, unsafe_allow_html=True)

# --- HISTORIAL SEMANAL ---
st.divider()
with st.expander("📊 Mi Rendimiento Semanal"):
    if not df_tareas.empty:
        df_tareas['Fecha'] = pd.to_datetime(df_tareas['Fecha'], errors='coerce')
        hace_7_dias = pd.Timestamp(date.today() - pd.Timedelta(days=7))
        df_semana = df_tareas[df_tareas['Fecha'] >= hace_7_dias]
        
        if not df_semana.empty:
            total_sem = len(df_semana)
            completadas_sem = len(df_semana[df_semana['Estado'] == 'Completada'])
            pct_sem = int(completadas_sem / total_sem * 100) if total_sem > 0 else 0
            
            m1, m2, m3 = st.columns(3)
            m1.metric("📋 Tareas Asignadas (7 días)", total_sem)
            m2.metric("✅ Completadas", completadas_sem)
            m3.metric("📈 Tasa de Cumplimiento", f"{pct_sem}%")
            
            # Gráfico por día
            df_por_dia = df_semana.groupby([df_semana['Fecha'].dt.date, 'Estado']).size().reset_index(name='Cantidad')
            df_por_dia.columns = ['Fecha', 'Estado', 'Cantidad']
            
            import plotly.express as px
            fig = px.bar(df_por_dia, x='Fecha', y='Cantidad', color='Estado', barmode='stack',
                        color_discrete_map={"Pendiente": "#ff4b2b", "Completada": "#38ef7d"})
            fig.update_layout(height=250)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos de la última semana.")
    else:
        st.info("No hay historial disponible aún.")

# --- BOTÓN DE REFRESCO ---
st.divider()
if st.button("🔄 Refrescar Tareas", use_container_width=True):
    cargar_mis_tareas.clear()
    st.rerun()
