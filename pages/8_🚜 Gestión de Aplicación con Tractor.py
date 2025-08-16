import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time
from io import BytesIO
import openpyxl

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Aplicación", page_icon="🚜", layout="wide")
st.title("🚜 Cartilla de Aplicación con Tractor")
st.write("El operario completa la cartilla digital con los detalles de la aplicación para marcar la orden como finalizada.")

# --- NOMBRES DE ARCHIVOS ---
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'

# --- FUNCIONES ---
def cargar_ordenes():
    if os.path.exists(ORDENES_FILE):
        return pd.read_excel(ORDENES_FILE)
    cols = ['ID_Orden', 'Status', 'Fecha_Programada', 'Sector_Aplicacion', 'Objetivo', 'Receta_Mezcla_Lotes']
    return pd.DataFrame(columns=cols)

def guardar_ordenes(df):
    df.to_excel(ORDENES_FILE, index=False, engine='openpyxl')
    return True

def to_excel_detailed(tarea_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Hoja 1: Resumen
        resumen_data = {k: [v] for k, v in tarea_row.items() if not isinstance(v, (list, dict, str)) or len(str(v)) < 200}
        pd.DataFrame(resumen_data).to_excel(writer, index=False, sheet_name='Resumen_Orden')
        
        # Hoja 2: Receta
        if 'Receta_Mezcla_Lotes' in tarea_row and pd.notna(tarea_row['Receta_Mezcla_Lotes']):
            receta = json.loads(tarea_row['Receta_Mezcla_Lotes'])
            pd.DataFrame(receta).to_excel(writer, index=False, sheet_name='Receta_Detallada')

        # Hoja 3: Cartilla de Aplicación
        if 'Detalle_Aplicacion' in tarea_row and pd.notna(tarea_row['Detalle_Aplicacion']):
            detalle = json.loads(tarea_row['Detalle_Aplicacion'])
            pd.DataFrame([detalle]).T.to_excel(writer, sheet_name='Cartilla_Aplicacion')
            
    return output.getvalue()

# --- CARGA DE DATOS ---
df_ordenes = cargar_ordenes()

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
st.write("Aquí aparecen las órdenes que ya tienen la mezcla preparada.")

tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Fecha:** {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}"
        with st.expander(expander_title):
            
            st.write("**Receta de la Mezcla (Lotes a Usar):**")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_tractor_{tarea['ID_Orden']}"):
                st.subheader("Cartilla de Aplicación")
                
                # --- DATOS DE LA CARTILLA ---
                st.markdown("##### Método de Aplicación")
                col_tipo, col_vol = st.columns(2)
                with col_tipo:
                    tipo_aplicacion = st.radio("Tipo de Aplicación", ["Nebulizador (Turbo)", "Barras", "Pistolas/Drench"])
                with col_vol:
                    volumen_total = st.number_input("Volumen de Agua Total (L)", value=2200)
                    volumen_ha = st.number_input("Volumen por Hectárea", value=1200)

                st.markdown("##### Maquinaria")
                col_maq1, col_maq2, col_maq3 = st.columns(3)
                with col_maq1:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")
                    pulverizador = st.text_input("Pulverizador", "FULL MAQUINARIAS")
                with col_maq2:
                    marcha_tractor = st.text_input("Marcha / Tractor", "1ra")
                    velocidad_kmh = st.number_input("Velocidad (km/h)", value=9.0, format="%.1f")
                with col_maq3:
                    rpm = st.number_input("RPM", value=98)
                    presion_bar = st.number_input("Presión (bar)", value=9.0, format="%.1f")

                st.markdown("##### Boquillas")
                col_boq1, col_boq2 = st.columns(2)
                with col_boq1:
                    n_boquillas = st.number_input("Nº Boquillas Total", value=18)
                with col_boq2:
                    color_boquilla = st.text_input("Color de Boquilla", "Negra y Marrón")
                ubicacion_boquillas = st.text_area("Ubicación y Estado de Boquillas", "Descripción de la configuración de boquillas (ej: 2 corona, 2 centro, 2 bajas por lado)")

                st.markdown("##### Personal y Horarios")
                operario = st.text_input("Nombre del Operario / Aplicador", "Antonio Carraro")
                col_h1, col_h2 = st.columns(2)
                with col_h1: hora_inicio = st.time_input("Hora de Inicio", time(2,0))
                with col_h2: hora_fin = st.time_input("Hora Final", time(7,0))
                
                observaciones = st.text_area("Observaciones Generales", "Aplicación con turbo y con boquillas intermedias")

                submitted_tractor = st.form_submit_button("🏁 Finalizar y Guardar Aplicación")

                if submitted_tractor:
                    detalle_aplicacion = {
                        "Tipo_Aplicacion": tipo_aplicacion, "Volumen_Agua_Total_L": volumen_total, "Volumen_por_Ha": volumen_ha,
                        "Tractor": tractor_utilizado, "Pulverizador": pulverizador, "Marcha": marcha_tractor,
                        "Velocidad_KMH": velocidad_kmh, "RPM": rpm, "Presion_Bar": presion_bar,
                        "N_Boquillas": n_boquillas, "Color_Boquillas": color_boquilla, "Ubicacion_Boquillas": ubicacion_boquillas,
                        "Operario": operario, "Hora_Inicio": hora_inicio.strftime("%H:%M"), "Hora_Fin": hora_fin.strftime("%H:%M"),
                        "Observaciones": observaciones
                    }
                    
                    df_ordenes.loc[index, 'Status'] = 'Completada'
                    df_ordenes.loc[index, 'Tractor_Responsable'] = operario
                    df_ordenes.loc[index, 'Aplicacion_Completada_Fecha'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    df_ordenes.loc[index, 'Detalle_Aplicacion'] = json.dumps(detalle_aplicacion)

                    exito = guardar_ordenes(df_ordenes)
                    if exito:
                        st.success(f"¡Aplicación de la orden '{tarea['ID_Orden']}' registrada exitosamente!")
                        st.rerun()
                    else:
                        st.error("Error al guardar la actualización de la orden.")
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIAL Y DESCARGA ---
st.subheader("📚 Historial de Aplicaciones Completadas")
historial_apps = df_ordenes[df_ordenes['Status'] == 'Completada'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not historial_apps.empty:
    for index, tarea in historial_apps.sort_values(by='Aplicacion_Completada_Fecha', ascending=False).iterrows():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 2, 1])
            col1.metric("Orden ID", tarea['ID_Orden'])
            col2.metric("Sector", tarea['Sector_Aplicacion'])
            
            with col3:
                st.write("") 
                reporte_individual = to_excel_detailed(tarea)
                st.download_button(
                    label="📥 Descargar Reporte",
                    data=reporte_individual,
                    file_name=f"Reporte_Orden_{tarea['ID_Orden']}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    key=f"download_{tarea['ID_Orden']}"
                )
else:
    st.info("Aún no se ha completado ninguna aplicación.")
