import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
from io import BytesIO

# --- 1. CANDADO DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal para acceder.")
    st.stop()

# ✅ FIX: usar .get() para evitar KeyError si el rol desaparece por caché
if st.session_state.get("rol", "") not in ["Admin", "Programador", "Costos"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para la Gerencia y Administración.")
    st.stop()

# --- 2. CONFIGURACIÓN ---
st.set_page_config(page_title="Módulo Financiero - Project Uva", page_icon="💰", layout="wide")

# --- 3. CONEXIÓN A SUPABASE ---
from supabase import create_client

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. CARGA DE DATA ---
@st.cache_data(ttl=60)
def cargar_data_financiera():
    try:
        res_horas    = supabase.table('Registro_Horas_Tractor').select("*").execute()
        res_personal = supabase.table('Personal').select("id, nombre_completo, rol, Sueldo_Hora, activo").execute()
        return pd.DataFrame(res_horas.data), pd.DataFrame(res_personal.data)
    except Exception as e:
        st.error(f"❌ Error crítico en servidor: {e}")
        return pd.DataFrame(), pd.DataFrame()

def to_excel_finanzas(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Planilla')
    return output.getvalue()

df_horas_raw, df_personal_raw = cargar_data_financiera()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💰 Centro de Control Financiero y Planillas")
st.write("Auditoría en tiempo real de mano de obra y costos operativos de maquinaria.")
st.divider()

# CONTROLES SIDEBAR
st.sidebar.header("⚙️ Controles de Datos")
if st.sidebar.button("🔄 Forzar Actualización"):
    cargar_data_financiera.clear()
    st.rerun()

if df_horas_raw.empty:
    st.info("📊 La tabla 'Registro_Horas_Tractor' está vacía. Esperando primer registro del campo.")
    st.stop()
elif df_personal_raw.empty:
    st.error("⚠️ No se encontraron empleados en 'Personal'. Registra al menos un trabajador con sueldo.")
    st.stop()

# --- FILTROS TEMPORALES ---
st.sidebar.write("---")
st.sidebar.header("🗓️ Periodo de Liquidación")
f_inicio = st.sidebar.date_input("Fecha Inicio", value=date.today() - timedelta(days=30))
f_fin    = st.sidebar.date_input("Fecha Fin",    value=date.today() + timedelta(days=1))

# ✅ FIX: NaT-safe date conversion
df_horas_raw['Fecha'] = pd.to_datetime(df_horas_raw['Fecha'], errors='coerce')
df_horas_raw = df_horas_raw.dropna(subset=['Fecha'])
df_horas_raw['Fecha_date'] = df_horas_raw['Fecha'].dt.date
df_horas_filtradas = df_horas_raw[
    (df_horas_raw['Fecha_date'] >= f_inicio) & (df_horas_raw['Fecha_date'] <= f_fin)
]

# Cruce relacional
df_planilla = pd.merge(
    df_horas_filtradas,
    df_personal_raw[['id', 'nombre_completo', 'rol', 'Sueldo_Hora']],
    left_on='personal_id', right_on='id', how='left'
)

# Filtrar solo tractoristas/operadores
if not df_planilla.empty and 'rol' in df_planilla.columns:
    df_planilla['rol_clean'] = df_planilla['rol'].astype(str).str.strip().str.lower()
    df_planilla = df_planilla[df_planilla['rol_clean'].isin(['tractorista', 'operador', 'maquinista'])]

if df_planilla.empty:
    st.warning("⏳ No se encontraron aplicaciones de tractoristas en este rango de fechas.")
    with st.expander("🕵️ Spyglass: Ver datos crudos"):
        st.dataframe(df_horas_filtradas, use_container_width=True)
        st.dataframe(df_personal_raw, use_container_width=True)
    st.stop()

# ✅ FIX CRÍTICO: Rellenar NaN ANTES de hacer matemáticas
# Si un tractorista no tiene sueldo configurado, ponemos 0 y mostramos alerta
sin_sueldo = df_planilla[df_planilla['Sueldo_Hora'].isna()]['nombre_completo'].dropna().unique()
if len(sin_sueldo) > 0:
    st.warning(f"⚠️ Los siguientes operadores no tienen tarifa horaria configurada: **{', '.join(sin_sueldo)}**. Sus horas se cuentan pero su costo aparece como S/ 0. Configura su sueldo en la tabla Personal.")

df_planilla['Sueldo_Hora']  = pd.to_numeric(df_planilla['Sueldo_Hora'],  errors='coerce').fillna(0)
df_planilla['Total_Horas']  = pd.to_numeric(df_planilla['Total_Horas'],  errors='coerce').fillna(0)
df_planilla['Total_Pago_Labor'] = df_planilla['Total_Horas'] * df_planilla['Sueldo_Hora']

# --- KPIs GLOBALES ---
total_soles_periodo = df_planilla['Total_Pago_Labor'].sum()
total_horas_periodo = df_planilla['Total_Horas'].sum()
operarios_activos   = df_planilla['personal_id'].nunique()
costo_por_hora_prom = total_soles_periodo / total_horas_periodo if total_horas_periodo > 0 else 0

m1, m2, m3, m4 = st.columns(4)
m1.metric("💵 Planilla Periodo",        f"S/ {total_soles_periodo:,.2f}")
m2.metric("⏱️ Total Horas Motor",       f"{total_horas_periodo:,.1f} hrs")
m3.metric("🚜 Operadores Liquidados",   f"{operarios_activos}")
m4.metric("📊 Costo Promedio/Hora",     f"S/ {costo_por_hora_prom:,.2f}")

st.divider()

# --- 📊 GRÁFICOS ---
cg1, cg2 = st.columns(2)

with cg1:
    st.subheader("📅 Tendencia de Costos Diarios")
    df_trend = df_planilla.groupby('Fecha_date')['Total_Pago_Labor'].sum().reset_index()
    df_trend.columns = ['Fecha', 'Costo_S']
    fig_trend = px.bar(
        df_trend, x='Fecha', y='Costo_S',
        labels={'Costo_S': 'Costo (S/)', 'Fecha': 'Fecha'},
        color_discrete_sequence=['#27ae60']
    )
    fig_trend.update_layout(height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig_trend, use_container_width=True)

with cg2:
    st.subheader("🏆 Ranking de Costo por Operador")
    df_rank = df_planilla.groupby('nombre_completo')['Total_Pago_Labor'].sum().sort_values(ascending=True).reset_index()
    fig_rank = px.bar(
        df_rank, x='Total_Pago_Labor', y='nombre_completo', orientation='h',
        labels={'Total_Pago_Labor': 'Costo Total (S/)', 'nombre_completo': ''},
        text=df_rank['Total_Pago_Labor'].apply(lambda x: f"S/ {x:,.2f}"),
        color_discrete_sequence=['#2980b9']
    )
    fig_rank.update_layout(height=320, margin=dict(t=10, b=10))
    st.plotly_chart(fig_rank, use_container_width=True)

st.divider()

# --- ✅ NUEVO: COSTO POR HECTÁREA ---
st.subheader("🌱 Costo de Maquinaria por Hectárea (por Sector)")

# Áreas reales del fundo (en hectáreas) — ajustar según mediciones reales
AREAS_SECTOR = {
    'J1': 1.8, 'J2': 1.8, 'R1': 1.5, 'R2': 1.5,
    'W1': 2.0, 'W2': 2.0, 'W3': 2.0,
    'K1': 1.5, 'K2': 1.5, 'K3': 1.5
}

if 'Sector' in df_planilla.columns:
    df_costo_sector = df_planilla.groupby('Sector').agg(
        Costo_Total   =('Total_Pago_Labor', 'sum'),
        Horas_Total   =('Total_Horas',      'sum'),
        Jornadas      =('Fecha_date',       'nunique'),
    ).reset_index()
    
    df_costo_sector['Hectareas'] = df_costo_sector['Sector'].map(AREAS_SECTOR).fillna(1.5)
    df_costo_sector['Costo_por_Ha'] = (df_costo_sector['Costo_Total'] / df_costo_sector['Hectareas']).round(2)
    df_costo_sector['Horas_por_Ha']  = (df_costo_sector['Horas_Total'] / df_costo_sector['Hectareas']).round(2)
    
    cha1, cha2 = st.columns(2)
    with cha1:
        fig_cpha = px.bar(
            df_costo_sector.sort_values('Costo_por_Ha', ascending=True),
            x='Costo_por_Ha', y='Sector', orientation='h',
            text=df_costo_sector.sort_values('Costo_por_Ha', ascending=True)['Costo_por_Ha'].apply(lambda x: f"S/ {x:,.2f}"),
            color='Costo_por_Ha', color_continuous_scale='RdYlGn_r',
            title="Costo Maquinaria por Ha (S/)"
        )
        fig_cpha.update_layout(height=320, showlegend=False)
        st.plotly_chart(fig_cpha, use_container_width=True)
    
    with cha2:
        # ✅ NUEVO: Desglose por tipo de labor
        if 'Labor_Realizada' in df_planilla.columns:
            st.subheader("🎯 Desglose por Labor")
            df_labor = df_planilla.groupby('Labor_Realizada')['Total_Pago_Labor'].sum().reset_index()
            df_labor.columns = ['Labor', 'Costo_S']
            fig_labor = px.pie(
                df_labor, values='Costo_S', names='Labor',
                title="¿En qué se gasta el dinero?", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Prism
            )
            fig_labor.update_layout(height=320)
            st.plotly_chart(fig_labor, use_container_width=True)
    
    # Tabla resumen Costo/Ha
    with st.expander("📋 Ver tabla detallada Costo por Hectárea"):
        df_costo_show = df_costo_sector[['Sector', 'Hectareas', 'Jornadas', 'Horas_Total', 'Costo_Total', 'Costo_por_Ha', 'Horas_por_Ha']].copy()
        df_costo_show.columns = ['📍 Sector', '📐 Ha', '📅 Jornadas', '⏱️ Horas', '💵 Costo Total', '💰 S/Ha', '⏱️ Hrs/Ha']
        st.dataframe(df_costo_show, use_container_width=True, hide_index=True,
                     column_config={
                         "💵 Costo Total": st.column_config.NumberColumn(format="S/ %.2f"),
                         "💰 S/Ha":        st.column_config.NumberColumn(format="S/ %.2f"),
                     })

    # ✅ NUEVO: Alerta de desvío semanal
    st.divider()
    dias_periodo = (f_fin - f_inicio).days
    if dias_periodo >= 14 and len(df_trend) >= 7:
        mitad = len(df_trend) // 2
        costo_primera_mitad = df_trend.iloc[:mitad]['Costo_S'].sum()
        costo_segunda_mitad = df_trend.iloc[mitad:]['Costo_S'].sum()
        if costo_primera_mitad > 0:
            variacion = ((costo_segunda_mitad - costo_primera_mitad) / costo_primera_mitad) * 100
            if variacion > 20:
                st.warning(f"🔺 **Alerta de Gasto:** El costo de la segunda mitad del periodo es un **{variacion:.0f}% mayor** que la primera mitad. Verificar si hay horas extras o labores no planificadas.")
            elif variacion < -20:
                st.success(f"🔽 **Ahorro Detectado:** El costo bajó un **{abs(variacion):.0f}%** en la segunda mitad del periodo. ¡Buena eficiencia!")

st.divider()

# --- RESUMEN AGRUPADO ---
st.subheader("📋 Resumen de Pagos por Trabajador")
df_resumen = df_planilla.groupby('nombre_completo').agg(
    Horas_Totales    =('Total_Horas',      'sum'),
    Tarifa_Hora      =('Sueldo_Hora',      'first'),
    Total_a_Pagar    =('Total_Pago_Labor', 'sum')
).reset_index()
df_resumen.columns = ['👤 Nombre del Operador', '⏱️ Horas Totales', '🏷️ Tarifa/Hora', '💰 Total a Pagar']

st.dataframe(
    df_resumen,
    use_container_width=True,
    hide_index=True,
    column_config={
        "💰 Total a Pagar": st.column_config.NumberColumn(format="S/ %.2f"),
        "🏷️ Tarifa/Hora":  st.column_config.NumberColumn(format="S/ %.2f"),
    }
)

# Descarga Excel
excel_data = to_excel_finanzas(df_resumen)
st.download_button(
    label="📥 Descargar Planilla (Excel)",
    data=excel_data,
    file_name=f"Planilla_{f_inicio.strftime('%Y%m%d')}_al_{f_fin.strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.ms-excel"
)

st.divider()

# --- TRAZABILIDAD DETALLADA ---
st.subheader("🔍 Desglose de Jornadas y Sectores")
cols_audit = ['Fecha_date', 'nombre_completo', 'Sector', 'Labor_Realizada', 'Implemento', 'Total_Horas', 'Total_Pago_Labor']
cols_audit = [c for c in cols_audit if c in df_planilla.columns]
df_auditoria = df_planilla[cols_audit].copy().sort_values('Fecha_date', ascending=False)
df_auditoria.rename(columns={
    'Fecha_date': '📅 Fecha', 'nombre_completo': '👤 Operador',
    'Sector': '📍 Sector', 'Labor_Realizada': '🎯 Labor',
    'Implemento': '🛠️ Implemento', 'Total_Horas': '⏱️ Horas',
    'Total_Pago_Labor': '💵 Costo Labor'
}, inplace=True)
st.dataframe(df_auditoria, use_container_width=True, hide_index=True,
             column_config={"💵 Costo Labor": st.column_config.NumberColumn(format="S/ %.2f")})