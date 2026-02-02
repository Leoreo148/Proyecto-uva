import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Aplicación y Horas", page_icon="🚜", layout="wide")
st.title("🚜 Cartilla de Aplicación y Control de Horas (Build 7.2)")
st.write("Registro unificado de labores de campo y uso de maquinaria.")

# --- FUNCIÓN DE CONEXIÓN SEGURA ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- CARGA DE DATOS NORMALIZADA ---
@st.cache_data(ttl=60)
def cargar_datos_operacion():
    if supabase:
        try:
            # 1. Órdenes listas
            res_o = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Lista para Aplicar').execute()
            # 2. Personal Activo
            res_p = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
            # 3. Maquinaria
            res_m = supabase.table('Maquinaria').select("id, nombre").execute()
            # 4. Historiales
            res_h = supabase.table('Registro_Horas_Tractor').select("*").order('created_at', desc=True).limit(20).execute()
            res_obj = supabase.table('Maestro_Objetivos').select("*").execute()

            return (pd.DataFrame(res_o.data), pd.DataFrame(res_p.data), 
                    pd.DataFrame(res_m.data), pd.DataFrame(res_h.data),
                    pd.DataFrame(res_obj.data))
        except Exception as e:
            st.error(f"Error en carga de datos: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- CARGA INICIAL ---
df_ord, df_pers, df_maqu, df_hist_h, df_obj = cargar_datos_operacion()

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")

if df_ord.empty:
    st.info("No hay aplicaciones con mezcla preparada esperando ser aplicadas.")
else:
    # Diccionarios de mapeo para los selectbox
    dict_personal = {r['nombre_completo']: r['id'] for _, r in df_pers.iterrows()}
    dict_maquina = {r['nombre']: r['id'] for _, r in df_maqu.iterrows()}
    dict_nombres_obj = {r['id']: r['nombre'] for _, r in df_obj.iterrows()}

    for _, tarea in df_ord.iterrows():
        nombre_objetivo = dict_nombres_obj.get(tarea['Objetivo'], "Desconocido")
        exp_title = f"**Orden:** `{tarea['ID_Orden_Personalizado']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Objetivo:** {nombre_objetivo}"
        
        with st.expander(exp_title, expanded=True):
            st.info(f"🧪 **Receta preparada:** {len(tarea['Receta_Mezcla_Lotes'])} productos en tanque.")
            
            with st.form(key=f"form_tractor_{tarea['id']}"):
                st.markdown("##### 🚜 Control de Maquinaria")
                c1, c2 = st.columns(2)
                with c1:
                    op_sel = st.selectbox("Operador Responsable", options=list(dict_personal.keys()))
                    tract_sel = st.selectbox("Tractor / Equipo", options=list(dict_maquina.keys()))
                    h_ini = st.number_input("Horómetro Inicial", min_value=0.0, format="%.2f")
                with c2:
                    implemento = st.text_input("Implemento", value="Nebulizadora Turbo")
                    labor = st.text_input("Labor Realizada", value=f"Aplicación {nombre_objetivo}")
                    h_fin = st.number_input("Horómetro Final", min_value=0.0, format="%.2f")

                st.markdown("##### 🍇 Detalles Técnicos de Aplicación")
                ca1, ca2, ca3 = st.columns(3)
                with ca1:
                    t_app = st.selectbox("Tipo App", ["Pulverizado", "Nebulizado", "Drench"])
                    vol_agua = st.number_input("Volumen Agua/Ha (L)", value=int(tarea.get('Volumen_Agua_Ha', 2200) or 2200))
                with ca2:
                    marcha = st.number_input("Marcha", value=int(tarea.get('Marcha', 18) or 18))
                    presion = st.number_input("Presión (Bar)", value=15.0)
                with ca3:
                    boquilla = st.text_input("Color Boquilla", value="Marrón/Negra")
                    full_maq = st.checkbox("Full Maquinaria", value=True)

                obs = st.text_area("Observaciones de Campo", placeholder="Clima, velocidad del viento, etc.")

                if st.form_submit_button("🏁 Finalizar y Registrar"):
                    if h_fin <= h_ini:
                        st.error("El horómetro final debe ser mayor al inicial.")
                    else:
                        try:
                            # 1. Registro de Horas (Usando IDs)
                            data_horas = {
                                "Fecha": tarea['Fecha_Programada'],
                                "Turno": tarea['Turno'],
                                "Operador": dict_personal[op_sel], # ID de Personal
                                "Tractor": dict_maquina[tract_sel], # ID de Maquinaria
                                "Implemento": implemento,
                                "Labor_Realizada": labor,
                                "Sector": tarea['Sector_Aplicacion'],
                                "Horometro_Inicial": h_ini,
                                "Horometro_Final": h_fin,
                                "Total_Horas": h_fin - h_ini,
                                "Observaciones": obs
                            }
                            supabase.table('Registro_Horas_Tractor').insert(data_horas).execute()

                            # 2. Actualizar Orden a Completada
                            data_update = {
                                "Status": "Completada",
                                "Tractor_Responsable": op_sel, # Mantenemos nombre para visualización rápida
                                "Aplicacion_Completada_Fecha": datetime.now().isoformat(),
                                "Tipo_Aplicacion": t_app,
                                "Volumen_Agua_Ha": vol_agua,
                                "Marcha": marcha,
                                "Presion_Bar": str(presion),
                                "Color_Boquilla": boquilla,
                                "Full_Maquinarias": full_maq,
                                "Observaciones_Aplicacion": obs
                            }
                            supabase.table('Ordenes_de_Trabajo').update(data_update).eq('id', tarea['id']).execute()

                            st.success(f"¡Tarea {tarea['ID_Orden_Personalizado']} finalizada con éxito!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

# --- SECCIÓN 2: HISTORIALES ---
st.divider()
st.header("📚 Historial Reciente")

if not df_hist_h.empty:
    # Unir con Personal y Maquinaria para mostrar nombres en el historial
    df_h_view = pd.merge(df_hist_h, df_pers, left_on='Operador', right_on='id', how='left')
    df_h_view = pd.merge(df_h_view, df_maqu, left_on='Tractor', right_on='id', how='left')
    
    st.subheader("Últimos Registros de Maquinaria")
    st.dataframe(
        df_h_view[['Fecha', 'nombre_completo', 'nombre', 'Labor_Realizada', 'Total_Horas', 'Sector']],
        column_config={
            "nombre_completo": "Operador",
            "nombre": "Tractor",
            "Total_Horas": st.column_config.NumberColumn("Horas", format="%.2f")
        }, use_container_width=True
    )