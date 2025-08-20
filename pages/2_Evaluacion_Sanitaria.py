import streamlit as st
import pandas as pd
from datetime import datetime
from io import BytesIO
import json

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Evaluación Sanitaria", page_icon="🔬", layout="wide")
st.title("🔬 Evaluación Sanitaria de Campo")
st.write("Registre aquí la evaluación completa de plagas y enfermedades para un lote específico.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        client = create_client(url, key)
        return client
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        st.info("Asegúrate de haber configurado SUPABASE_URL y SUPABASE_KEY en los Secrets de tu app.")
        return None

supabase = init_supabase_connection()

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_evaluaciones_supabase():
    """Carga el historial de evaluaciones desde la tabla de Supabase."""
    if supabase:
        try:
            response = supabase.table('Evaluaciones_Sanitarias').select("*").execute()
            df = pd.DataFrame(response.data)
            return df
        except Exception as e:
            st.error(f"Error al cargar los datos de Supabase: {e}")
    return pd.DataFrame()

def to_excel_detailed(evaluacion_row):
    """Genera un reporte Excel detallado a partir de una fila de datos de Supabase."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Hoja de Resumen
        resumen_data = {
            "Fecha": [pd.to_datetime(evaluacion_row['Fecha']).strftime('%Y-%m-%d')],
            "Sector": [evaluacion_row['Sector']],
            "Evaluador": [evaluacion_row['Evaluador']]
        }
        pd.DataFrame(resumen_data).to_excel(writer, index=False, sheet_name='Resumen')
        
        # Hojas de Datos (leyendo desde las columnas jsonb)
        if 'Datos_Plagas' in evaluacion_row and evaluacion_row['Datos_Plagas']:
            pd.DataFrame(evaluacion_row['Datos_Plagas']).set_index('Planta').to_excel(writer, sheet_name='Plagas')
        if 'Datos_Enfermedades' in evaluacion_row and evaluacion_row['Datos_Enfermedades']:
            pd.DataFrame(evaluacion_row['Datos_Enfermedades']).set_index('Planta').to_excel(writer, sheet_name='Enfermedades')
        if 'Datos_Perimetro' in evaluacion_row and evaluacion_row['Datos_Perimetro']:
            pd.DataFrame(evaluacion_row['Datos_Perimetro']).set_index('Plaga/Enfermedad').to_excel(writer, sheet_name='Perimetro')
            
    return output.getvalue()

# --- INTERFAZ DE REGISTRO (CASI SIN CAMBIOS) ---
with st.expander("➕ Registrar Nueva Evaluación Sanitaria", expanded=True):
    with st.form("evaluacion_sanitaria_form"):
        st.header("1. Datos Generales de la Evaluación")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_evaluacion = st.date_input("Fecha de Evaluación", datetime.now())
        with col2:
            sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
            sector_evaluado = st.selectbox("Lote / Sector Evaluado", options=sectores_del_fundo)
        with col3:
            evaluador = st.text_input("Nombre del Evaluador")

        st.divider()
        st.header("2. Evaluación Detallada")
        
        tab_plagas, tab_enfermedades, tab_perimetro = st.tabs(["PLAGAS", "ENFERMEDADES", "PERÍMETRO"])

        with tab_plagas:
            st.subheader("Evaluación de Plagas (para 25 plantas)")
            plagas_plantilla = {
                'Planta': [f"P.{i+1}" for i in range(25)],
                'TRIPS N° Ind/Racimo': [0]*25, 'TRIPS N° Ind/Hoja': [0]*25, 'TRIPS N° Ind/Brot': [0]*25,
                'M. BLANCA % Adulto/Hoja': [0.0]*25,
                'A. ROJA % Adultos/Hoja': [0.0]*25, 'A. ROJA % Adultos/Racimo': [0.0]*25,
                'COCHINILLA H. % Hojas': [0.0]*25, 'COCHINILLA H. % Racimo': [0.0]*25,
                'PULGÓN % Hojas': [0.0]*25, 'PULGÓN % Racimo': [0.0]*25,
                'EMPOASCA N° Ind/Hoja': [0]*25
            }
            df_plagas = st.data_editor(pd.DataFrame(plagas_plantilla).set_index('Planta'), use_container_width=True, key="editor_plagas")

        with tab_enfermedades:
            st.subheader("Evaluación de Enfermedades (para 25 plantas)")
            enfermedades_plantilla = {
                'Planta': [f"P.{i+1}" for i in range(25)],
                'OIDIOSIS % Hojas': [0.0]*25, 'OIDIOSIS % Racimos': [0.0]*25,
                'MILDIU % Hojas': [0.0]*25, 'MILDIU % Rac. Floral': [0.0]*25,
                'BOTRYTIS % Racimos': [0.0]*25,
                'PUD. ACIDA % Racimos': [0.0]*25,
                'PENICILLIUM % Racimos': [0.0]*25,
                'HONG. VASC % Plantas': [0.0]*25
            }
            df_enfermedades = st.data_editor(pd.DataFrame(enfermedades_plantilla).set_index('Planta'), use_container_width=True, key="editor_enfermedades")
        
        with tab_perimetro:
            st.subheader("Evaluación de Perímetro o Lindero")
            perimetro_plantilla = {
                'Plaga/Enfermedad': ['OIDIUM', 'MILDIU', 'ARAÑITA ROJA', 'ACARO HIALINO', 'COCHINILLA HARINOSA', 'PICADURA AVES'],
                '1ER. PERIMETRO - HOJA': [0.0]*6, '1ER. PERIMETRO - RACIMOS': [0.0]*6,
                '2DO. PERIMETRO - HOJA': [0.0]*6, '2DO. PERIMETRO - RACIMOS': [0.0]*6
            }
            df_perimetro = st.data_editor(pd.DataFrame(perimetro_plantilla).set_index('Plaga/Enfermedad'), use_container_width=True, key="editor_perimetro")

        st.divider()
        submitted = st.form_submit_button("✅ Guardar Evaluación Completa")

        if submitted and supabase:
            if not evaluador or not sector_evaluado:
                st.warning("Por favor, complete los campos de Evaluador y Sector.")
            else:
                try:
                    # Preparamos los datos para insertar en Supabase
                    datos_para_insertar = {
                        "Fecha": fecha_evaluacion.strftime("%Y-%m-%d"),
                        "Sector": sector_evaluado,
                        "Evaluador": evaluador,
                        "Datos_Plagas": df_plagas.reset_index().to_dict(orient='records'),
                        "Datos_Enfermedades": df_enfermedades.reset_index().to_dict(orient='records'),
                        "Datos_Perimetro": df_perimetro.reset_index().to_dict(orient='records')
                    }
                    
                    # Insertamos el nuevo registro en la tabla de Supabase
                    supabase.table('Evaluaciones_Sanitarias').insert(datos_para_insertar).execute()
                    st.success("¡Evaluación sanitaria guardada exitosamente en Supabase!")
                    st.cache_data.clear() # Limpiamos el caché para recargar el historial
                    st.rerun()

                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}")

# --- HISTORIAL Y DESCARGA (ADAPTADO PARA SUPABASE) ---
st.divider()
st.header("📚 Historial de Evaluaciones Sanitarias")
df_historial = cargar_evaluaciones_supabase()

if df_historial is not None and not df_historial.empty:
    st.write("A continuación se muestra un resumen de las últimas evaluaciones realizadas.")
    
    # Ordenamos por fecha descendente
    df_historial['Fecha'] = pd.to_datetime(df_historial['Fecha'])
    df_historial_ordenado = df_historial.sort_values(by='Fecha', ascending=False)

    for index, evaluacion in df_historial_ordenado.head(10).iterrows():
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            col1.metric("Fecha", evaluacion['Fecha'].strftime('%d/%m/%Y'))
            col2.metric("Sector", evaluacion['Sector'])
            col3.metric("Evaluador", evaluacion['Evaluador'])
            with col4:
                st.write("") # Espacio para alinear el botón
                reporte_individual = to_excel_detailed(evaluacion)
                st.download_button(
                    label="📥 Reporte",
                    data=reporte_individual,
                    file_name=f"Reporte_Sanitario_{evaluacion['Sector']}_{evaluacion['Fecha'].strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_sanitario_{evaluacion['id']}" # Usamos el id de Supabase como clave única
                )
else:
    st.info("Aún no se ha registrado ninguna evaluación sanitaria.")
