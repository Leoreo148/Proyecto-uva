import streamlit as st
import pandas as pd
from datetime import datetime, date

# 🚨 1.CANDADO DE SEGURIDAD (Colocar al inicio de la página, justo debajo de los imports)
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal antes de acceder a este módulo.")
    st.stop() # Frena la ejecución del resto del código de golpe


# Ajusta los roles que tienen permiso de registrar la uva que entra (Admin, Campo, Logística)
if st.session_state["rol"] not in ["Admin", "Programador", "Logistica", "Campo"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para el área de Operaciones y Jefes de Cuadrilla.")
    st.stop()

# --- 2. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Control de Cosecha y Rendimiento - Project Uva", page_icon="🍇", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #fcfcfc; }
    .seccion-titulo { color: #1e3d33; font-weight: 600; margin-top: 15px; border-bottom: 2px solid #9b59b6; padding-bottom: 5px;}
    </style>
    """, unsafe_allow_html=True)

# --- 3. CONEXIÓN A SUPABASE ---
from supabase import create_client
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. CARGA DE CATÁLOGOS (Personal para Jefes de Cuadrilla) ---
@st.cache_data(ttl=60)
def cargar_personal_cosecha():
    try:
        res = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        return pd.DataFrame(res.data)
    except Exception as e:
        st.error(f"❌ Error al cargar catálogo de personal: {e}")
        return pd.DataFrame()

df_pers = cargar_personal_cosecha()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("🍇 Control de Cosecha y Rendimiento de Fruta")
st.write("Registro técnico de ingresos de uva al centro de acopio y control de calidad de exportación.")
st.divider()

# Creamos dos pestañas: una para registrar y otra para auditoría
tab_reg, tab_hist = st.tabs(["📝 Registrar Ingreso de Fruta", "📊 Historial y Rendimiento"])

# ==========================================
# PESTAÑA 1: FORMULARIO DE REGISTRO
# ==========================================
with tab_reg:
    with st.form("form_registro_cosecha", clear_on_submit=True):
        st.markdown('<div class="seccion-titulo">1. Origen y Responsable</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        
        f_cosecha = c1.date_input("Fecha de Cosecha", value=date.today())
        
        # Lista oficial de sectores incluyendo explícitamente el W3
        SECTORES_UVA = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2', 'K3']
        sec_origen = c2.selectbox("Sector / Lote de Origen", options=SECTORES_UVA)
        
        # Mapeo de personal para el combo box
        if not df_pers.empty:
            dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
            resp_cuadrilla = c3.selectbox("Responsable de Cuadrilla / Pesaje", options=list(dict_personal.keys()))
        else:
            dict_personal = {}
            resp_cuadrilla = c3.selectbox("Responsable de Cuadrilla / Pesaje", options=["Sin personal activo"])

        st.markdown('<div class="seccion-titulo">2. Control de Pesaje y Calidad</div>', unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        
        # Variedad unificada por defecto
        variedad_uva = c4.text_input("Variedad Biológica", value="ARRA 34", disabled=True)
        javas = c5.number_input("Cantidad de Javas Ingresadas", min_value=1, value=50, step=1)
        
        st.markdown("### ⚖️ Desglose de Kilos Netos")
        ck1, ck2 = st.columns(2)
        kg_export = ck1.number_input("Kilos de Calidad Exportación Premium (Kg)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        kg_local = ck2.number_input("Kilos de Descarte / Mercado Local (Kg)", min_value=0.0, value=0.0, step=0.5, format="%.2f")
        
        st.write("---")
        obs_cosecha = st.text_area("📝 Observaciones del lote (Opcional)", placeholder="Ej: Fruta con excelente calibre. / Ligero descarte por racimos sueltos.")
        
        # Botón de envío
        if st.form_submit_button("📡 Grabar Ingreso de Cosecha en Supabase", type="primary"):
            if kg_export == 0 and kg_local == 0:
                st.error("❌ Debes ingresar el peso de al menos una de las dos calidades (Exportación o Local).")
            elif not dict_personal:
                st.error("❌ No se puede registrar sin un responsable de cuadrilla válido.")
            else:
                # Empaquetamos la data para Supabase
                cosecha_data = {
                    "Fecha": str(f_cosecha),
                    "Sector": sec_origen,
                    "Variedad": "ARRA 34", # Forzamos consistencia genética
                    "Cantidad_Javas": int(javas),
                    "Kilos_Exportacion_Premium": float(kg_export),
                    "Kilos_Descarte_Local": float(kg_local),
                    "Responsable_Cuadrilla_id": int(dict_personal[resp_cuadrilla]),
                    "Observaciones": obs_cosecha
                }
                
                try:
                    supabase.table('Registro_Cosecha').insert(cosecha_data).execute()
                    st.success(f"✅ ¡Éxito! Lote del sector {sec_origen} guardado. Servidor calculó automáticamente el peso total.")
                    st.cache_data.clear() # Limpiamos caché para actualizar el historial al instante
                except Exception as e:
                    st.error(f"❌ Error al guardar en el servidor: {e}")

# ==========================================
# PESTAÑA 2: HISTORIAL Y AUDITORÍA DE CALIDAD
# ==========================================
with tab_hist:
    st.subheader("📚 Trazabilidad de Producción por Sectores")
    
    try:
        # Jalamos el historial crudo directamente de Supabase
        res_h = supabase.table('Registro_Cosecha').select("*").order('Fecha', desc=True).execute()
        df_cosecha_raw = pd.DataFrame(res_h.data)
        
        if df_cosecha_raw.empty:
            st.info("📊 El almacén de acopio está vacío. Esperando los primeros ingresos de fruta de la campaña.")
        else:
            # Cruzamos con personal para tener el nombre del encargado
            if not df_pers.empty:
                df_view = pd.merge(df_cosecha_raw, df_pers, left_on='Responsable_Cuadrilla_id', right_on='id', how='left')
            else:
                df_view = df_cosecha_raw.copy()
                df_view['nombre_completo'] = "N/A"
            
            # Limpiamos y reordenamos las columnas para la vista del usuario
            df_view = df_view[['Fecha', 'Sector', 'Cantidad_Javas', 'Kilos_Exportacion_Premium', 'Kilos_Descarte_Local', 'Kilos_Totales_Sectores', 'nombre_completo', 'Observaciones']].copy()
            df_view.columns = ['📅 Fecha', '📍 Sector', '📦 Javas', '🛫 Kg Exportación', '🏪 Kg Local', '⚖️ Total Kilos', '👤 Responsable', '📝 Detalles']
            
            # KPIs rápidos en la parte superior
            k1, k2, k3 = st.columns(3)
            k1.metric("🍇 Total Kilos Cosechados", f"{df_view['⚖️ Total Kilos'].sum():,.1f} Kg")
            
            kg_exp_tot = df_view['🛫 Kg Exportación'].sum()
            kg_global = df_view['⚖️ Total Kilos'].sum()
            porcentaje_exp = (kg_exp_tot / kg_global * 100) if kg_global > 0 else 0
            
            k2.metric("🛫 Eficiencia de Exportación", f"{porcentaje_exp:.1f} %")
            k3.metric("📦 Total Javas Movilizadas", f"{df_view['📦 Javas'].sum():,}")
            
            st.divider()
            
            # Mostramos la tabla formateada como de contabilidad técnica
            st.dataframe(
                df_view.style.format({
                    '📦 Javas': '{:,}',
                    '🛫 Kg Exportación': '{:,.1f} Kg',
                    '🏪 Kg Local': '{:,.1f} Kg',
                    '⚖️ Total Kilos': '{:,.1f} Kg'
                }),
                use_container_width=True,
                hide_index=True
            )
            
            # Botón para descargar reporte para el directorio o packing
            csv_cosecha = df_view.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📥 Descargar Reporte de Cosecha (CSV)",
                data=csv_cosecha,
                file_name=f"Reporte_Cosecha_Rendimiento_{date.today()}.csv",
                mime="text/csv"
            )
            
    except Exception as e:
        st.error(f"Error al procesar el historial de producción: {e}")