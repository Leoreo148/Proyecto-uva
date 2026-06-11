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
st.markdown("""
    <style>
    /* === TARJETAS DE TURNO === */
    .turno-header {
        font-size: 1.3rem;
        font-weight: 800;
        padding: 10px 18px;
        border-radius: 10px;
        margin: 20px 0 10px 0;
        letter-spacing: 0.5px;
    }
    .turno-dia   { background: #FFF8E1; color: #E65100; border-left: 6px solid #FF8F00; }
    .turno-tarde { background: #E8F5E9; color: #1B5E20; border-left: 6px solid #2E7D32; }
    .turno-noche { background: #EDE7F6; color: #311B92; border-left: 6px solid #4527A0; }

    .ot-card {
        background: white;
        border-radius: 14px;
        padding: 20px 22px;
        margin-bottom: 18px;
        box-shadow: 0 3px 12px rgba(0,0,0,0.10);
        border-left: 7px solid #3498db;
    }
    .ot-card-header {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1a252f;
        margin-bottom: 6px;
    }
    .ot-badge {
        display: inline-block;
        font-size: 0.82rem;
        font-weight: 600;
        padding: 3px 10px;
        border-radius: 20px;
        background: #EBF5FB;
        color: #2980b9;
        margin-right: 6px;
        margin-bottom: 8px;
    }
    .ot-mezcla {
        background: #FDF5E6;
        border-left: 4px solid #f39c12;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 1rem;
        margin: 10px 0;
        color: #7D4800;
        line-height: 1.6;
    }
    .ot-instruc {
        background: #E8F8F5;
        border-left: 4px solid #1abc9c;
        border-radius: 8px;
        padding: 12px 14px;
        font-size: 1rem;
        line-height: 1.8;
        margin: 10px 0;
        color: #1a252f;
    }
    .ot-obs {
        background: #EBF5FB;
        border-left: 4px solid #3498db;
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.95rem;
        color: #1F618D;
        margin: 10px 0;
    }
    /* Botones más grandes en móvil */
    div[data-testid="stButton"] > button {
        font-size: 1.05rem !important;
        padding: 0.6rem 1rem !important;
    }
    </style>
""", unsafe_allow_html=True)

if df_ord.empty:
    st.info("No hay órdenes de aplicación pendientes. Descansa. ☕")
elif df_pers.empty or df_maqu.empty:
    st.warning("⚠️ Faltan datos de personal o maquinaria en Supabase.")
else:
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina  = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}

    # --- Filtrar órdenes relevantes ---
    ordenes_filtradas = []
    for _, tarea in df_ord.iterrows():
        tipo_app = str(tarea.get('Tipo_Aplicacion', ''))
        if "Fertirriego" in tipo_app:
            continue
        if not es_supervisor and mi_personal_id is not None:
            oper_id_orden = tarea.get('operador_id')
            if oper_id_orden is not None and int(oper_id_orden) != mi_personal_id:
                continue
        ordenes_filtradas.append(tarea)

    if not ordenes_filtradas:
        if not es_supervisor and mi_personal_id is None:
            st.warning(f"⚠️ Tu nombre '{nombre_sesion}' no coincide con ningún operario en la tabla Personal.")
        else:
            st.info("No tienes órdenes de aplicación pendientes asignadas a ti. Descansa. ☕")
    else:
        # --- Ordenar por turno: Día → Tarde → Noche ---
        orden_turno = {"Día": 0, "Tarde": 1, "Noche": 2}
        def get_turno(t):
            dt = t.get('Datos_Tecnicos') or {}
            return dt.get('Turno', 'Día') if isinstance(dt, dict) else 'Día'

        ordenes_filtradas.sort(key=lambda t: orden_turno.get(get_turno(t), 0))

        turno_iconos = {
            "Día":   ("☀️ TURNO DÍA",   "turno-dia"),
            "Tarde": ("🌤️ TURNO TARDE", "turno-tarde"),
            "Noche": ("🌙 TURNO NOCHE", "turno-noche"),
        }
        turno_color_card = {
            "Día":   "#FF8F00",
            "Tarde": "#2E7D32",
            "Noche": "#4527A0",
        }

        turno_actual_mostrado = None

        for tarea in ordenes_filtradas:
            turno_ot = get_turno(tarea)

            # --- Encabezado de turno cuando cambia ---
            if turno_ot != turno_actual_mostrado:
                turno_actual_mostrado = turno_ot
                label, css_class = turno_iconos.get(turno_ot, ("📋 SIN TURNO", "turno-dia"))
                st.markdown(f'<div class="turno-header {css_class}">{label}</div>', unsafe_allow_html=True)

            color_card = turno_color_card.get(turno_ot, "#3498db")
            sector     = tarea.get('Sector_Aplicacion', '-')
            objetivo   = tarea.get('Objetivo', 'General')
            id_orden   = tarea.get('ID_Orden_Personalizado', tarea.get('id', ''))

            # --- Parser de instrucciones ---
            inst_raw = str(tarea.get('Observaciones_Aplicacion', ''))
            def xtag(texto, tag_start, tag_end_list):
                if tag_start in texto:
                    si = texto.find(tag_start) + len(tag_start)
                    ends = [texto.find(t, si) for t in tag_end_list if texto.find(t, si) != -1]
                    ei = min(ends) if ends else len(texto)
                    return texto[si:ei].strip(' |').strip()
                return "N/A"

            metodo     = xtag(inst_raw, "[MÉTODO]:",    ["[AGUA]:", "[CALIBRACIÓN]:", "[BOQUILLAS]:", "[EQUIPO]:", "[OBSERVACIONES]:"])
            calibracion= xtag(inst_raw, "[CALIBRACIÓN]:",["[BOQUILLAS]:", "[EQUIPO]:", "[OBSERVACIONES]:"])
            agua       = xtag(inst_raw, "[AGUA]:",      ["[CALIBRACIÓN]:", "[BOQUILLAS]:", "[EQUIPO]:", "[OBSERVACIONES]:"])
            boquillas  = xtag(inst_raw, "[BOQUILLAS]:", ["[EQUIPO]:", "[OBSERVACIONES]:"])
            obs_pura   = ""
            if "[OBSERVACIONES]:" in inst_raw:
                obs_pura = inst_raw[inst_raw.find("[OBSERVACIONES]:") + len("[OBSERVACIONES]:"):].strip()

            # Receta mezcla
            receta_items = tarea.get('Receta_Mezcla_Lotes', []) or []
            receta_str = " &nbsp;|&nbsp; ".join([f"<b>{i['p']}</b> ({i['c']})" for i in receta_items]) if receta_items else "Sin mezcla registrada"

            # --- Tarjeta visual ---
            st.markdown(f"""
                <div class="ot-card" style="border-left-color:{color_card}">
                    <div class="ot-card-header">📋 {id_orden}</div>
                    <span class="ot-badge">📍 Sector: {sector}</span>
                    <span class="ot-badge">🎯 {objetivo}</span>
                    <div class="ot-mezcla">🧪 <b>Mezcla autorizada:</b><br>{receta_str}</div>
                    <div class="ot-instruc">
                        🚜 <b>Método:</b> {metodo}<br>
                        ⚙️ <b>Calibración:</b> {calibracion}<br>
                        💧 <b>Agua:</b> {agua}<br>
                        🚰 <b>Boquillas:</b> {boquillas}
                    </div>
                    {"<div class='ot-obs'>📝 <b>Nota del Ingeniero:</b> " + obs_pura + "</div>" if obs_pura else ""}
                </div>
            """, unsafe_allow_html=True)

            # --- Formulario de reporte (dentro de expander compacto) ---
            with st.expander("✅ Registrar reporte de campo para esta OT", expanded=False):
                with st.form(key=f"form_horometro_{tarea['id']}"):
                    c1, c2, c3 = st.columns(3)
                    op_sel    = c1.selectbox("Soy el Operador:", options=list(dict_personal.keys()))
                    tract_sel = c2.selectbox("Tractor Utilizado:", options=list(dict_maquina.keys()))
                    turno_sel = c3.selectbox("Turno:", options=["Día", "Tarde", "Noche"],
                                             index=["Día","Tarde","Noche"].index(turno_ot) if turno_ot in ["Día","Tarde","Noche"] else 0)

                    c4, c5, c6 = st.columns(3)
                    horometro_ini = c4.number_input("Horómetro INICIAL", min_value=0.0, step=0.1, format="%.1f")
                    horometro_fin = c5.number_input("Horómetro FINAL",   min_value=0.0, step=0.1, format="%.1f")
                    agua_total    = c6.number_input("Agua Usada (Litros)", min_value=0, step=100)

                    obs = st.text_area("📝 Novedades en campo (Opcional)", placeholder="Ej: Se tapó boquilla derecha.")

                    if st.form_submit_button("💾 ENVIAR REPORTE AL INGENIERO", use_container_width=True, type="primary"):
                        if horometro_fin < horometro_ini:
                            st.error("❌ El horómetro final no puede ser menor al inicial.")
                        else:
                            horas_trabajadas = horometro_fin - horometro_ini
                            try:
                                obs_ant       = tarea.get('Observaciones_Aplicacion', '')
                                reporte_final = f"{obs_ant}\n[OPERADOR]: Usó {agua_total} Lts. Turno: {turno_sel}. Notas: {obs}"
                                data_horas = {
                                    "Fecha":             str(date.today()),
                                    "Turno":             turno_sel,
                                    "personal_id":       int(dict_personal[op_sel]),
                                    "maquinaria_id":     int(dict_maquina[tract_sel]),
                                    "Implemento":        tarea.get('Tipo_Aplicacion', 'Pulverizador'),
                                    "Labor_Realizada":   f"Aplicación {objetivo}",
                                    "Sector":            sector,
                                    "Horometro_Inicial": float(horometro_ini),
                                    "Horometro_Final":   float(horometro_fin),
                                    "Total_Horas":       round(horas_trabajadas, 2),
                                    "Observaciones":     f"Agua: {agua_total}L | Turno: {turno_sel} | Notas: {obs}"
                                }
                                supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()
                                dt = tarea.get('Datos_Tecnicos', {}) or {}
                                dt['Agua_Real_Lts']        = agua_total
                                dt['Horas_Maquina_Reales'] = round(horas_trabajadas, 2)
                                dt['Turno']                = turno_sel
                                supabase.table('Ordenes_de_Trabajo').update({
                                    "Status":                      "Aplicada en Campo",
                                    "Aplicacion_Completada_Fecha": datetime.now().isoformat(),
                                    "Datos_Tecnicos":              dt,
                                    "Observaciones_Aplicacion":    reporte_final
                                }).eq('id', tarea['id']).execute()
                                st.success(f"¡Reporte enviado! {round(horas_trabajadas,2)} hrs | Turno: {turno_sel}")
                                cargar_datos_operacion.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al enviar: {e}")



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