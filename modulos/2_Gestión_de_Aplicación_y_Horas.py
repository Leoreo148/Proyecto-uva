import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from supabase import create_client
from streamlit_extras.stylable_container import stylable_container

# 🚨 CANDADO DE SEGURIDAD
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal antes de acceder a este módulo.")
    st.stop()

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Tablero del Tractorista", page_icon="🚜", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .instrucciones-box { background-color: #e8f4f8; padding: 15px; border-left: 5px solid #3498db; border-radius: 5px; margin-bottom: 15px; font-family: monospace;}
    .receta-box { background-color: #fdf5e6; padding: 10px; border-left: 5px solid #f39c12; border-radius: 5px; margin-bottom: 15px;}
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS (con caché específica) ---
@st.cache_data(ttl=30)
def cargar_datos_operacion():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    try:
        # ✅ FIX ESTADO: Traemos Finalizada + Aplicada en Campo para no perder histórico
        res_o = supabase.table('Ordenes_de_Trabajo').select("*").in_('Status', ['Finalizada']).execute()
        res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
        res_m = supabase.table('Maquinaria').select("id, nombre").execute()
        return pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), pd.DataFrame(res_m.data)
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

df_ord, df_pers, df_maqu = cargar_datos_operacion()

# --- 4. IDENTIFICAR AL OPERARIO LOGUEADO ---
rol_actual    = st.session_state.get("rol", "")
nombre_sesion = st.session_state.get("nombre", "")

# ✅ MEJORA: Encontrar el ID del personal que coincide con el usuario logueado
mi_personal_id = None
es_supervisor  = rol_actual in ["Admin", "Programador"]   # Supervisores ven TODO

if not df_pers.empty and not es_supervisor:
    match_personal = df_pers[df_pers['nombre_completo'].str.lower() == nombre_sesion.lower()]
    if not match_personal.empty:
        mi_personal_id = int(match_personal.iloc[0]['id'])

# --- 5. CABECERA ---
with stylable_container(key="green_title", css_styles="{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; }"):
    st.title("🚜 Panel de Registro de Campo (Horómetro)")
    if es_supervisor:
        st.write("Vista de supervisor: mostrando todas las órdenes asignadas.")
    else:
        st.write(f"Bienvenido, **{nombre_sesion}**. Aquí están tus órdenes asignadas para aplicar.")

# --- 6. TAREAS PENDIENTES ---
st.subheader("📋 Mis Órdenes Asignadas")

if df_ord.empty:
    st.info("No hay órdenes de aplicación pendientes. Descansa. ☕")
elif df_pers.empty or df_maqu.empty:
    st.warning("⚠️ Faltan datos de personal o maquinaria en Supabase.")
else:
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina  = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}

    tareas_mostradas = 0

    for _, tarea in df_ord.iterrows():
        tipo_app = str(tarea.get('Tipo_Aplicacion', ''))
        if "Fertirriego" in tipo_app:
            continue  # Las de riego van para el casetero

        # ✅ MEJORA: Filtrar por operario logueado (supervisores ven todo)
        if not es_supervisor and mi_personal_id is not None:
            oper_id_orden = tarea.get('operador_id')
            if oper_id_orden is not None and int(oper_id_orden) != mi_personal_id:
                continue   # No es tu orden, la saltamos

        tareas_mostradas += 1
        nombre_objetivo = tarea.get('Objetivo', "General")
        exp_title = f"📦 OT: {tarea['ID_Orden_Personalizado']} | Sector: {tarea.get('Sector_Aplicacion','')} | 🎯 {nombre_objetivo}"

        with st.expander(exp_title, expanded=False):

            # Datos que el tractorista debe leer
            receta_str = ", ".join([f"{i['p']} ({i['c']})" for i in tarea.get('Receta_Mezcla_Lotes', [])])
            st.markdown(f'<div class="receta-box"><b>🧪 MEZCLA AUTORIZADA:</b> {receta_str}</div>', unsafe_allow_html=True)

            vol_ha   = tarea.get('Volumen_Hectarea', 'N/A')
            marcha   = tarea.get('Marcha', 'N/A')
            presion  = tarea.get('Presion_Bar', 'N/A')
            metodo   = tarea.get('Tipo_Aplicacion', 'N/A')
            boquillas= tarea.get('Color_Boquilla', 'N/A')

            st.markdown(f"""
                <div class="instrucciones-box">
                    <b>📝 CONFIGURACIÓN DEL TRACTOR (Mandato del Ingeniero):</b><br>
                    • <b>Método:</b> {metodo}<br>
                    • <b>Marcha:</b> {marcha} &nbsp;|&nbsp; <b>Presión:</b> {presion} Bar<br>
                    • <b>Volumen/Ha:</b> {vol_ha} Lts/Ha &nbsp;|&nbsp; <b>Boquillas:</b> {boquillas}
                </div>
            """, unsafe_allow_html=True)

            instrucciones_extra = tarea.get('Observaciones_Aplicacion', '')
            if instrucciones_extra:
                st.info(f"**Nota del Ingeniero:** {instrucciones_extra}")

            st.write("---")
            st.write("✅ **Rellena los datos físicos al terminar la labor:**")

            # Formulario de cierre
            with st.form(key=f"form_horometro_{tarea['id']}"):
                c1, c2, c3 = st.columns(3)
                op_sel    = c1.selectbox("Soy el Operador:", options=list(dict_personal.keys()))
                tract_sel = c2.selectbox("Tractor Utilizado:", options=list(dict_maquina.keys()))
                # ✅ MEJORA: Campo de Turno añadido al formulario
                turno_sel = c3.selectbox("Turno:", options=["Día", "Tarde", "Noche"])

                c4, c5, c6 = st.columns(3)
                horometro_ini = c4.number_input("Horómetro INICIAL", min_value=0.0, step=0.1, format="%.1f")
                horometro_fin = c5.number_input("Horómetro FINAL",   min_value=0.0, step=0.1, format="%.1f")
                agua_total    = c6.number_input("Total Agua Usada (Litros)", min_value=0, step=100)

                obs = st.text_area("📝 Novedades en campo (Opcional)", placeholder="Limpié filtros 2 veces. / Se tapó boquilla derecha.")

                if st.form_submit_button("💾 ENVIAR REPORTE AL INGENIERO", use_container_width=True, type="primary"):
                    if horometro_fin < horometro_ini:
                        st.error("❌ El horómetro final no puede ser menor al inicial.")
                    else:
                        horas_trabajadas = horometro_fin - horometro_ini
                        try:
                            obs_ant      = tarea.get('Observaciones_Aplicacion', '')
                            reporte_final = f"{obs_ant}\n[OPERADOR]: Usó {agua_total} Lts. Turno: {turno_sel}. Notas: {obs}"

                            data_horas = {
                                "Fecha":             str(date.today()),
                                "Turno":             turno_sel,    # ✅ Ahora sí guarda el turno real
                                "personal_id":       int(dict_personal[op_sel]),
                                "maquinaria_id":     int(dict_maquina[tract_sel]),
                                "Implemento":        tarea.get('Tipo_Aplicacion', 'Pulverizador'),
                                "Labor_Realizada":   f"Aplicación {nombre_objetivo}",
                                "Sector":            tarea.get('Sector_Aplicacion', ''),
                                "Horometro_Inicial": float(horometro_ini),
                                "Horometro_Final":   float(horometro_fin),
                                "Total_Horas":       round(horas_trabajadas, 2),
                                "Observaciones":     f"Agua: {agua_total}L | Turno: {turno_sel} | Notas: {obs}"
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # ✅ FIX ESTADO: Cambiamos a "Aplicada en Campo" para no romper el historial de costos
                            dt = tarea.get('Datos_Tecnicos', {}) or {}
                            dt['Agua_Real_Lts']       = agua_total
                            dt['Horas_Maquina_Reales'] = round(horas_trabajadas, 2)
                            dt['Turno']               = turno_sel

                            supabase.table('Ordenes_de_Trabajo').update({
                                "Status":                       "Aplicada en Campo",
                                "Aplicacion_Completada_Fecha":  datetime.now().isoformat(),
                                "Datos_Tecnicos":               dt,
                                "Observaciones_Aplicacion":     reporte_final
                            }).eq('id', tarea['id']).execute()

                            st.success(f"¡Reporte enviado! Horas registradas: **{round(horas_trabajadas, 2)} hrs** | Turno: **{turno_sel}**")
                            # ✅ Caché específica
                            cargar_datos_operacion.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al enviar: {e}")

    if tareas_mostradas == 0:
        if not es_supervisor and mi_personal_id is None:
            st.warning(f"⚠️ Tu nombre '{nombre_sesion}' no coincide con ningún operario registrado en la tabla Personal. Contacta al administrador.")
        else:
            st.info("No tienes órdenes de aplicación pendientes asignadas a ti. Descansa. ☕")

# --- 7. HISTORIAL DE LABORES Y DESCARGA ---
st.divider()
st.header("📚 Historial de Aplicaciones")

try:
    res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(50).execute()
    df_hist_fresco = pd.DataFrame(res_h.data)

    if not df_hist_fresco.empty:
        df_merged = pd.merge(df_hist_fresco, df_pers, left_on='personal_id', right_on='id', how='left')
        df_merged = pd.merge(df_merged, df_maqu, left_on='maquinaria_id', right_on='id', how='left')

        df_view = df_merged[['Fecha', 'Turno', 'nombre_completo', 'nombre', 'Sector', 'Total_Horas', 'Observaciones']].copy()
        df_view.columns = ['📅 Fecha', '🕐 Turno', '👤 Operador', '🚜 Tractor', '📍 Sector', '⏱️ Hrs', '📝 Detalles']

        # ✅ Filtrar por operario si no es supervisor
        if not es_supervisor and mi_personal_id is not None:
            nombre_op = df_pers[df_pers['id'] == mi_personal_id]['nombre_completo'].values
            if len(nombre_op) > 0:
                df_view = df_view[df_view['👤 Operador'] == nombre_op[0]]

        c_h1, c_h2, c_h3 = st.columns(3)
        horas_tot = df_view['⏱️ Hrs'].sum()
        c_h1.metric("Horas Totales", f"{horas_tot:.2f} hrs")
        c_h2.metric("Aplicaciones", f"{len(df_view)} registros")

        csv = df_view.to_csv(index=False).encode('utf-8-sig')
        c_h3.download_button("📥 Descargar Reporte", data=csv,
                              file_name=f'reporte_tractor_{date.today()}.csv', mime='text/csv')

        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.info("Aún no hay registros en el historial de campo.")
except Exception as e:
    st.error(f"Error visualizando historial: {e}")