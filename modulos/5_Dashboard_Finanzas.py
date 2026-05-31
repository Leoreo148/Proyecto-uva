import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# --- 1. CANDADO DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal para acceder.")
    st.stop()

if st.session_state["rol"] not in ["Admin", "Programador", "Costos"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para la Gerencia y Administración.")
    st.stop()

# --- 2. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Módulo Financiero - Project Uva", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONEXIÓN A SUPABASE ---
from supabase import create_client
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. CARGA DE DATA CON FUNCIÓN DE LIMPIEZA ---
@st.cache_data(ttl=60)
def cargar_data_financiera():
    try:
        res_horas = supabase.table('Registro_Horas_Tractor').select("*").execute()
        res_personal = supabase.table('Personal').select("id, nombre_completo, rol, Sueldo_Hora, activo").execute()
        return pd.DataFrame(res_horas.data), pd.DataFrame(res_personal.data)
    except Exception as e:
        st.error(f"❌ Error crítico en servidor: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_horas_raw, df_personal_raw = cargar_data_financiera()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💰 Centro de Control Financiero y Planillas")
st.write("Auditoría en tiempo real de mano de obra y costos operativos de maquinaria.")
st.divider()

# 🔄 BOTÓN DE EMERGENCIA EN SIDEBAR PARA BORRAR CACHÉ
st.sidebar.header("⚙️ Controles de Datos")
if st.sidebar.button("🔄 Forzar Actualización de Datos"):
    st.cache_data.clear()
    st.rerun()

if df_horas_raw.empty:
    st.info("📊 La tabla 'Registro_Horas_Tractor' está vacía en Supabase. Esperando primer registro físico del campo.")
elif df_personal_raw.empty:
    st.error("⚠️ No se encontraron empleados en la tabla 'Personal'. Registra al menos un trabajador con sueldo.")
else:
    # --- FILTROS TEMPORALES ---
    st.sidebar.write("---")
    st.sidebar.header("🗓️ Periodo de Liquidación")
    f_inicio = st.sidebar.date_input("Fecha Inicio", value=date.today() - timedelta(days=30)) # Ampliado a 30 días para pruebas
    f_fin = st.sidebar.date_input("Fecha Fin", value=date.today() + timedelta(days=1)) # +1 día para evitar sustos de zona horaria
    
    # Procesamos fechas de forma segura
    df_horas_raw['Fecha'] = pd.to_datetime(df_horas_raw['Fecha']).dt.date
    df_horas_filtradas = df_horas_raw[(df_horas_raw['Fecha'] >= f_inicio) & (df_horas_raw['Fecha'] <= f_fin)]
    
    # Cruce relacional
    df_planilla = pd.merge(
        df_horas_filtradas, 
        df_personal_raw[['id', 'nombre_completo', 'rol', 'Sueldo_Hora']], 
        left_on='personal_id', 
        right_on='id', 
        how='left'
    )
    
    # 💡 FIX ANTI-MAYÚSCULAS: Normalizamos el texto del Rol para que acepte cualquier variante
    if not df_planilla.empty and 'rol' in df_planilla.columns:
        df_planilla['rol_clean'] = df_planilla['rol'].astype(str).str.strip().str.lower()
        # Captura: 'tractorista', 'Tractorista', 'TRACTORISTA', 'operador' o 'maquinista'
        df_planilla = df_planilla[df_planilla['rol_clean'].isin(['tractorista', 'operador', 'maquinista'])]

    # --- VERIFICACIÓN DE SEGURIDAD ---
    if df_planilla.empty:
        st.warning(f"⏳ Datos detectados en el sistema ({len(df_horas_filtradas)} registros generales), pero ninguno coincide con un empleado que tenga el rol de 'Tractorista' en este rango de fechas.")
        
        # Pestaña de diagnóstico secreta para ti
        with st.expander("🕵️ Spyglass: Ver qué datos crudos están llegando"):
            st.write("Historial crudo en este rango de fechas:")
            st.dataframe(df_horas_filtradas, use_container_width=True)
            st.write("Maestro de personal registrado:")
            st.dataframe(df_personal_raw, use_container_width=True)
    else:
        # Matemáticas de costos
        df_planilla['Total_Pago_Labor'] = df_planilla['Total_Horas'] * df_planilla['Sueldo_Hora']
        
        # KPIs GLOBALES
        total_soles_periodo = df_planilla['Total_Pago_Labor'].sum()
        total_horas_periodo = df_planilla['Total_Horas'].sum()
        operarios_activos = df_planilla['personal_id'].nunique()
        
        m1, m2, m3 = st.columns(3)
        m1.metric("💵 Planilla Tractoristas (Periodo)", f"S/ {total_soles_periodo:,.2f}")
        m2.metric("⏱️ Total Horas Motor Acumuladas", f"{total_horas_periodo:,.1f} hrs")
        m3.metric("🚜 Operadores Liquidados", f"{operarios_activos} Tractoristas")
            
        st.write("---")
        
        # RESUMEN AGRUPADO
        st.subheader("📋 Resumen de Pagos por Trabajador")
        df_resumen_pago = df_planilla.groupby('nombre_completo').agg({
            'Total_Horas': 'sum',
            'Sueldo_Hora': '