import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Tractor", page_icon="🚜", layout="wide")
st.title("🚜 Gestión de Aplicación con Tractor")
st.write("El tractorista completa los detalles de la aplicación y la marca como finalizada.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_ORDENES = 'Ordenes_de_Trabajo.xlsx'

# --- FUNCIONES PARA CARGAR Y GUARDAR DATOS ---
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

# --- Cargar datos al inicio ---
columnas_ordenes = ["ID_Orden", "Status", "Fecha_Programada", "Sector_Aplicacion", "Objetivo", "Receta_Mezcla", "Mezcla_Responsable"]
df_ordenes = cargar_datos(ARCHIVO_ORDENES, columnas_ordenes)

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
st.info("Aquí aparecen las órdenes que ya tienen la mezcla preparada.")

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
                
                # Fila 1: Datos generales de la aplicación
                col1, col2, col3 = st.columns(3)
                with col1:
                    tipo_aplicacion = st.selectbox("Tipo de Aplicación", ["Nebulizador (Turbo)", "Barras", "Pistolas/Drench"])
                with col2:
                    volumen_total = st.number_input("Volumen de Agua Total (L)", value=2200)
                with col3:
                    tractor_utilizado = st.text_input("Tractor Utilizado", "CASE")

                # Fila 2: Parámetros de la máquina
                col4, col5, col6 = st.columns(3)
                with col4:
                    presion_bar = st.number_input("Presión (bar)", min_value=0.0, value=9.0, format="%.1f")
                with col5:
                    velocidad_kmh = st.number_input("Velocidad (km/h)", min_value=0.0, value=9.0, format="%.1f")
                with col6:
                    tractor_responsable = st.text_input("Nombre del Tractorista", "Antonio Carraro")

                # Fila 3: Boquillas
                st.subheader("Ubicación y Color de Boquillas")
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    boquilla_der = st.text_input("Derecha (Color)", "Negra")
                with c2:
                    boquilla_izq = st.text_input("Izquierda (Color)", "Marrón")
                with c3:
                    boquilla_centro = st.text_input("Centro (Color)", "N/A")
                with c4:
                    boquilla_total = st.number_input("N° Boquillas Total", min_value=0, value=18)

                # Fila 4: Horarios y Observaciones
                col7, col8 = st.columns(2)
                with col7:
                    hora_inicio = st.time_input("Hora de Inicio")
                with col8:
                    hora_fin = st.time_input("Hora Final")
                
                observaciones = st.text_area("Observaciones", "Aplicación con turbo y con boquillas intermedias")

                submitted_tractor = st.form_submit_button("🏁 Finalizar y Guardar Aplicación")

                if submitted_tractor:
                    tractor_info = {
                        "Tipo_Aplicacion": tipo_aplicacion, "Volumen_Agua": volumen_total,
                        "Tractor_Utilizado": tractor_utilizado, "Presion_Bar": presion_bar,
                        "Velocidad_KMH": velocidad_kmh, "Boquilla_Derecha": boquilla_der,
                        "Boquilla_Izquierda": boquilla_izq, "Boquilla_Centro": boquilla_centro,
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

# --- HISTORIAL DE APLICACIONES COMPLETADAS ---
st.subheader("📚 Historial de Aplicaciones Completadas Recientemente")
historial_tractor = df_ordenes[df_ordenes['Status'] == 'Completada']
if not historial_tractor.empty:
    st.dataframe(
        historial_tractor[['Fecha_Programada', 'Sector_Aplicacion', 'Tractor_Responsable', 'Objetivo']].tail(10).iloc[::-1],
        use_container_width=True
    )
else:
    st.info("Aún no se ha completado ninguna aplicación.")
