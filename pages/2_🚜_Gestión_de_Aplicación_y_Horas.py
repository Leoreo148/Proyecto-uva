import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- LIBRERÍAS PRO ---
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Tablero del Tractorista", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .instrucciones-box { background-color: #e8f4f8; padding: 15px; border-left: 5px solid #3498db; border-radius: 5px; margin-bottom: 15px; font-family: monospace;}
    .receta-box { background-color: #fdf5e6; padding: 10px; border-left: 5px solid #f39c12; border-radius: 5px; margin-bottom: 15px;}
    .btn-finish > button { background-color: #2ecc71; color: white; height: 3.5em; font-size: 18px; border-radius: 10px; font-weight: bold; width: 100%;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS ---
def cargar_datos_operacion():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        # Traemos órdenes que estén Finalizadas por almacén (O sea, Listas para aplicar)
        res_o = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Finalizada').execute()
        res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        res_m = supabase.table('Maquinaria').select("id, nombre").execute()
        return pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), pd.DataFrame(res_m.data)
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ord, df_pers, df_maqu = cargar_datos_operacion()

# --- 4. CABECERA ---
with stylable_container(key="green_title", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("🚜 Panel de Registro de Campo (Horómetro)")
    st.write("Llena este formulario al terminar tu aplicación para registrar tus horas y el consumo real de agua.")

# --- 5. TAREAS PARA APLICAR ---
st.subheader("📋 Mis Órdenes Asignadas")

if df_ord.empty:
    st.info("No tienes órdenes de aplicación pendientes. Descansa.")
elif df_pers.empty or df_maqu.empty:
    st.warning("⚠️ Faltan datos de personal o maquinaria en Supabase.")
else:
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}

    for _, tarea in df_ord.iterrows():
        nombre_objetivo = tarea.get('Objetivo', "General")
        
        # 💡 SOLO MOSTRAMOS TAREAS FOLARES/MAQUINARIA AL TRACTORISTA
        tipo_app = tarea.get('Tipo_Aplicacion', '')
        if "Fertirriego" in tipo_app:
            continue # Saltamos las de riego, esas van para el casetero
            
        exp_title = f"📦 OT: {tarea['ID_Orden_Personalizado']} | Sector: {tarea.get('Sector_Aplicacion','')} | 🎯 {nombre_objetivo}"
        
        with st.expander(exp_title, expanded=False):
            
            # --- DATOS QUE EL TRACTORISTA DEBE LEER ---
            st.markdown(f'<div class="receta-box"><b>🧪 MEZCLA AUTORIZADA:</b> {", ".join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])}</div>', unsafe_allow_html=True)
            
            instrucciones = tarea.get('Observaciones_Aplicacion', 'Sin instrucciones especiales.')
            st.markdown(f'<div class="instrucciones-box"><b>📝 PARÁMETROS DEL INGENIERO:</b><br>{instrucciones}</div>', unsafe_allow_html=True)
            
            st.write("---")
            st.write("✅ **Rellena los datos físicos al terminar la labor:**")
            
            # --- FORMULARIO DE CIERRE DIFERIDO ---
            with st.form(key=f"form_horometro_{tarea['id']}"):
                c1, c2 = st.columns(2)
                op_sel = c1.selectbox("Soy el Operador:", options=list(dict_personal.keys()))
                tract_sel = c2.selectbox("Tractor Utilizado:", options=list(dict_maquina.keys()))
                
                c3, c4, c5 = st.columns(3)
                # Datos clave operativos
                horometro_ini = c3.number_input("Horómetro INICIAL", min_value=0.0, step=0.1, format="%.1f")
                horometro_fin = c4.number_input("Horómetro FINAL", min_value=0.0, step=0.1, format="%.1f")
                agua_total = c5.number_input("Total Agua Usada (Litros)", min_value=0, step=100)
                
                obs = st.text_area("📝 Novedades en campo (Opcional)", placeholder="Limpié filtros 2 veces. / Se tapó boquilla derecha.")
                
                st.markdown('<div class="btn-finish">', unsafe_allow_html=True)
                if st.form_submit_button("💾 ENVIAR REPORTE AL INGENIERO", use_container_width=True):
                    
                    if horometro_fin < horometro_ini:
                        st.error("❌ El horómetro final no puede ser menor al inicial.")
                    else:
                        horas_trabajadas = horometro_fin - horometro_ini
                        
                        try:
                            # 1. Armamos el reporte sumando lo que puso el ingeniero + lo que puso el tractorista
                            obs_ant = tarea.get('Observaciones_Aplicacion', '')
                            reporte_final = f"{obs_ant}\n[OPERADOR]: Usó {agua_total} Lts. Notas: {obs}"
                            
                            # 2. Guardamos las horas exactas en la tabla de Horas_Tractor
                            data_horas = {
                                "Fecha": str(date.today()),
                                "Turno": tarea.get('Turno', 'Día'),
                                "personal_id": int(dict_personal[op_sel]),
                                "maquinaria_id": int(dict_maquina[tract_sel]),
                                "Implemento": tarea.get('Tipo_Aplicacion', 'Pulverizador'), 
                                "Labor_Realizada": f"Aplicación {nombre_objetivo}",
                                "Sector": tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": float(horometro_ini), 
                                "Horometro_Final": float(horometro_fin), 
                                "Total_Horas": round(horas_trabajadas, 2),
                                "Observaciones": f"Agua: {agua_total}L | Notas: {obs}"
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # 3. Cerramos la orden maestra para que le salga como "Finalizada" en el Dashboard de Costos
                            # 💡 MAGIA: Añadimos el Agua Total a los Datos Técnicos de la Orden
                            dt = tarea.get('Datos_Tecnicos', {})
                            dt['Agua_Real_Lts'] = agua_total
                            dt['Horas_Maquina_Reales'] = round(horas_trabajadas, 2)
                            
                            data_close = {
                                "Status": "Aplicada en Campo",
                                "Aplicacion_Completada_Fecha": datetime.now().isoformat(),
                                "Datos_Tecnicos": dt,
                                "Observaciones_Aplicacion": reporte_final
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_close).eq('id', tarea['id']).execute()

                            st.success(f"¡Reporte enviado! Horas de tractor registradas: {round(horas_trabajadas, 2)} hrs.")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al enviar: {e}")
                st.markdown('</div>', unsafe_allow_html=True)

# --- 6. HISTORIAL DE LABORES Y DESCARGA ---
st.divider()
st.header("📚 Historial de Aplicaciones")

try:
    res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(20).execute()
    df_hist_fresco = pd.DataFrame(res_h.data)

    if not df_hist_fresco.empty:
        df_merged = pd.merge(df_hist_fresco, df_pers, left_on='personal_id', right_on='id', how='left')
        df_merged = pd.merge(df_merged, df_maqu, left_on='maquinaria_id', right_on='id', how='left')
        
        df_view = df_merged[['Fecha', 'nombre_completo', 'nombre', 'Sector', 'Total_Horas', 'Observaciones']].copy()
        df_view.columns = ['📅 Fecha', '👤 Operador', '🚜 Tractor', '📍 Sector', '⏱️ Hrs', '📝 Detalles']

        c_h1, c_h2 = st.columns(2)
        c_h1.metric("Horas Totales (Últimos Registros)", f"{df_view['⏱️ Hrs'].sum():.2f} hrs")
        
        csv = df_view.to_csv(index=False).encode('utf-8-sig')
        c_h2.download_button("📥 Descargar Reporte (Excel)", data=csv, file_name=f'reporte_tractor_{date.today()}.csv', mime='text/csv')

        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay registros en el historial de campo.")
except Exception as e:
    st.error(f"Error visualizando historial: {e}")