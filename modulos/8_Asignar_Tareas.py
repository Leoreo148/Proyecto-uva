import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client

# 🚨 CANDADO DE SEGURIDAD
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

# Solo Ingeniero (Admin), Sanidad y Programador pueden asignar tareas
if st.session_state.get("rol") not in ["Admin", "Programador", "Sanidad"]:
    st.error("🚫 Acceso denegado. Solo el Ingeniero o Jefe de Sanidad pueden asignar tareas al evaluador.")
    st.stop()

st.set_page_config(page_title="Asignar Tareas - Project Uva", page_icon="📋", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .tarea-card { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white; padding: 18px; border-radius: 12px; margin-bottom: 10px;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
    }
    .tarea-pendiente { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
    .tarea-hecha { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); opacity: 0.7; }
    </style>
""", unsafe_allow_html=True)

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE TAREAS ---
@st.cache_data(ttl=30)
def cargar_tareas():
    try:
        res = supabase.table('Tareas_Evaluador').select("*").order('Fecha', desc=True).limit(100).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.sidebar.error(f"⚠️ Error cargando tareas: {e}")
        return pd.DataFrame()

# --- INTERFAZ ---
st.title("📋 Asignar Tareas al Evaluador de Campo")
st.markdown(f"*Asignando como:* **{st.session_state.get('nombre', 'Desconocido')}** ({st.session_state.get('rol', '')})")
st.divider()

tab_nueva, tab_historial = st.tabs(["➕ Nueva Tarea", "📚 Historial de Tareas"])

# ==========================================
# TAB 1: CREAR NUEVA TAREA
# ==========================================
with tab_nueva:
    with st.form("form_tarea", clear_on_submit=True):
        st.markdown("### 🎯 Definir la Tarea")
        
        c1, c2 = st.columns(2)
        fecha_tarea = c1.date_input("📅 Fecha de la tarea", value=date.today())
        
        MODULOS_EVALUACION = [
            "🔬 Evaluación Sanitaria (Plagas/Enfermedades)",
            "🪰 Monitoreo de Mosca de la Fruta",
            "🌱 Evaluación Fenológica",
            "🍇 Diámetro de Baya",
            "✂️ Control de Raleo"
        ]
        modulo_sel = c2.selectbox("📦 Módulo / Tipo de Evaluación", MODULOS_EVALUACION)
        
        c3, c4 = st.columns(2)
        SECTORES_UVA = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2', 'K3']
        sector_sel = c3.selectbox("📍 Sector a evaluar", SECTORES_UVA)
        
        PRIORIDADES = ["🟢 Normal", "🟡 Importante", "🔴 Urgente"]
        prioridad = c4.selectbox("⚡ Prioridad", PRIORIDADES)
        
        instrucciones = st.text_area(
            "📝 Instrucciones específicas (Opcional)", 
            placeholder="Ej: Revisar especialmente la hilera 3 donde se vio Oidio ayer. Tomar fotos si hay daño severo."
        )
        
        if st.form_submit_button("📡 Enviar Tarea al Evaluador", type="primary"):
            # Mapear módulo a nombre corto
            modulo_corto = modulo_sel.split("(")[0].strip()
            
            tarea_data = {
                "Fecha": str(fecha_tarea),
                "Modulo": modulo_corto,
                "Sector": sector_sel,
                "Prioridad": prioridad,
                "Instrucciones": instrucciones if instrucciones else None,
                "Estado": "Pendiente",
                "Asignado_por": st.session_state.get("nombre", "Sistema"),
                "Rol_Asignador": st.session_state.get("rol", ""),
            }
            
            try:
                supabase.table('Tareas_Evaluador').insert(tarea_data).execute()
                st.success(f"✅ ¡Tarea enviada! El evaluador verá: **{modulo_corto}** en el sector **{sector_sel}** para el **{fecha_tarea}**.")
                cargar_tareas.clear()
                st.balloons()
            except Exception as e:
                st.error(f"❌ Error al guardar la tarea: {e}")
                st.info("💡 **¿Primera vez?** Necesitas crear la tabla `Tareas_Evaluador` en Supabase. Revisa las instrucciones del módulo.")

# ==========================================
# TAB 2: HISTORIAL
# ==========================================
with tab_historial:
    df_tareas = cargar_tareas()
    
    if df_tareas.empty:
        st.info("📭 No hay tareas registradas aún.")
    else:
        # Filtro rápido
        filtro_estado = st.radio("Filtrar:", ["Todas", "Pendiente", "Completada"], horizontal=True)
        
        if filtro_estado != "Todas":
            df_show = df_tareas[df_tareas['Estado'] == filtro_estado]
        else:
            df_show = df_tareas
        
        if df_show.empty:
            st.info(f"No hay tareas con estado '{filtro_estado}'.")
        else:
            for _, t in df_show.iterrows():
                estado = t.get('Estado', 'Pendiente')
                css_class = "tarea-hecha" if estado == "Completada" else "tarea-pendiente"
                icono_estado = "✅" if estado == "Completada" else "⏳"
                
                st.markdown(f"""
                <div class="tarea-card {css_class}">
                    <strong>{icono_estado} {t.get('Modulo', '')} — Sector {t.get('Sector', '')}</strong><br>
                    📅 {t.get('Fecha', '')} | ⚡ {t.get('Prioridad', '')} | 👤 Asignó: {t.get('Asignado_por', '')}<br>
                    {f"📝 {t.get('Instrucciones', '')}" if t.get('Instrucciones') else ""}
                </div>
                """, unsafe_allow_html=True)
