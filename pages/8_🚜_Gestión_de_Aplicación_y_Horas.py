import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- LIBRERÍAS PRO ---
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
from streamlit_extras.metric_cards import style_metric_cards
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Tablero del Tractorista", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; }
    .btn-start > button { background-color: #2ecc71; color: white; height: 3.5em; font-size: 18px; border-radius: 10px;}
    .btn-stop > button { background-color: #e74c3c; color: white; height: 3.5em; font-size: 18px; border-radius: 10px;}
    .status-progreso { background-color: #fff3cd; padding: 15px; border-radius: 10px; border: 1px solid #ffeeba; text-align: center; margin-bottom: 15px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS ---
def cargar_datos_operacion():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        # Traemos órdenes que estén Finalizadas por almacén o ya En Progreso por el tractorista
        res_o = supabase.table('Ordenes_de_Trabajo').select("*").in_('Status', ['Finalizada', 'En Progreso']).execute()
        res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        res_m = supabase.table('Maquinaria').select("id, nombre").execute()
        res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(50).execute()
        return (pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), pd.DataFrame(res_m.data), pd.DataFrame(res_h.data))
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ord, df_pers, df_maqu, df_hist_h = cargar_datos_operacion()

# --- 4. CABECERA ---
with stylable_container(key="green_title", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("🚜 Panel de Operador en Campo")
    st.write("Control de tiempos de aplicación y registros de maquinaria.")

# --- 5. TAREAS PARA APLICAR ---
st.subheader("📋 Mis Labores Asignadas")

if df_ord.empty:
    st.info("No tienes labores pendientes. Todo está al día en el fundo.")
elif df_pers.empty or df_maqu.empty:
    st.warning("⚠️ Faltan datos de personal o maquinaria en Supabase.")
else:
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}

    for _, tarea in df_ord.iterrows():
        nombre_objetivo = tarea.get('Objetivo', "General")
        estado_actual = tarea['Status']
        
        # Icono visual dependiendo del estado
        icono = "⏳" if estado_actual == 'En Progreso' else "📦"
        exp_title = f"{icono} OT: {tarea['ID_Orden_Personalizado']} | Sector: {tarea.get('Sector_Aplicacion','')} | 🎯 {nombre_objetivo}"
        
        # Si está en progreso, lo expandimos por defecto para que el tractorista lo vea rápido
        with st.expander(exp_title, expanded=(estado_actual == 'En Progreso')):
            
            # --- ESTADO 1: LISTO PARA INICIAR (Configuración) ---
            if estado_actual == 'Finalizada':
                st.info(f"🧪 **Mezcla lista en tanque:** {', '.join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])}")
                
                with st.form(key=f"form_start_{tarea['id']}"):
                    st.write("⚙️ **Configuración del Equipo**")
                    c1, c2 = st.columns(2)
                    op_sel = c1.selectbox("Operador", options=list(dict_personal.keys()))
                    tract_sel = c2.selectbox("Tractor Utilizado", options=list(dict_maquina.keys()))
                    
                    c3, c4, c5 = st.columns(3)
                    marcha = c3.number_input("Marcha", value=1)
                    presion = c4.number_input("Presión (Bar)", value=9.0)
                    vol_ha = c5.number_input("Vol. Lts/Ha", value=1200)

                    st.markdown('<div class="btn-start">', unsafe_allow_html=True)
                    if st.form_submit_button("▶️ INICIAR LABOR", use_container_width=True):
                        try:
                            # Guardamos la configuración y la hora de inicio exactas
                            data_update = {
                                "Status": "En Progreso",
                                "Hora_Inicio_Real": datetime.now().isoformat(),
                                "operador_id": dict_personal[op_sel],
                                "maquinaria_id": dict_maquina[tract_sel],
                                "Marcha": marcha,
                                "Presion_Bar": int(presion),
                                "Observaciones_Aplicacion": f"[CALIBRACIÓN] Marcha: {marcha} | Presión: {presion} Bar | Vol/Ha: {vol_ha} L\n"
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_update).eq('id', tarea['id']).execute()
                            st.success("¡Cronómetro Iniciado! Ya puedes bloquear tu celular y trabajar.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al iniciar: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)

            # --- ESTADO 2: EN PROGRESO (Reloj corriendo) ---
            elif estado_actual == 'En Progreso':
                hora_inicio_str = tarea.get('Hora_Inicio_Real')
                hora_inicio = pd.to_datetime(hora_inicio_str)
                
                st.markdown(f"""
                    <div class="status-progreso">
                        <h2>🚜 APLICACIÓN EN CURSO</h2>
                        <p>Iniciaste a las: <b>{hora_inicio.strftime('%H:%M')}</b></p>
                    </div>
                """, unsafe_allow_html=True)

                with st.form(key=f"form_stop_{tarea['id']}"):
                    obs = st.text_area("📝 Observaciones de Campo (Llenar al terminar)", placeholder="Clima, problemas mecánicos, viento...")
                    
                    st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
                    if st.form_submit_button("⏹️ FINALIZAR LABOR", use_container_width=True):
                        hora_fin = datetime.now()
                        # Cálculo de horas trabajadas (diferencia en segundos / 3600)
                        horas_trabajadas = (hora_fin - hora_inicio).total_seconds() / 3600.0
                        
                        try:
                            # 1. Creamos el registro en el historial de horas (Con Horómetros en 0, ya no se usan)
                            reporte_final = tarea.get('Observaciones_Aplicacion', '') + f"[OBSERVACIONES CAMPO]: {obs}"
                            
                            data_horas = {
                                "Fecha": str(date.today()),
                                "Turno": tarea.get('Turno', 'Día'),
                                "personal_id": tarea['operador_id'], 
                                "maquinaria_id": tarea['maquinaria_id'], 
                                "Implemento": "Pulverizador", # Genérico
                                "Labor_Realizada": f"Aplicación {nombre_objetivo}",
                                "Sector": tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": 0.0,
                                "Horometro_Final": 0.0,
                                "Total_Horas": round(horas_trabajadas, 2), # Redondeado a 2 decimales
                                "Observaciones": reporte_final
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # 2. Cerramos la orden
                            data_close = {
                                "Status": "Aplicada en Campo",
                                "Aplicacion_Completada_Fecha": hora_fin.isoformat(),
                                "Observaciones_Aplicacion": reporte_final
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_close).eq('id', tarea['id']).execute()

                            st.success(f"¡Labor finalizada! Tiempo total registrado: {round(horas_trabajadas, 2)} horas.")
                            st.balloons()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al finalizar: {e}")
                    st.markdown('</div>', unsafe_allow_html=True)

# --- 6. HISTORIAL RÁPIDO ---
st.divider()
st.subheader("📚 Mis Últimas Labores")

if not df_hist_h.empty:
    df_h_view = pd.merge(df_hist_h, df_pers, left_on='personal_id', right_on='id', how='left')
    df_h_view = pd.merge(df_h_view, df_maqu, left_on='maquinaria_id', right_on='id', how='left')
    
    # Filtramos solo para ver en tabla las columnas esenciales
    cols_hist = ['Fecha', 'nombre_completo', 'nombre', 'Total_Horas', 'Sector']
    df_mini = df_h_view[cols_hist].rename(columns={'nombre_completo': 'Operador', 'nombre': 'Tractor'})
    
    gb = GridOptionsBuilder.from_dataframe(df_mini)
    gb.configure_pagination(paginationPageSize=5)
    AgGrid(df_mini, gridOptions=gb.build(), theme='balham', height=250, columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS)