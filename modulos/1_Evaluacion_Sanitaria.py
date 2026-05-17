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
st.set_page_config(page_title="Evaluación Sanitaria", page_icon="🔬", layout="wide")

# CSS para móvil: Botones grandes y fondo que no cansa
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3em; font-weight: bold; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    .sync-box { background-color: #fff3cd; padding: 15px; border-radius: 10px; border: 1px solid #ffeeba; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. INICIALIZACIÓN DE MEMORIA LOCAL (COLA OFFLINE) ---
if 'cola_sincronizacion' not in st.session_state:
    st.session_state.cola_sincronizacion = []

# --- 3. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. FUNCIONES DE APOYO ---
def sync_ahora():
    """Sube los datos de la cola local a Supabase."""
    if not st.session_state.cola_sincronizacion:
        st.info("No hay datos pendientes de sincronizar.")
        return

    exitos = 0
    try:
        for evaluacion in st.session_state.cola_sincronizacion:
            supabase.table('Evaluaciones_Sanitarias').insert(evaluacion).execute()
            exitos += 1
        
        st.session_state.cola_sincronizacion = [] # Limpiar cola
        st.success(f"¡Éxito! {exitos} evaluaciones subidas a la nube.")
        st.balloons()
    except Exception as e:
        st.error(f"Error al sincronizar: {e}. Intente cuando tenga mejor señal.")

def to_excel_detailed(evaluacion_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Resumen
        resumen = pd.DataFrame([{
            "Fecha": evaluacion_row['Fecha'],
            "Sector": evaluacion_row['Sector'],
            "Evaluador": evaluacion_row['Evaluador']
        }])
        resumen.to_excel(writer, index=False, sheet_name='Resumen')
        
        # Datos JSONB
        for sheet, key in [('Plagas', 'Datos_Plagas'), ('Enfermedades', 'Datos_Enfermedades'), ('Lindero', 'Datos_Perimetro')]:
            if key in evaluacion_row and evaluacion_row[key]:
                pd.DataFrame(evaluacion_row[key]).to_excel(writer, index=False, sheet_name=sheet)
    return output.getvalue()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("🔬 Monitor Sanitario Móvil")

# --- BLOQUE DE SINCRONIZACIÓN (SOLO APARECE SI HAY PENDIENTES) ---
if st.session_state.cola_sincronizacion:
    with st.container():
        st.markdown(f"""
            <div class="sync-box">
                <strong>⚠️ Tienes {len(st.session_state.cola_sincronizacion)} evaluaciones guardadas en el teléfono.</strong><br>
                Presiona el botón de abajo cuando tengas internet para subirlas.
            </div>
            """, unsafe_allow_html=True)
        if st.button("🔄 SINCRONIZAR AHORA CON LA NUBE", type="primary"):
            sync_ahora()

# --- FORMULARIO DE REGISTRO ---
with st.expander("📝 Nueva Evaluación de Campo", expanded=True):
    with st.form("form_sanidad", clear_on_submit=True):
        c1, c2 = st.columns(2)
        fecha = c1.date_input("Fecha", value=date.today())
        sector = c2.selectbox("Sector", ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3'])
        evaluador = st.text_input("Evaluador (Nombre)")

        st.divider()
        
        tab_p, tab_e, tab_l = st.tabs(["🪲 PLAGAS", "🍄 ENFERMEDADES", "🚧 LINDERO"])

        with tab_p:
            # Plantilla simplificada para carga rápida en móvil
            plagas_df = pd.DataFrame({
                'Planta': [f"P.{i+1}" for i in range(25)],
                'TRIPS': [0]*25, 'M.BLANCA': [0.0]*25, 'A.ROJA': [0.0]*25, 'COCHINILLA': [0.0]*25
            }).set_index('Planta')
            df_plagas_input = st.data_editor(plagas_df, use_container_width=True, key="ed_p")

        with tab_e:
            enferm_df = pd.DataFrame({
                'Planta': [f"P.{i+1}" for i in range(25)],
                'OIDIO %': [0.0]*25, 'MILDIU %': [0.0]*25, 'BOTRYTIS': [0.0]*25
            }).set_index('Planta')
            df_enferm_input = st.data_editor(enferm_df, use_container_width=True, key="ed_e")

        with tab_l:
            lindero_df = pd.DataFrame({
                'Problema': ['OIDIUM', 'MILDIU', 'ARAÑITA', 'COCHINILLA'],
                'P1_HOJA': [0.0]*4, 'P1_RAC': [0.0]*4, 'P2_HOJA': [0.0]*4, 'P2_RAC': [0.0]*4
            }).set_index('Problema')
            df_lindero_input = st.data_editor(lindero_df, use_container_width=True, key="ed_l")

        if st.form_submit_button("💾 GUARDAR EN EL TELÉFONO"):
            if not evaluador:
                st.warning("Escribe tu nombre antes de guardar.")
            else:
                nueva_eval = {
                    "Fecha": str(fecha),
                    "Sector": sector,
                    "Evaluador": evaluador,
                    "Datos_Plagas": df_plagas_input.reset_index().to_dict(orient='records'),
                    "Datos_Enfermedades": df_enferm_input.reset_index().to_dict(orient='records'),
                    "Datos_Perimetro": df_lindero_input.reset_index().to_dict(orient='records')
                }
                st.session_state.cola_sincronizacion.append(nueva_eval)
                st.success(f"✅ Evaluación de {sector} guardada localmente. ¡Sigue con el siguiente lote!")
                # Nota: st.rerun() no es necesario aquí porque el st.form(clear_on_submit=True) limpia los campos

# --- 6. HISTORIAL (PARA EL JEFE DE SANIDAD) ---
st.divider()
st.subheader("📚 Historial en la Nube")
try:
    res = supabase.table('Evaluaciones_Sanitarias').select("*").order('Fecha', desc=True).limit(20).execute()
    df_historial = pd.DataFrame(res.data)
except:
    df_historial = pd.DataFrame()

if not df_historial.empty:
    for _, fila in df_historial.iterrows():
        with st.container(border=True):
            col_a, col_b, col_c = st.columns([3, 3, 2])
            col_a.write(f"📅 **{fila['Fecha']}**")
            col_b.write(f"📍 Sector: **{fila['Sector']}**")
            
            excel_data = to_excel_detailed(fila)
            col_c.download_button(
                label="📥 Excel",
                data=excel_data,
                file_name=f"Sanidad_{fila['Sector']}_{fila['Fecha']}.xlsx",
                mime="application/vnd.ms-excel",
                key=f"dl_{fila['id']}"
            )
else:
    st.info("No hay datos en la nube. Sincroniza las evaluaciones pendientes.")