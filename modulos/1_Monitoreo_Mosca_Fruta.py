import streamlit as st
import pandas as pd
from datetime import datetime, date
from io import BytesIO
from supabase import create_client

# 🚨 CANDADO DE SEGURIDAD (Colocar al inicio de la página, justo debajo de los imports)
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal antes de acceder a este módulo.")
    st.stop() # Frena la ejecución del resto del código de golpe

# --- 1. CONFIGURACIÓN MÓVIL ---
st.set_page_config(page_title="Monitoreo de Mosca", page_icon="🪰", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; font-weight: bold; }
    .sync-box { background-color: #e3f2fd; padding: 15px; border-radius: 10px; border: 1px solid #90caf9; margin-bottom: 20px; }
    /* Ajuste para inputs en móvil */
    .stNumberInput input { font-size: 18px !important; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. MEMORIA LOCAL (COLA OFFLINE) ---
if 'cola_mosca' not in st.session_state:
    st.session_state.cola_mosca = []
if 'sector_fijo' not in st.session_state:
    st.session_state.sector_fijo = ""

# --- 3. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. FUNCIONES ---
def sync_mosca():
    if not st.session_state.cola_mosca:
        st.info("No hay datos pendientes.")
        return

    try:
        with st.spinner("Subiendo datos a la nube..."):
            supabase.table('Monitoreo_Mosca').insert(st.session_state.cola_mosca).execute()
            st.session_state.cola_mosca = []
            st.success("¡Sincronización Exitosa!")
            st.balloons()
            st.cache_data.clear()
    except Exception as e:
        st.error(f"Error de conexión: {e}. Los datos siguen guardados en el celular.")

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Monitoreo_Mosca')
    return output.getvalue()

# --- 5. INTERFAZ PRINCIPAL ---
with st.container():
    st.title("🪰 Monitor de Mosca")
    
    # INDICADOR DE COLA PENDIENTE
    if st.session_state.cola_mosca:
        st.markdown(f"""
            <div class="sync-box">
                🔵 <strong>{len(st.session_state.cola_mosca)} registros listos</strong> para subir.<br>
                Sincroniza cuando tengas internet.
            </div>
            """, unsafe_allow_html=True)
        if st.button("🔄 SUBIR DATOS A SUPABASE"):
            sync_mosca()

# --- FORMULARIO DE REGISTRO RÁPIDO ---
with st.expander("📝 Registro de Trampa", expanded=True):
    # Datos de cabecera (se mantienen fijos por sesión)
    c1, c2 = st.columns(2)
    with c1:
        sectores = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_input = st.selectbox("Sector", sectores, index=0)
    with c2:
        fecha_input = st.date_input("Fecha", value=date.today())

    st.divider()

    with st.form("form_trampa", clear_on_submit=True):
        col_t1, col_t2 = st.columns(2)
        n_trampa = col_t1.text_input("N° Trampa", placeholder="Ej: 101")
        t_trampa = col_t2.selectbox("Tipo", ["Jackson", "McPhail", "Otro"])

        st.markdown("**Capturas Encontradas:**")
        capitata = st.number_input("Ceratitis capitata", min_value=0, step=1, value=0)
        fraterculus = st.number_input("Anastrepha fraterculus", min_value=0, step=1, value=0)
        distinta = st.number_input("Anastrepha distinta", min_value=0, step=1, value=0)

        if st.form_submit_button("➕ AÑADIR A LA LISTA"):
            if not n_trampa:
                st.warning("Debes poner el número de trampa.")
            else:
                nuevo_registro = {
                    "Fecha": str(fecha_input),
                    "Sector": sector_input,
                    "Numero_Trampa": n_trampa,
                    "Tipo_Trampa": t_trampa,
                    "Ceratitis_capitata": int(capitata),
                    "Anastrepha_fraterculus": int(fraterculus),
                    "Anastrepha_distinta": int(distinta)
                }
                st.session_state.cola_mosca.append(nuevo_registro)
                st.toast(f"Trampa {n_trampa} guardada", icon="✅")

# --- 6. VISUALIZACIÓN DE COLA ACTUAL ---
if st.session_state.cola_mosca:
    with st.expander("📋 Ver registros en el teléfono"):
        df_cola = pd.DataFrame(st.session_state.cola_mosca)
        st.dataframe(df_cola[['Numero_Trampa', 'Ceratitis_capitata', 'Anastrepha_fraterculus']], use_container_width=True)
        if st.button("🗑️ Borrar lista local"):
            st.session_state.cola_mosca = []
            st.rerun()

# --- 7. HISTORIAL (NUBE) ---
st.divider()
st.subheader("📚 Historial Sincronizado")
try:
    res = supabase.table('Monitoreo_Mosca').select("*").order('Fecha', desc=True).limit(50).execute()
    df_db = pd.DataFrame(res.data)
except:
    df_db = pd.DataFrame()

if not df_db.empty:
    # Agrupamos por fecha y sector para que el de sanidad vea resúmenes
    df_view = df_db[['Fecha', 'Sector', 'Numero_Trampa', 'Ceratitis_capitata', 'Anastrepha_fraterculus', 'Anastrepha_distinta']]
    st.dataframe(df_view, use_container_width=True, hide_index=True)
    
    excel_file = to_excel(df_db)
    st.download_button(
        label="📥 Descargar Historial Completo (Excel)",
        data=excel_file,
        file_name=f"Monitoreo_Mosca_{date.today()}.xlsx",
        mime="application/vnd.ms-excel"
    )
else:
    st.info("No hay datos históricos sincronizados.")