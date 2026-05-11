import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Campo y Maquinaria", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; }
    .seccion-titulo { color: #1e3d33; font-weight: 600; margin-top: 15px; margin-bottom: 10px; border-bottom: 2px solid #2ecc71; padding-bottom: 5px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS ---
@st.cache_data(ttl=60)
def cargar_datos_operacion():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        res_o = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Finalizada').execute()
        res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        res_m = supabase.table('Maquinaria').select("id, nombre").execute()
        res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(50).execute()
        return (pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), pd.DataFrame(res_m.data), pd.DataFrame(res_h.data))
    except Exception as e:
        st.error(f"Error en carga: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ord, df_pers, df_maqu, df_hist_h = cargar_datos_operacion()

# --- 4. CABECERA Y MÉTRICAS ---
with stylable_container(key="green_title", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("🚜 Registro de Aplicación Fitosanitaria")
    st.write("Cierre de campo basado en formato físico.")

st.write("")
m1, m2, m3 = st.columns(3)
style_metric_cards(border_left_color="#1e3d33")
m1.metric("Apps Pendientes", len(df_ord))
m2.metric("Maquinaria en Base", len(df_maqu))
horas_hoy = df_hist_h[df_hist_h['Fecha'] == str(date.today())]['Total_Horas'].sum() if not df_hist_h.empty else 0
m3.metric("Horas Tractor (Hoy)", f"{horas_hoy:.1f} hrs")

# --- 5. TAREAS PARA APLICAR ---
st.subheader("✅ Órdenes Listas para Ejecución")

if df_ord.empty:
    st.info("No hay mezclas esperando aplicación. Revisa el módulo de Almacén.")
elif df_pers.empty or df_maqu.empty:
    st.warning("⚠️ Configuración requerida: Registra personal y maquinaria en Supabase.")
else:
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}

    for _, tarea in df_ord.iterrows():
        nombre_objetivo = tarea.get('Objetivo', "General")
        exp_title = f"📦 OT: {tarea['ID_Orden_Personalizado']} | Sector: {tarea.get('Sector_Aplicacion','')} | 🎯 {nombre_objetivo}"
        
        with st.expander(exp_title, expanded=False):
            # Info de la mezcla
            st.info(f"🧪 **Mezcla en Tanque:** {', '.join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])}")

            with st.form(key=f"form_v3_{tarea['id']}"):
                
                # SECCIÓN 1: DATOS GENERALES
                st.markdown('<div class="seccion-titulo">1. Datos Generales y Área</div>', unsafe_allow_html=True)
                ca1, ca2, ca3, ca4 = st.columns(4)
                ha_cubiertas = ca1.number_input("Hectáreas", min_value=0.01, value=1.80)
                turno = ca2.selectbox("Turno", ["Día", "Noche"])
                h_inicio_reloj = ca3.time_input("Hora Inicio")
                h_fin_reloj = ca4.time_input("Hora Final")

                # SECCIÓN 2: MAQUINARIA Y PERSONAL
                st.markdown('<div class="seccion-titulo">2. Maquinaria y Personal</div>', unsafe_allow_html=True)
                cm1, cm2, cm3, cm4 = st.columns(4)
                tract_sel = cm1.selectbox("Tractor Utilizado", options=list(dict_maquina.keys()))
                implemento = cm2.text_input("Pulverizador / Tanque", value="Full Maquinarias")
                op_sel = cm3.selectbox("Operario Maquinaria", options=list(dict_personal.keys()))
                personal_apoyo = cm4.text_input("Personal de Aplicación", placeholder="Ej: Juan, Pedro...")

                # SECCIÓN 3: MÉTODO DE APLICACIÓN Y AGUA
                st.markdown('<div class="seccion-titulo">3. Método de Aplicación y Agua</div>', unsafe_allow_html=True)
                cw1, cw2, cw3, cw4 = st.columns(4)
                tipo_app = cw1.selectbox("Tipo Aplicación", ["Nebulizado (Turbo)", "Pulverizado", "Barras", "Pistolas/Drench", "Mochila Manual"])
                vol_total = cw2.number_input("Vol. Agua Total (Lts)", value=2200)
                vol_ha = cw3.number_input("Vol. Lts/Ha", value=1200)
                ph_agua = cw4.number_input("pH Agua", value=6.0, step=0.1)

                # SECCIÓN 4: CALIBRACIÓN DE TRACTOR
                st.markdown('<div class="seccion-titulo">4. Calibración y Boquillas</div>', unsafe_allow_html=True)
                cb1, cb2, cb3, cb4, cb5 = st.columns(5)
                h_ini = cb1.number_input("Horómetro Inicial", min_value=0.0, format="%.2f")
                h_fin = cb2.number_input("Horómetro Final", min_value=0.0, format="%.2f")
                marcha = cb3.number_input("Marcha (N°)", min_value=1, value=1)
                presion = cb4.number_input("Presión (Bar/Lb)", value=9.0)
                velocidad = cb5.number_input("Velocidad km/h", value=0.0)

                ct1, ct2 = st.columns(2)
                n_boquillas = ct1.number_input("N° Total de Boquillas", value=18)
                color_boquillas = ct2.text_input("Color de Boquillas", value="9 negras, 9 marrones")

                obs = st.text_area("Observaciones Generales", placeholder="Ej: Aplicación con boquillas intercaladas...")

                if st.form_submit_button("🏁 Registrar Aplicación en Campo", type="primary", use_container_width=True):
                    if h_fin <= h_ini and h_fin != 0:
                        st.error("Error: El horómetro final debe ser mayor al inicial.")
                    else:
                        # 📦 EMPAQUETAMOS LOS DATOS FÍSICOS EN TEXTO (Prevención de APIError)
                        reporte_tecnico = f"""
                        [TIPO]: {tipo_app} | [ÁREA]: {ha_cubiertas} Ha | [TURNO]: {turno} ({h_inicio_reloj} - {h_fin_reloj})
                        [AGUA]: Vol Total: {vol_total} L | Vol/Ha: {vol_ha} L | pH: {ph_agua}
                        [CALIBRACIÓN]: Marcha: {marcha} | Velocidad: {velocidad} km/h | Presión: {presion} Bar
                        [BOQUILLAS]: {n_boquillas} totales ({color_boquillas})
                        [EQUIPO]: Tractor: {tract_sel} | Tanque: {implemento} | Apoyo: {personal_apoyo}
                        [NOTAS]: {obs}
                        """

                        try:
                            # 1. Registro de Horas
                            data_horas = {
                                "Fecha": str(date.today()),
                                "Turno": turno,
                                "personal_id": dict_personal[op_sel], 
                                "maquinaria_id": dict_maquina[tract_sel], 
                                "Implemento": implemento,
                                "Labor_Realizada": f"Aplicación {nombre_objetivo}",
                                "Sector": tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": h_ini,
                                "Horometro_Final": h_fin,
                                "Total_Horas": h_fin - h_ini,
                                "Observaciones": reporte_tecnico
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # 2. Actualizar Orden
                            data_update = {
                                "Status": "Aplicada en Campo",
                                "operador_id": dict_personal[op_sel], 
                                "Aplicacion_Completada_Fecha": datetime.now().isoformat(),
                                "Marcha": marcha,
                                "Presion_Bar": int(presion), # Protegido contra decimales
                                "Observaciones_Aplicacion": reporte_tecnico
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_update).eq('id', tarea['id']).execute()

                            st.success("¡Registro de campo guardado exitosamente!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error DB: {e}")

# --- 6. HISTORIAL ---
st.divider()
st.header("📚 Historial de Labores")

if not df_hist_h.empty:
    df_h_view = pd.merge(df_hist_h, df_pers, left_on='personal_id', right_on='id', how='left')
    df_h_view = pd.merge(df_h_view, df_maqu, left_on='maquinaria_id', right_on='id', how='left')
    df_h_view = df_h_view.rename(columns={'nombre_completo': 'Operador', 'nombre': 'Tractor'})
    
    cols_hist = ['Fecha', 'Operador', 'Tractor', 'Labor_Realizada', 'Total_Horas', 'Sector']
    
    gb = GridOptionsBuilder.from_dataframe(df_h_view[cols_hist])
    gb.configure_pagination(paginationPageSize=10)
    for col in cols_hist:
        gb.configure_column(col, minWidth=120)
    
    AgGrid(
        df_h_view[cols_hist],
        gridOptions=gb.build(),
        theme='balham',
        height=350,
        columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE
    )