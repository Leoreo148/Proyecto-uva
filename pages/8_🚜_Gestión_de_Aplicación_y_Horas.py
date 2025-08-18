import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time, timedelta
from io import BytesIO
import openpyxl

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Aplicación y Horas", page_icon="🚜", layout="wide")
st.title("🚜 Cartilla de Aplicación y Control de Horas")
st.write("El operario completa la cartilla unificada para finalizar la aplicación y registrar las horas de maquinaria.")

# --- NOMBRES DE ARCHIVOS ---
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'
ARCHIVO_HORAS = 'Registro_Horas_Tractor.xlsx'

# --- FUNCIONES ---
def cargar_datos(nombre_archivo, columnas_defecto):
    if os.path.exists(nombre_archivo):
        df = pd.read_excel(nombre_archivo)
        # Asegurar que las columnas de fecha se lean correctamente
        for col in df.columns:
            if 'fecha' in col.lower():
                df[col] = pd.to_datetime(df[col])
        return df
    return pd.DataFrame(columns=columnas_defecto)

def guardar_datos(df, nombre_archivo):
    df.to_excel(nombre_archivo, index=False, engine='openpyxl')
    return True

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA DE DATOS ---
df_ordenes = cargar_datos(ORDENES_FILE, ['ID_Orden', 'Status'])
df_horas = cargar_datos(ARCHIVO_HORAS, [])

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']}"
        with st.expander(expander_title, expanded=True):
            st.write("**Receta de la Mezcla:**")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_unificado_{tarea['ID_Orden']}"):
                st.subheader("Cartilla Unificada de Aplicación y Horas")
                
                # --- DATOS DEL CONTROL DE HORAS ---
                st.markdown("##### Parte Diario de Maquinaria")
                col_parte1, col_parte2 = st.columns(2)
                with col_parte1:
                    operario = st.text_input("Nombre del Operador", value=tarea.get('Tractor_Responsable', 'Antonio Cornejo'))
                    implemento = st.text_input("Implemento Utilizado", "Nebulizadora")
                with col_parte2:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")
                    labor_realizada = st.text_input("Labor Realizada", value=f"Aplicación {tarea['Objetivo']}")

                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    h_inicial = st.number_input("Horómetro Inicial", min_value=0.0, format="%.2f", step=0.1)
                with col_h2:
                    h_final = st.number_input("Horómetro Final", min_value=0.0, format="%.2f", step=0.1)

                # --- DATOS DE LA CARTILLA DE APLICACIÓN (Según las imágenes) ---
                st.markdown("##### Detalles de la Aplicación")

                col_app1, col_app2 = st.columns(2)
                with col_app1:
                    tipo_aplicacion = st.selectbox(
                        "Tipo de Aplicación",
                        ["Pulverizado (Turbo)", "Nebulizado (Turbo)", "Pistolas/Winch", "Inyectores", "Foliar", "Drench"],
                        index=0
                    )
                    volumen_agua_ha = st.number_input("Volumen de Agua / Ha (L)", min_value=0, value=2200)
                    volumen_hectarea = st.number_input("Volumen Hectárea", min_value=0.0, value=1.55, format="%.2f")
                    rpm = st.number_input("RPM", min_value=0, step=1, value=9)
                    color_boquilla = st.text_input("Color de Boquilla", value="q Mast")
                
                with col_app2:
                    full_maquinarias = st.checkbox("Full Maquinarias", value=True)
                    num_boquillas = st.number_input("N° Boquillas Total", min_value=0, step=1, value=18)
                    presion_a = st.text_input("Presión Bar A", value="neg")
                    presion_b = st.text_input("Presión Bar B", value="neg")
                
                observaciones = st.text_area(
                    "Observaciones Generales (Clima, Novedades, etc.)",
                    value="Aplicación con turbo y con boquillas intercaladas una negra y una marrón."
                )

                submitted = st.form_submit_button("🏁 Finalizar Tarea y Guardar Registros")

                if submitted:
                    if h_final <= h_inicial:
                        st.error("El Horómetro Final debe ser mayor que el Inicial.")
                    else:
                        # 1. Guardar el registro de horas
                        total_horas = h_final - h_inicial
                        nuevo_registro_horas = pd.DataFrame([{
                            'Fecha': pd.to_datetime(tarea['Fecha_Programada']),
                            'Turno': tarea['Turno'], 'Operador': operario, 'Tractor': tractor_utilizado,
                            'Implemento': implemento, 'Labor Realizada': labor_realizada, 
                            'Sector': tarea['Sector_Aplicacion'],
                            'Horometro_Inicial': h_inicial, 'Horometro_Final': h_final,
                            'Total_Horas': total_horas, 'Observaciones': observaciones
                        }])
                        df_horas_actualizado = pd.concat([df_horas, nuevo_registro_horas], ignore_index=True)
                        guardar_datos(df_horas_actualizado, ARCHIVO_HORAS)

                        # 2. Actualizar la orden de trabajo con todos los datos del formulario
                        df_ordenes.loc[index, 'Status'] = 'Completada'
                        df_ordenes.loc[index, 'Tractor_Responsable'] = operario
                        df_ordenes.loc[index, 'Aplicacion_Completada_Fecha'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        # Guardar los nuevos campos de la cartilla de aplicación
                        df_ordenes.loc[index, 'Tipo_Aplicacion'] = tipo_aplicacion
                        df_ordenes.loc[index, 'Volumen_Agua_Ha'] = volumen_agua_ha
                        df_ordenes.loc[index, 'Volumen_Hectarea'] = volumen_hectarea
                        df_ordenes.loc[index, 'RPM_Aplicacion'] = rpm
                        df_ordenes.loc[index, 'Color_Boquilla'] = color_boquilla
                        df_ordenes.loc[index, 'Full_Maquinarias'] = full_maquinarias
                        df_ordenes.loc[index, 'Num_Boquillas_Total'] = num_boquillas
                        df_ordenes.loc[index, 'Presion_Bar_A'] = presion_a
                        df_ordenes.loc[index, 'Presion_Bar_B'] = presion_b
                        df_ordenes.loc[index, 'Observaciones_Aplicacion'] = observaciones
                        
                        guardar_datos(df_ordenes, ORDENES_FILE)

                        st.success(f"¡Tarea '{tarea['ID_Orden']}' completada y horas registradas!")
                        st.rerun()
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIALES Y DESCARGAS ---
st.header("📚 Historiales")

# Historial de Horas de Tractor
st.subheader("Historial de Horas de Tractor")
df_historial_horas = cargar_datos(ARCHIVO_HORAS, [])
if not df_historial_horas.empty:
    st.dataframe(df_historial_horas.sort_values(by="Fecha", ascending=False), use_container_width=True)
    excel_horas = to_excel(df_historial_horas)
    st.download_button(
        label="📥 Descargar Historial de Horas",
        data=excel_horas,
        file_name=f"Reporte_Horas_Tractor_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )
else:
    st.info("Aún no se ha registrado ninguna hora de tractor.")

# Historial de Aplicaciones Completadas
st.subheader("Historial de Aplicaciones Completadas")
historial_apps = df_ordenes[df_ordenes['Status'] == 'Completada'] if 'Status' in df_ordenes.columns else pd.DataFrame()
if not historial_apps.empty:
    st.dataframe(historial_apps[['ID_Orden', 'Sector_Aplicacion', 'Tractor_Responsable', 'Aplicacion_Completada_Fecha']], use_container_width=True)
else:
    st.info("Aún no se ha completado ninguna aplicación.")
    return output.getvalue()

# --- CARGA DE DATOS ---
df_ordenes = cargar_datos(ORDENES_FILE, ['ID_Orden', 'Status'])
df_horas = cargar_datos(ARCHIVO_HORAS, [])

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']}"
        with st.expander(expander_title, expanded=True):
            st.write("**Receta de la Mezcla:**")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_unificado_{tarea['ID_Orden']}"):
                st.subheader("Cartilla Unificada de Aplicación y Horas")
                
                # --- DATOS DEL CONTROL DE HORAS ---
                st.markdown("##### Parte Diario de Maquinaria")
                col_parte1, col_parte2 = st.columns(2)
                with col_parte1:
                    operario = st.text_input("Nombre del Operador", value=tarea.get('Tractor_Responsable', 'Antonio Cornejo'))
                    implemento = st.text_input("Implemento Utilizado", "Nebulizadora")
                with col_parte2:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")
                    labor_realizada = st.text_input("Labor Realizada", value=f"Aplicación {tarea['Objetivo']}")

                col_h1, col_h2 = st.columns(2)
                with col_h1:
                    h_inicial = st.number_input("Horómetro Inicial", min_value=0.0, format="%.2f", step=0.1)
                with col_h2:
                    h_final = st.number_input("Horómetro Final", min_value=0.0, format="%.2f", step=0.1)

                # --- INICIO DE LA MODIFICACIÓN ---
                # --- DATOS DE LA CARTILLA DE APLICACIÓN (Según las imágenes) ---
                st.markdown("##### Detalles de la Aplicación")

                col_app1, col_app2 = st.columns(2)
                with col_app1:
                    tipo_aplicacion = st.selectbox(
                        "Tipo de Aplicación",
                        ["Pulverizado (Turbo)", "Nebulizado (Turbo)", "Pistolas/Winch", "Inyectores", "Foliar", "Drench"],
                        index=0 # 'Pulverizado (Turbo)' por defecto
                    )
                    volumen_agua_ha = st.number_input("Volumen de Agua / Ha (L)", min_value=0, value=2200)
                    volumen_hectarea = st.number_input("Volumen Hectárea", min_value=0.0, value=1.55, format="%.2f")
                    rpm = st.number_input("RPM", min_value=0, step=1, value=9)
                    color_boquilla = st.text_input("Color de Boquilla", value="q Mast")
                
                with col_app2:
                    full_maquinarias = st.checkbox("Full Maquinarias", value=True)
                    num_boquillas = st.number_input("N° Boquillas Total", min_value=0, step=1, value=18)
                    presion_a = st.text_input("Presión Bar A", value="neg")
                    presion_b = st.text_input("Presión Bar B", value="neg")
                
                observaciones = st.text_area(
                    "Observaciones Generales (Clima, Novedades, etc.)",
                    value="Aplicación con turbo y con boquillas intercaladas una negra y una marrón."
                )
                # --- FIN DE LA MODIFICACIÓN ---


                submitted = st.form_submit_button("🏁 Finalizar Tarea y Guardar Registros")

                if submitted:
                    if h_final <= h_inicial:
                        st.error("El Horómetro Final debe ser mayor que el Inicial.")
                    else:
                        # 1. Guardar el registro de horas
                        total_horas = h_final - h_inicial
                        nuevo_registro_horas = pd.DataFrame([{
                            'Fecha': pd.to_datetime(tarea['Fecha_Programada']),
                            'Turno': tarea['Turno'], 'Operador': operario, 'Tractor': tractor_utilizado,
                            'Implemento': implemento, 'Labor Realizada': labor_realizada, 
                            'Sector': tarea['Sector_Aplicacion'],
                            'Horometro_Inicial': h_inicial, 'Horometro_Final': h_final,
                            'Total_Horas': total_horas, 'Observaciones': observaciones
                        }])
                        df_horas_actualizado = pd.concat([df_horas, nuevo_registro_horas], ignore_index=True)
                        guardar_datos(df_horas_actualizado, ARCHIVO_HORAS)

                        # --- INICIO DE LA MODIFICACIÓN (Guardado de datos) ---
                        # 2. Actualizar la orden de trabajo con todos los datos del formulario
                        df_ordenes.loc[index, 'Status'] = 'Completada'
                        df_ordenes.loc[index, 'Tractor_Responsable'] = operario
                        df_ordenes.loc[index, 'Aplicacion_Completada_Fecha'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        # Guardar los nuevos campos de la cartilla de aplicación
                        df_ordenes.loc[index, 'Tipo_Aplicacion'] = tipo_aplicacion
                        df_ordenes.loc[index, 'Volumen_Agua_Ha'] = volumen_agua_ha
                        df_ordenes.loc[index, 'Volumen_Hectarea'] = volumen_hectarea
                        df_ordenes.loc[index, 'RPM_Aplicacion'] = rpm
                        df_ordenes.loc[index, 'Color_Boquilla'] = color_boquilla
                        df_ordenes.loc[index, 'Full_Maquinarias'] = full_maquinarias
                        df_ordenes.loc[index, 'Num_Boquillas_Total'] = num_boquillas
                        df_ordenes.loc[index, 'Presion_Bar_A'] = presion_a
                        df_ordenes.loc[index, 'Presion_Bar_B'] = presion_b
                        df_ordenes.loc[index, 'Observaciones_Aplicacion'] = observaciones
                        # --- FIN DE LA MODIFICACIÓN (Guardado de datos) ---
                        
                        guardar_datos(df_ordenes, ORDENES_FILE)

                        st.success(f"¡Tarea '{tarea['ID_Orden']}' completada y horas registradas!")
                        st.rerun()
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIALES Y DESCARGAS ---
st.header("📚 Historiales")

# Historial de Horas de Tractor
st.subheader("Historial de Horas de Tractor")
df_historial_horas = cargar_datos(ARCHIVO_HORAS, [])
if not df_historial_horas.empty:
    st.dataframe(df_historial_horas.sort_values(by="Fecha", ascending=False), use_container_width=True)
    excel_horas = to_excel(df_historial_horas)
    st.download_button(
        label="📥 Descargar Historial de Horas",
        data=excel_horas,
        file_name=f"Reporte_Horas_Tractor_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )
else:
    st.info("Aún no se ha registrado ninguna hora de tractor.")

# Historial de Aplicaciones Completadas
st.subheader("Historial de Aplicaciones Completadas")
historial_apps = df_ordenes[df_ordenes['Status'] == 'Completada'] if 'Status' in df_ordenes.columns else pd.DataFrame()
if not historial_apps.empty:
    st.dataframe(historial_apps[['ID_Orden', 'Sector_Aplicacion', 'Tractor_Responsable', 'Aplicacion_Completada_Fecha']], use_container_width=True)
else:
    st.info("Aún no se ha completado ninguna aplicación.")

    return output.getvalue()

# --- CARGA DE DATOS ---
df_ordenes = cargar_datos(ORDENES_FILE, ['ID_Orden', 'Status'])
df_horas = cargar_datos(ARCHIVO_HORAS, [])

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']}"
        with st.expander(expander_title, expanded=True):
            st.write("**Receta de la Mezcla:**")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_unificado_{tarea['ID_Orden']}"):
                st.subheader("Cartilla Unificada de Aplicación y Horas")
                
                # --- DATOS DEL CONTROL DE HORAS ---
                st.markdown("##### Parte Diario de Maquinaria")
                col_parte1, col_parte2 = st.columns(2)
                with col_parte1:
                    operario = st.text_input("Nombre del Operador", value=tarea.get('Tractor_Responsable', ''))
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
                observaciones = st.text_area("Observaciones Generales (Clima, Novedades, etc.)")

                submitted = st.form_submit_button("🏁 Finalizar Tarea y Guardar Registros")

                if submitted:
                    if h_final <= h_inicial:
                        st.error("El Horómetro Final debe ser mayor que el Inicial.")
                    else:
                        # 1. Guardar el registro de horas
                        total_horas = h_final - h_inicial
                        nuevo_registro_horas = pd.DataFrame([{
                            'Fecha': pd.to_datetime(tarea['Fecha_Programada']),
                            'Turno': tarea['Turno'], 'Operador': operario, 'Tractor': tractor_utilizado,
                            'Implemento': implemento, 'Labor Realizada': labor_realizada, 
                            'Sector': tarea['Sector_Aplicacion'],
                            'Horometro_Inicial': h_inicial, 'Horometro_Final': h_final,
                            'Total_Horas': total_horas, 'Observaciones': observaciones
                        }])
                        df_horas_actualizado = pd.concat([df_horas, nuevo_registro_horas], ignore_index=True)
                        guardar_datos(df_horas_actualizado, ARCHIVO_HORAS)

                        # 2. Actualizar la orden de trabajo
                        df_ordenes.loc[index, 'Status'] = 'Completada'
                        df_ordenes.loc[index, 'Tractor_Responsable'] = operario
                        df_ordenes.loc[index, 'Aplicacion_Completada_Fecha'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        df_ordenes.loc[index, 'Observaciones_Aplicacion'] = observaciones
                        guardar_datos(df_ordenes, ORDENES_FILE)

                        st.success(f"¡Tarea '{tarea['ID_Orden']}' completada y horas registradas!")
                        st.rerun()
else:
    st.info("No hay aplicaciones con mezcla lista para ser aplicadas.")

st.divider()

# --- HISTORIALES Y DESCARGAS ---
st.header("📚 Historiales")

# Historial de Horas de Tractor
st.subheader("Historial de Horas de Tractor")
df_historial_horas = cargar_datos(ARCHIVO_HORAS, [])
if not df_historial_horas.empty:
    st.dataframe(df_historial_horas.sort_values(by="Fecha", ascending=False), use_container_width=True)
    excel_horas = to_excel(df_historial_horas)
    st.download_button(
        label="📥 Descargar Historial de Horas",
        data=excel_horas,
        file_name=f"Reporte_Horas_Tractor_{datetime.now().strftime('%Y%m%d')}.xlsx"
    )
else:
    st.info("Aún no se ha registrado ninguna hora de tractor.")

# Historial de Aplicaciones Completadas
st.subheader("Historial de Aplicaciones Completadas")
historial_apps = df_ordenes[df_ordenes['Status'] == 'Completada'] if 'Status' in df_ordenes.columns else pd.DataFrame()
if not historial_apps.empty:
    st.dataframe(historial_apps[['ID_Orden', 'Sector_Aplicacion', 'Tractor_Responsable', 'Aplicacion_Completada_Fecha']], use_container_width=True)
else:
    st.info("Aún no se ha completado ninguna aplicación.")
