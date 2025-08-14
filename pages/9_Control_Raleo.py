import streamlit as st
import pandas as pd
import os
from datetime import datetime
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Control de Raleo", page_icon="✂️", layout="wide")
st.title("✂️ Control de Avance de Raleo")
st.write("Registre el avance diario del personal de raleo en los diferentes sectores.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_RALEO = 'Registro_Raleo.xlsx'

# --- FUNCIONES ---
def cargar_datos_excel():
    if os.path.exists(ARCHIVO_RALEO):
        return pd.read_excel(ARCHIVO_RALEO)
    return None

def guardar_datos_excel(df_nuevos):
    try:
        df_existente = cargar_datos_excel()
        df_final = pd.concat([df_existente, df_nuevos], ignore_index=True) if df_existente is not None else df_nuevos
        df_final.to_excel(ARCHIVO_RALEO, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Raleo')
    return output.getvalue()

# --- INTERFAZ DE REGISTRO ---
with st.expander("➕ Registrar Nueva Cartilla de Raleo"):
    st.subheader("1. Definir la Jornada")
    col1, col2 = st.columns(2)
    with col1:
        fecha_jornada = st.date_input("Fecha de la Jornada", datetime.now())
    with col2:
        sectores_del_fundo = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_trabajado = st.selectbox("Sector Trabajado", options=sectores_del_fundo)

    st.subheader("2. Registrar Avance del Personal")
    # Creamos una plantilla para 30 trabajadores
    df_plantilla = pd.DataFrame(
        [{"Nombre del Trabajador": "", "Racimos Raleados": 0} for _ in range(30)]
    )
    
    # Usamos st.data_editor para una interfaz tipo Excel
    df_editada = st.data_editor(
        df_plantilla,
        num_rows="dynamic", # Permite añadir o quitar filas
        use_container_width=True,
        column_config={
            "Nombre del Trabajador": st.column_config.TextColumn("Nombre del Trabajador", required=True),
            "Racimos Raleados": st.column_config.NumberColumn("Racimos Raleados", min_value=0, step=1)
        }
    )

    if st.button("✅ Guardar Jornada de Raleo"):
        # Filtramos para quedarnos solo con las filas donde se ingresó un nombre
        df_final_jornada = df_editada[df_editada["Nombre del Trabajador"] != ""].copy()
        
        if not df_final_jornada.empty:
            df_final_jornada['Fecha'] = fecha_jornada.strftime("%Y-%m-%d")
            df_final_jornada['Sector'] = sector_trabajado
            
            # Reordenamos las columnas
            df_final_jornada = df_final_jornada[['Fecha', 'Sector', 'Nombre del Trabajador', 'Racimos Raleados']]

            exito, mensaje = guardar_datos_excel(df_final_jornada)

            if exito:
                st.success("¡Jornada de raleo guardada exitosamente!")
            else:
                st.error(f"Error al guardar: {mensaje}")
        else:
            st.warning("No se ingresaron datos de trabajadores.")

# --- HISTORIAL Y DESCARGA ---
st.divider()
st.subheader("📚 Historial de Jornadas de Raleo")
df_historial = cargar_datos_excel()

if df_historial is not None and not df_historial.empty:
    # Agrupar por fecha y sector para identificar cada jornada
    jornadas = df_historial.groupby(['Fecha', 'Sector']).size().reset_index(name='counts')
    
    st.write("A continuación se muestra un resumen de las últimas jornadas registradas.")

    for index, jornada in jornadas.sort_values(by='Fecha', ascending=False).head(10).iterrows():
        with st.container(border=True):
            df_jornada_actual = df_historial[(df_historial['Fecha'] == jornada['Fecha']) & (df_historial['Sector'] == jornada['Sector'])]
            
            total_personal = len(df_jornada_actual)
            total_racimos = df_jornada_actual['Racimos Raleados'].sum()
            
            col1, col2, col3, col4 = st.columns([2, 1, 2, 1])
            col1.metric("Fecha", pd.to_datetime(jornada['Fecha']).strftime('%d/%m/%Y'))
            col2.metric("Sector", jornada['Sector'])
            col3.metric("Total Racimos Raleados", f"{total_racimos}")

            with col4:
                st.write("")
                reporte_individual = to_excel(df_jornada_actual)
                st.download_button(
                    label="📥 Descargar Detalle",
                    data=reporte_individual,
                    file_name=f"Reporte_Raleo_{jornada['Sector']}_{pd.to_datetime(jornada['Fecha']).strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_raleo_{jornada['Fecha']}_{jornada['Sector']}"
                )
else:
    st.info("Aún no se ha registrado ninguna jornada de raleo.")
