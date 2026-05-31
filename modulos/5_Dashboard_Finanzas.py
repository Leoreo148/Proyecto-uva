import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# --- 1. CANDADO DE SEGURIDAD ---
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal para acceder.")
    st.stop()

# Bloqueo de seguridad: Solo entra Admin, Programador o el área de Costos/Finanzas
if st.session_state["rol"] not in ["Admin", "Programador", "Costos"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para la Gerencia y Administración.")
    st.stop()

# --- 2. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Módulo Financiero y Planillas - Project Uva", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    .card-kpi { background-color: #ffffff; padding: 20px; border-radius: 10px; border: 1px solid #eaeaea; box-shadow: 0 4px 6px rgba(0,0,0,0.02); }
    .titulo-finanzas { color: #112a20; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONEXIÓN A SUPABASE ---
from supabase import create_client
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. CARGA DE DATA RELACIONAL (Planilla y Horas) ---
@st.cache_data(ttl=30) # Cache de 30 segundos para auditorías rápidas
def cargar_data_financiera():
    try:
        # Jalamos las horas registradas en campo y el maestro de personal
        res_horas = supabase.table('Registro_Horas_Tractor').select("*").execute()
        res_personal = supabase.table('Personal').select("id, nombre_completo, rol, Sueldo_Hora, activo").execute()
        return pd.DataFrame(res_horas.data), pd.DataFrame(res_personal.data)
    except Exception as e:
        st.error(f"❌ Error al conectar con el servidor financiero: {e}")
        return pd.DataFrame(), pd.DataFrame()

df_horas_raw, df_personal_raw = cargar_data_financiera()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💰 Centro de Control Financiero y Planillas")
st.write("Auditoría en tiempo real de mano de obra y costos operativos de maquinaria.")
st.divider()

if df_horas_raw.empty or df_personal_raw.empty:
    st.info("📊 Esperando datos históricos de tareo o personal para inicializar los libros contables.")
else:
    # --- FILTROS TEMPORALES (Control de Quincenas/Meses) ---
    st.sidebar.header("🗓️ Periodo de Liquidación")
    
    # Atajo rápido para el rango de fechas (Por defecto los últimos 15 días)
    fecha_fin_def = date.today()
    fecha_ini_def = fecha_fin_def - timedelta(days=15)
    
    f_inicio = st.sidebar.date_input("Fecha Inicio", value=fecha_ini_def)
    f_fin = st.sidebar.date_input("Fecha Fin", value=fecha_fin_def)
    
    if f_inicio > f_fin:
        st.sidebar.error("❌ La fecha de inicio no puede ser mayor a la de fin.")
    else:
        # Convertimos la columna de fecha a formato datetime de pandas para poder filtrar
        df_horas_raw['Fecha'] = pd.to_datetime(df_horas_raw['Fecha']).dt.date
        
        # Filtrado estricto por rango de fechas
        df_horas_filtradas = df_horas_raw[
            (df_horas_raw['Fecha'] >= f_inicio) & 
            (df_horas_raw['Fecha'] <= f_fin)
        ]
        
        # --- PROCESAMIENTO MATEMÁTICO (El Cruce Relacional) ---
        # Cruzamos las horas con el maestro de personal para obtener el Sueldo_Hora real
        df_planilla = pd.merge(
            df_horas_filtradas, 
            df_personal_raw[['id', 'nombre_completo', 'rol', 'Sueldo_Hora']], 
            left_on='personal_id', 
            right_on='id', 
            how='left'
        )
        
        # 💡 SOLO TRACTORISTAS POR AHORA (Atendiendo a tu orden)
        df_planilla = df_planilla[df_planilla['rol'] == 'Tractorista']
        
        if df_planilla.empty:
            st.warning(f"⏳ No se encontraron aplicaciones de tractoristas registradas entre el {f_inicio.strftime('%d/%m/%Y')} y el {f_fin.strftime('%d/%m/%Y')}.")
        else:
            # Cálculo de la inversión individual por cada tareo/fila
            df_planilla['Total_Pago_Labor'] = df_planilla['Total_Horas'] * df_planilla['Sueldo_Hora']
            
            # --- SECCIÓN 1: KPIs GLOBALES ---
            total_soles_periodo = df_planilla['Total_Pago_Labor'].sum()
            total_horas_periodo = df_planilla['Total_Horas'].sum()
            operarios_activos = df_planilla['personal_id'].nunique()
            
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("💵 Planilla Tractoristas (Periodo)", f"S/ {total_soles_periodo:,.2f}")
            with m2:
                st.metric("⏱️ Total Horas Motor Acumuladas", f"{total_horas_periodo:,.1f} hrs")
            with m3:
                st.metric("🚜 Operadores Liquidados", f"{operarios_activos} Tractoristas")
                
            st.write("---")
            
            # --- SECCIÓN 2: LIQUIDACIÓN AGRUPADA (La Planilla de César) ---
            st.subheader("📋 Resumen de Pagos por Trabajador")
            
            # Agrupamos por operador para consolidar la quincena/mes
            df_resumen_pago = df_planilla.groupby('nombre_completo').agg({
                'Total_Horas': 'sum',
                'Sueldo_Hora': 'first', # Jalamos su tarifa base
                'Total_Pago_Labor': 'sum'
            }).reset_index()
            
            df_resumen_pago.columns = ['👤 Nombre del Operador', '⏱️ Horas Totales', '🏷️ Tarifa por Hora', '💰 Total Neto a Pagar']
            
            # Formateamos visualmente la tabla para que parezca de contabilidad profesional
            st.dataframe(
                df_resumen_pago.style.format({
                    '⏱️ Horas Totales': '{:.1f} hrs',
                    '🏷️ Tarifa por Hora': 'S/ {:.2f}',
                    '💰 Total Neto a Pagar': 'S/ {:,.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # --- SECCIÓN 3: DETALLE HISTÓRICO (Trazabilidad para Auditoría) ---
            st.divider()
            st.subheader("🔍 Desglose de Jornadas y Sectores")
            
            # Seleccionamos las columnas que le importan al administrador para auditar por qué salió ese monto
            df_auditoria = df_planilla[['Fecha', 'nombre_completo', 'Sector', 'Labor_Realizada', 'Implemento', 'Total_Horas', 'Total_Pago_Labor']].copy()
            df_auditoria = df_auditoria.sort_values(by='Fecha', ascending=False)
            df_auditoria.columns = ['📅 Fecha', '👤 Operador', '📍 Sector', '🎯 Labor Realizada', '🛠️ Implemento', '⏱️ Horas', '💵 Costo Labor']
            
            st.dataframe(
                df_auditoria.style.format({
                    '⏱️ Horas': '{:.1f}',
                    '💵 Costo Labor': 'S/ {:.2f}'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # --- BOTÓN DE EXPORTACIÓN DIRECTA ---
            csv_data = df_resumen_pago.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Exportar Planilla del Periodo (CSV)",
                data=csv_data,
                file_name=f"Planilla_Tractoristas_{f_inicio}_al_{f_fin}.csv",
                mime="text/csv"
            )