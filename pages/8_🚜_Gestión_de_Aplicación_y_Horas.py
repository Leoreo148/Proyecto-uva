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
    .btn-start > button { background-color: #2ecc71; color: white; height: 3.5em; font-size: 18px; border-radius: 10px; font-weight: bold;}
    .btn-stop > button { background-color: #e74c3c; color: white; height: 3.5em; font-size: 18px; border-radius: 10px; font-weight: bold;}
    .status-progreso { background-color: #fff3cd; padding: 15px; border-radius: 10px; border: 1px solid #ffeeba; text-align: center; margin-bottom: 15px;}
    .instrucciones-box { background-color: #e8f4f8; padding: 15px; border-left: 5px solid #3498db; border-radius: 5px; margin-bottom: 15px; font-family: monospace;}
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
    st.write("Control de tiempos de aplicación y parámetros de maquinaria.")

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
            
            # --- ESTADO 1: LISTO PARA INICIAR (Modo Lectura + Cronómetro) ---
            if estado_actual == 'Finalizada':
                st.info(f"🧪 **Mezcla lista en tanque:** {', '.join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])}")
                
                # Mostramos las instrucciones que el ingeniero mandó desde "Mezclas"
                instrucciones = tarea.get('Observaciones_Aplicacion', 'Sin instrucciones especiales.')
                st.markdown(f'<div class="instrucciones-box"><b>📝 PARÁMETROS DEL INGENIERO:</b><br>{instrucciones}</div>', unsafe_allow_html=True)
                
                with st.form(key=f"form_start_{tarea['id']}"):
                    st.write("👤 **Confirma tu identidad y equipo antes de iniciar:**")
                    c1, c2 = st.columns(2)
                    # Solo pedimos esto para que la base de datos sepa a qué tractor sumarle las horas
                    op_sel = c1.selectbox("Soy el Operador:", options=list(dict_personal.keys()))
                    tract_sel = c2.selectbox("Voy a usar el Tractor:", options=list(dict_maquina.keys()))
                    
                    st.markdown('<div class="btn-start">', unsafe_allow_html=True)
                    if st.form_submit_button("▶️ INICIAR LABOR", use_container_width=True):
                        try:
                            # Guardamos la hora de inicio exacta
                            data_update = {
                                "Status": "En Progreso",
                                "Hora_Inicio_Real": datetime.now().isoformat(),
                                "operador_id": dict_personal[op_sel],
                                "maquinaria_id": dict_maquina[tract_sel]
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
                    obs = st.text_area("📝 Novedades en campo (Opcional)", placeholder="Problemas mecánicos, viento fuerte, etc.")
                    
                    st.markdown('<div class="btn-stop">', unsafe_allow_html=True)
                    if st.form_submit_button("⏹️ FINALIZAR LABOR", use_container_width=True):
                        hora_fin = datetime.now()
                        
                        # CÁLCULO MÁGICO: Diferencia en segundos convertida a horas con 2 decimales
                        horas_trabajadas = (hora_fin - hora_inicio).total_seconds() / 3600.0
                        
                        try:
                            # --- 🛡️ FIX ANTI-FLOAT ---
                            obs_ant = tarea.get('Observaciones_Aplicacion', '')
                            if pd.isna(obs_ant): # Si es NaN (float), lo volvemos texto vacío
                                obs_ant = ""
                            
                            reporte_final = str(obs_ant) + f"\n[NOTAS DEL OPERADOR]: {obs}"
                            # --------------------------
                            
                            data_horas = {
                                "Fecha": str(date.today()),
                                "Turno": tarea.get('Turno', 'Día'),
                                "personal_id": int(tarea['operador_id']), # <--- FIX: Forzamos a entero
                                "maquinaria_id": int(tarea['maquinaria_id']), # <--- FIX: Forzamos a entero
                                "Implemento": "Pulverizador", 
                                "Labor_Realizada": f"Aplicación {nombre_objetivo}",
                                "Sector": tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": 0.0, 
                                "Horometro_Final": round(horas_trabajadas, 2), 
                                "Total_Horas": round(horas_trabajadas, 2),
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