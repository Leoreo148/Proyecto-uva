import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Tractor", page_icon="🚜", layout="wide")
st.title("🚜 Gestión de Aplicación con Tractor")
st.write("El tractorista completa los detalles de la aplicación y la marca como finalizada.")
st.info("ℹ️ **Importante:** Para finalizar una tarea y guardar los datos, necesitará conexión a internet.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_ORDENES = 'Ordenes_de_Trabajo.xlsx'

# --- FUNCIONES ---
def cargar_datos(nombre_archivo, columnas_defecto):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    else:
        return pd.DataFrame(columns=columnas_defecto)

def guardar_datos(df, nombre_archivo):
    try:
        df.to_excel(nombre_archivo, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

def to_excel_detailed(tarea_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Hoja 1: Resumen General
        resumen_data = {
            "ID Orden": [tarea_row.get('ID_Orden')],
            "Fecha Programada": [pd.to_datetime(tarea_row.get('Fecha_Programada')).strftime('%d/%m/%Y')],
            "Sector": [tarea_row.get('Sector_Aplicacion')],
            "Objetivo": [tarea_row.get('Objetivo')],
            "Mezcla Hecha por": [tarea_row.get('Mezcla_Responsable')],
            "Aplicación Hecha por": [tarea_row.get('Tractor_Responsable')],
            "Fecha Completada": [pd.to_datetime(tarea_row.get('Aplicacion_Completada')).strftime('%d/%m/%Y %H:%M')],
        }
        pd.DataFrame(resumen_data).to_excel(writer, index=False, sheet_name='Resumen')

        # Hoja 2: Receta
        if 'Receta_Mezcla' in tarea_row and pd.notna(tarea_row['Receta_Mezcla']):
            receta = json.loads(tarea_row['Receta_Mezcla'])
            pd.DataFrame(receta).to_excel(writer, index=False, sheet_name='Receta_Mezcla')

        # Hoja 3: Datos del Tractor
        if 'Tractor_Info' in tarea_row and pd.notna(tarea_row['Tractor_Info']):
            tractor_info = json.loads(tarea_row['Tractor_Info'])
            pd.DataFrame([tractor_info]).to_excel(writer, index=False, sheet_name='Datos_Tractor')
            
    return output.getvalue()

# --- Cargar datos al inicio ---
columnas_ordenes = ["ID_Orden", "Status", "Fecha_Programada", "Sector_Aplicacion", "Objetivo", "Receta_Mezcla", "Mezcla_Responsable"]
df_ordenes = cargar_datos(ARCHIVO_ORDENES, columnas_ordenes)

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
st.write("Aquí aparecen las órdenes que ya tienen la mezcla preparada.")

tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar']

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID: {tarea['ID_Orden']}** | Sector: {tarea['Sector_Aplicacion']} | Fecha: {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}"
        with st.expander(expander_title):
            
            st.write("**Receta de la Mezcla:**")
            mezcla = json.loads(tarea['Receta_Mezcla'])
            st.dataframe(pd.DataFrame(mezcla), use_container_width=True)
            st.write(f"**Mezcla preparada por:** {tarea['Mezcla_Responsable']}")
            
            with st.form(key=f"form_tractor_{tarea['ID_Orden']}"):
                st.subheader("Registro de Maquinaria y Aplicación")
                
                # Fila 1: Tipo de Aplicación y Volumen
                col_tipo, col_vol = st.columns(2)
                with col_tipo:
                    st.write("**Tipo de Aplicación**")
                    tipo_aplicacion_turbo = st.checkbox("Nebulizador (Turbo)", value=True)
                    tipo_aplicacion_barras = st.checkbox("Barras")
                with col_vol:
                    volumen_total = st.number_input("Volumen de Agua Total (L)", value=2200)
                    pulverizador = st.text_input("Pulverizador", "Full Maquinarias")

                st.divider()

                # Fila 2: Datos del Tractor
                st.write("**Datos del Tractor**")
                col_tract1, col_tract2, col_tract3 = st.columns(3)
                with col_tract1:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")
                with col_tract2:
                    velocidad_kmh = st.number_input("Velocidad (km/h)", min_value=0.0, value=9.0, format="%.1f")
                with col_tract3:
                    presion_bar = st.number_input("Presión (bar)", min_value=0.0, value=9.0, format="%.1f")

                st.divider()

                # Fila 3: Boquillas
                st.write("**Registro de Boquillas**")
                col_boq1, col_boq2 = st.columns(2)
                with col_boq1:
                    color_boquilla = st.text_input("Color de Boquilla", "Negra y Marrón")
                with col_boq2:
                    boquilla_total = st.number_input("N° Boquillas Total", min_value=0, value=18)

                st.divider()

                # Fila 4: Personal y Horarios
                st.write("**Personal y Horarios**")
                col_pers1, col_pers2, col_pers3 = st.columns(3)
                with col_pers1:
                    tractor_responsable = st.text_input("Nombre del Aplicador", "Antonio Carraro")
                with col_pers2:
                    hora_inicio = st.time_input("Hora de Inicio", time(2,0))
                with col_pers3:
                    hora_fin = st.time_input("Hora Final", time(7,0))
                
                observaciones = st.text_area("Observaciones", "Aplicación con turbo y con boquillas intermedias")

                submitted_tractor = st.form_submit_button("🏁 Finalizar y Guardar Aplicación")

                if submitted_tractor:
                    tipo_app_str = []
                    if tipo_aplicacion_turbo: tipo_app_str.append("Turbo")
                    if tipo_aplicacion_barras: tipo_app_str.append("Barras")
                    
                    tractor_info = {
                        "Tipo_Aplicacion": ", ".join(tipo_app_str),
                        "Volumen_Agua": volumen_total,
                        "Pulverizador": pulverizador,
                        "Tractor_Utilizado": tractor_utilizado,
                        "Velocidad_KMH": velocidad_kmh,
                        "Presion_Bar": presion_bar,
                        "Color_Boquilla": color_boquilla,
                        "N_Boquillas_Total": boquilla_total
                    }
                    
                    df_ordenes.loc[index, 'Status'] = 'Completada'
                    df_ordenes.loc[index, 'Tractor_Responsable'] = tractor_responsable
                    df_ordenes.loc[index, 'Tractor_Info'] = json.dumps(tractor_info)
                    df_ordenes.loc[index, 'Aplicacion_Hora_Inicio'] = hora_inicio.strftime("%H:%M")
                    df_ordenes.loc[index, 'Aplicacion_Hora_Fin'] = hora_fin.strftime("%H:%M")
                    df_ordenes.loc[index, 'Observaciones'] = observaciones
                    df_ordenes.loc[index, 'Aplicacion_Completada'] = datetime.now().strftime("%Y-%m-%d %H:%M")

                    exito, mensaje = guardar_datos(df_ordenes, ARCHIVO_ORDENES)
                    if exito:
                        st.success("¡Aplicación registrada exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {mensaje}")
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIAL Y DESCARGA ---
st.subheader("📚 Historial de Aplicaciones Completadas")
historial_tractor = df_ordenes[df_ordenes['Status'] == 'Completada']
if not historial_tractor.empty:
    for index, tarea in historial_tractor.iterrows():
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
            with col1:
                st.markdown(f"**Fecha:** {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}")
                st.markdown(f"**Sector:** {tarea['Sector_Aplicacion']}")
            with col2:
                st.markdown(f"**Objetivo:** {tarea['Objetivo']}")
                st.markdown(f"**Tractorista:** {tarea['Tractor_Responsable']}")
            with col3:
                st.markdown(f"**Mezcla por:** {tarea['Mezcla_Responsable']}")
                st.markdown(f"**Completada:** {pd.to_datetime(tarea.get('Aplicacion_Completada')).strftime('%d/%m/%y %H:%M') if pd.notna(tarea.get('Aplicacion_Completada')) else 'N/A'}")
            with col4:
                st.write("")
                reporte_individual = to_excel_detailed(tarea)
                st.download_button(label="📥 Reporte", data=reporte_individual, file_name=f"Reporte_Orden_{tarea['ID_Orden']}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"download_{tarea['ID_Orden']}")
else:
    st.info("Aún no se ha completado ninguna aplicación.")
