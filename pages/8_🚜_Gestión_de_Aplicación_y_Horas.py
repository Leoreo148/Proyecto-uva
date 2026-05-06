import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode, GridUpdateMode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Campo y Maquinaria", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
    }
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
        # 1. Órdenes despachadas (Status = Finalizada en Almacén)
        res_o = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Finalizada').execute()
        # 2. Personal Activo
        res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        # 3. Maquinaria
        res_m = supabase.table('Maquinaria').select("id, nombre").execute()
        # 4. Historial (Últimas 50 horas)
        res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(50).execute()

        return (pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), 
                pd.DataFrame(res_m.data), pd.DataFrame(res_h.data))
    except Exception as e:
        st.error(f"Error en carga: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ord, df_pers, df_maqu, df_hist_h = cargar_datos_operacion()

# --- 4. CABECERA Y MÉTRICAS ---
with stylable_container(key="green_title", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("🚜 Control de Aplicación y Horas Tractor")
    st.write("Cierre de órdenes de trabajo y registro de rendimientos de maquinaria.")

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
            c_info1, c_info2 = st.columns([1, 2])
            with c_info1:
                st.info(f"🧪 **Tanque:** {len(tarea.get('Receta_Mezcla_Lotes', []))} insumos.")
            with c_info2:
                # Mostrar brevemente qué hay en la receta
                receta_txt = ", ".join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])
                st.caption(f"Detalle: {receta_txt}")

            with st.form(key=f"form_v2_{tarea['id']}"):
                st.markdown("##### 🚜 Operación y Maquinaria")
                col1, col2, col3 = st.columns(3)
                op_sel = col1.selectbox("Operador", options=list(dict_personal.keys()))
                tract_sel = col2.selectbox("Tractor / Equipo", options=list(dict_maquina.keys()))
                implemento = col3.text_input("Implemento", value="Nebulizadora")

                st.markdown("##### ⚙️ Horómetro y Calibración")
                c_h1, c_h2, c_h3, c_h4 = st.columns(4)
                h_ini = c_h1.number_input("Horo. Inicial", min_value=0.0, format="%.2f", key=f"hi_{tarea['id']}")
                h_fin = c_h2.number_input("Horo. Final", min_value=0.0, format="%.2f", key=f"hf_{tarea['id']}")
                marcha = c_h3.number_input("Marcha", value=2)
                presion = c_h4.number_input("Presión (Bar)", value=15.0)

                obs = st.text_area("Notas de Campo", placeholder="Viento fuerte, fallas, etc.")

                if st.form_submit_button("🏁 Registrar y Cerrar Orden", type="primary", use_container_width=True):
                    if h_fin <= h_ini and h_fin != 0:
                        st.error("Error: El horómetro final debe ser mayor al inicial.")
                    else:
                        try:
                            # 1. Registro de Horas
                            data_horas = {
                                "Fecha": str(date.today()),
                                "Turno": tarea.get('Turno', 'Mañana'),
                                "personal_id": dict_personal[op_sel], 
                                "maquinaria_id": dict_maquina[tract_sel], 
                                "Implemento": implemento,
                                "Labor_Realizada": f"Aplicación {nombre_objetivo}",
                                "Sector": tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": h_ini,
                                "Horometro_Final": h_fin,
                                "Total_Horas": h_fin - h_ini,
                                "Observaciones": obs
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # 2. Actualizar Orden
                            data_update = {
                                "Status": "Aplicada en Campo",
                                "operador_id": dict_personal[op_sel], 
                                "Aplicacion_Completada_Fecha": datetime.now().isoformat(),
                                "Marcha": marcha,
                                "Presion_Bar": presion,
                                "Observaciones_Aplicacion": obs
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_update).eq('id', tarea['id']).execute()

                            st.success("¡Registro completado!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error DB: {e}")

# --- 6. HISTORIAL CON AG-GRID (MOBILE READY) ---
st.divider()
st.header("📚 Historial de Labores")

if not df_hist_h.empty:
    # Unir para ver nombres en lugar de IDs
    df_h_view = pd.merge(df_hist_h, df_pers, left_on='personal_id', right_on='id', how='left')
    df_h_view = pd.merge(df_h_view, df_maqu, left_on='maquinaria_id', right_on='id', how='left')
    df_h_view = df_h_view.rename(columns={'nombre_completo': 'Operador', 'nombre': 'Tractor'})
    
    cols_hist = ['Fecha', 'Operador', 'Tractor', 'Labor_Realizada', 'Total_Horas', 'Sector']
    
    gb = GridOptionsBuilder.from_dataframe(df_h_view[cols_hist])
    gb.configure_pagination(paginationPageSize=10)
    
    # Anchos mínimos para celular
    for col in cols_hist:
        gb.configure_column(col, minWidth=120)
    
    AgGrid(
        df_h_view[cols_hist],
        gridOptions=gb.build(),
        theme='balham',
        height=350,
        columns_auto_size_mode=ColumnsAutoSizeMode.NO_AUTOSIZE # Para que respete el minWidth
    )