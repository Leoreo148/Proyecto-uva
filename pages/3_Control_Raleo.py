import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Control de Raleo", page_icon="✂️", layout="wide")
st.title("✂️ Control de Avance de Raleo")
st.write("Registre el avance del personal por tandas verificadas para un control más preciso.")

# --- CONSTANTES ---
# Define aquí cuántos racimos promedio se consideran por cada tanda completada.
RACIMOS_POR_TANDA = 100

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
def cargar_raleo_supabase():
    """Carga el historial de raleo desde la tabla de Supabase."""
    if supabase:
        try:
            response = supabase.table('Control_Raleo').select("*").execute()
            df = pd.DataFrame(response.data)
            return df
        except Exception as e:
            st.error(f"Error al cargar los datos de Supabase: {e}")
    return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Raleo')
    return output.getvalue()

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Cartilla de Raleo por Tandas", expanded=True):
    st.subheader("1. Definir la Jornada y Evaluador")
    col1, col2, col3 = st.columns(3)
    with col1:
        fecha_jornada = st.date_input("Fecha de la Jornada", datetime.now())
    with col2:
        sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_trabajado = st.selectbox("Sector Trabajado", options=sectores_del_fundo)
    with col3:
        evaluador = st.text_input("Nombre del Evaluador", placeholder="Ej: Carlos")

    st.subheader("2. Registrar Avance del Personal")
    st.info(f"Ingrese el número de tandas completadas por cada trabajador. La app calculará los racimos estimados ({RACIMOS_POR_TANDA} por tanda).")
    
    df_plantilla = pd.DataFrame(
        [{"Nombre del Trabajador": "", "Tandas Completadas": 0} for _ in range(30)]
    )
    
    df_editada = st.data_editor(
        df_plantilla,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Nombre del Trabajador": st.column_config.TextColumn("Nombre del Trabajador", required=True),
            "Tandas Completadas": st.column_config.NumberColumn("N° de Tandas Completadas", min_value=0, step=1)
        }
    )

    if st.button("✅ Guardar Jornada de Raleo"):
        if not evaluador:
            st.warning("Por favor, ingrese el nombre del evaluador.")
        else:
            df_final_jornada = df_editada[df_editada["Nombre del Trabajador"] != ""].copy()
            
            if not df_final_jornada.empty:
                # Añadir los datos de la jornada a cada registro
                df_final_jornada['Fecha'] = fecha_jornada.strftime("%Y-%m-%d")
                df_final_jornada['Sector'] = sector_trabajado
                df_final_jornada['Evaluador'] = evaluador
                
                # Calcular los racimos estimados
                df_final_jornada['Racimos_Estimados'] = df_final_jornada['Tandas Completadas'] * RACIMOS_POR_TANDA
                
                # Renombrar columnas para que coincidan con Supabase
                df_final_jornada = df_final_jornada.rename(columns={
                    "Nombre del Trabajador": "Nombre_del_Trabajador",
                    "Tandas Completadas": "Tandas_Completadas"
                })
                
                # Seleccionar y reordenar las columnas finales
                columnas_finales = ['Fecha', 'Sector', 'Evaluador', 'Nombre_del_Trabajador', 'Tandas_Completadas', 'Racimos_Estimados']
                df_para_insertar = df_final_jornada[columnas_finales]

                try:
                    # Convertir el DataFrame a una lista de diccionarios para la inserción
                    registros_para_insertar = df_para_insertar.to_dict(orient='records')
                    
                    # Insertar los registros en la tabla de Supabase
                    supabase.table('Control_Raleo').insert(registros_para_insertar).execute()
                    st.success("¡Jornada de raleo guardada exitosamente en Supabase!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")
            else:
                st.warning("No se ingresaron datos de trabajadores.")

# --- HISTORIAL Y DESCARGA ---
st.divider()
st.subheader("📚 Historial de Jornadas de Raleo")
df_historial = cargar_raleo_supabase()

if df_historial is not None and not df_historial.empty:
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    jornadas = df_historial.groupby(['Fecha', 'Sector', 'Evaluador']).size().reset_index(name='counts')
    
    st.write("A continuación se muestra un resumen de las últimas jornadas registradas.")

    for index, jornada in jornadas.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            df_jornada_actual = df_historial[
                (df_historial['Fecha'] == jornada['Fecha']) & 
                (df_historial['Sector'] == jornada['Sector']) &
                (df_historial['Evaluador'] == jornada['Evaluador'])
            ]
            
            total_tandas = df_jornada_actual['Tandas_Completadas'].sum()
            total_racimos_estimados = df_jornada_actual['Racimos_Estimados'].sum()
            
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 2, 1])
            col1.metric("Fecha", jornada['Fecha'].strftime('%d/%m/%Y'))
            col2.metric("Sector", jornada['Sector'])
            col3.metric("Evaluador", jornada['Evaluador'])
            col4.metric("Total Racimos Estimados", f"{total_racimos_estimados}")

            with col5:
                st.write("")
                reporte_individual = to_excel(df_jornada_actual)
                st.download_button(
                    label="📥 Detalle",
                    data=reporte_individual,
                    file_name=f"Reporte_Raleo_{jornada['Sector']}_{jornada['Fecha'].strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_raleo_{index}"
                )
else:
    st.info("Aún no se ha registrado ninguna jornada de raleo.")
