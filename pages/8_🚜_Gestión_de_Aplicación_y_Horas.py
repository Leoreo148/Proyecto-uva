import streamlit as st
import pandas as pd
import json
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Aplicación y Horas", page_icon="🚜", layout="wide")
st.title("🚜 Cartilla de Aplicación y Control de Horas")
st.write("El operario completa la cartilla unificada para finalizar la aplicación y registrar las horas de maquinaria.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
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

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_para_aplicacion():
    """Carga las órdenes listas para aplicar y el historial de horas desde Supabase."""
    if supabase:
        try:
            # Cargar órdenes con estado 'Lista para Aplicar'
            res_ordenes = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Lista para Aplicar').execute()
            df_ordenes = pd.DataFrame(res_ordenes.data)
            
            # Cargar historial de horas de tractor
            res_horas = supabase.table('Registro_Horas_Tractor').select("*").order('Fecha', desc=True).limit(50).execute()
            df_horas = pd.DataFrame(res_horas.data)
            
            # Cargar historial de órdenes completadas
            res_completadas = supabase.table('Ordenes_de_Trabajo').select("*").eq('Status', 'Completada').order('created_at', desc=True).limit(50).execute()
            df_completadas = pd.DataFrame(res_completadas.data)

            return df_ordenes, df_horas, df_completadas
        except Exception as e:
            st.error(f"Error al cargar datos de Supabase: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

# --- CARGA DE DATOS ---
df_ordenes_pendientes, df_historial_horas, df_historial_apps = cargar_datos_para_aplicacion()

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")

if not df_ordenes_pendientes.empty:
    for index, tarea in df_ordenes_pendientes.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden_Personalizado']}` | **Sector:** {tarea['Sector_Aplicacion']}"
        with st.expander(expander_title, expanded=True):
            st.write("**Receta de la Mezcla:**")
            receta = tarea['Receta_Mezcla_Lotes']
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_unificado_{tarea['id']}"):
                st.subheader("Cartilla Unificada de Aplicación y Horas")
                
                # --- DATOS DEL CONTROL DE HORAS ---
                st.markdown("##### Parte Diario de Maquinaria")
                col_parte1, col_parte2 = st.columns(2)
                with col_parte1:
                    operario = st.text_input("Nombre del Operador", value="Antonio Cornejo")
                    implemento = st.text_input("Implemento Utilizado", "Nebulizadora")
                with col_parte2:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")
                    labor_realizada = st.text_input("Labor Realizada", value=f"Aplicación {tarea['Objetivo']}")

                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    h_inicial = st.number_input("Horómetro Inicial", min_value=0.0, format="%.2f", step=0.1)
                with col_h2:
                    h_final = st.number_input("Horómetro Final", min_value=0.0, format="%.2f", step=0.1)

                # --- DATOS DE LA CARTILLA DE APLICACIÓN ---
                st.markdown("##### Detalles de la Aplicación")
                col_app1, col_app2 = st.columns(2)
                with col_app1:
                    tipo_aplicacion = st.selectbox("Tipo de Aplicación", ["Pulverizado (Turbo)", "Nebulizado (Turbo)", "Pistolas/Winch", "Inyectores", "Foliar", "Drench"])
                    volumen_agua_ha = st.number_input("Volumen de Agua / Ha (L)", min_value=0, value=2200)
                    volumen_hectarea = st.number_input("Volumen Hectárea", min_value=0.0, value=1.55, format="%.2f")
                    marcha = st.number_input("Marcha", min_value=0, step=1, value=18)
                    presion = st.text_input("Presión Bar", value="bares")
                with col_app2:
                    full_maquinarias = st.checkbox("Full Maquinarias", value=True)
                    num_boquillas = st.number_input("N° Boquillas Total", min_value=0, step=1, value=18)
                    color_boquilla = st.text_input("Color de Boquilla", value="q Mast")
                    cultivo = st.text_input("Cultivo", value="Vid")
                
                observaciones = st.text_area("Observaciones Generales (Clima, Novedades, etc.)", value="Aplicación con turbo y con boquillas intercaladas una negra y una marrón.")

                submitted = st.form_submit_button("🏁 Finalizar Tarea y Guardar Registros")

                if submitted and supabase:
                    if h_final <= h_inicial:
                        st.error("El Horómetro Final debe ser mayor que el Inicial.")
                    else:
                        try:
                            # 1. Preparar y guardar el registro de horas
                            total_horas = h_final - h_inicial
                            nuevo_registro_horas = {
                                'Fecha': tarea['Fecha_Programada'],
                                'Turno': tarea['Turno'], 'Operador': operario, 'Tractor': tractor_utilizado,
                                'Implemento': implemento, 'Labor_Realizada': labor_realizada, 
                                'Sector': tarea['Sector_Aplicacion'],
                                'Horometro_Inicial': h_inicial, 'Horometro_Final': h_final,
                                'Total_Horas': total_horas, 'Observaciones': observaciones
                            }
                            supabase.table('Registro_Horas_Tractor').insert(nuevo_registro_horas).execute()

                            # 2. Preparar y actualizar la orden de trabajo
                            datos_actualizacion_orden = {
                                'Status': 'Completada',
                                'Tractor_Responsable': operario,
                                'Aplicacion_Completada_Fecha': datetime.now().isoformat(),
                                'Tipo_Aplicacion': tipo_aplicacion,
                                'Volumen_Agua_Ha': volumen_agua_ha,
                                'Volumen_Hectarea': volumen_hectarea,
                                'Marcha': marcha,
                                'Presion_Bar': presion,
                                'Full_Maquinarias': full_maquinarias,
                                'Num_Boquillas_Total': num_boquillas,
                                'Color_Boquilla': color_boquilla,
                                'Cultivo': cultivo,
                                'Observaciones_Aplicacion': observaciones
                            }
                            supabase.table('Ordenes_de_Trabajo').update(datos_actualizacion_orden).eq('id', tarea['id']).execute()

                            st.success(f"¡Tarea '{tarea['ID_Orden_Personalizado']}' completada y horas registradas!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar los registros en Supabase: {e}")
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIALES Y DESCARGAS ---
st.header("📚 Historiales")

# Historial de Horas de Tractor
st.subheader("Historial de Horas de Tractor")
if not df_historial_horas.empty:
    st.dataframe(df_historial_horas, use_container_width=True)
else:
    st.info("Aún no se ha registrado ninguna hora de tractor.")

# Historial de Aplicaciones Completadas
st.subheader("Historial de Aplicaciones Completadas")
if not df_historial_apps.empty:
    columnas_a_mostrar = ['ID_Orden_Personalizado', 'Sector_Aplicacion', 'Tractor_Responsable', 'Aplicacion_Completada_Fecha']
    st.dataframe(df_historial_apps[columnas_a_mostrar], use_container_width=True)
else:
    st.info("Aún no se ha completado ninguna aplicación.")
