import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas")
st.write("El encargado confirma la preparación de las recetas programadas por el ingeniero.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Productos.xlsx'
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

# --- Función para convertir DataFrame a Excel en memoria ---
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    processed_data = output.getvalue()
    return processed_data

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto', 'Cantidad_Stock', 'Unidad'])
df_ordenes = cargar_datos(ARCHIVO_ORDENES, ['ID_Orden', 'Status'])

# --- SECCIÓN 1: TAREAS PENDIENTES ---
st.subheader("📋 Recetas Pendientes de Preparar")

tareas_pendientes = df_ordenes[df_ordenes['Status'] == 'Pendiente de Mezcla']

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.expander(f"**Orden ID: {tarea['ID_Orden']}** | Sector: {tarea['Sector_Aplicacion']} | Fecha: {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}"):
            
            st.write("**Receta a Preparar:**")
            receta = json.loads(tarea['Receta_Mezcla'])
            df_receta = pd.DataFrame(receta)
            st.dataframe(df_receta, use_container_width=True)
            
            with st.form(key=f"form_mezcla_{tarea['ID_Orden']}"):
                responsable_mezcla = st.text_input("Nombre del Responsable de la Mezcla")
                
                submitted_confirmar = st.form_submit_button("✅ Terminado: Confirmar Preparación")

                if submitted_confirmar:
                    if responsable_mezcla:
                        inventario_actualizado = df_inventario.copy()
                        error_stock = False
                        for _, producto_usado in df_receta.iterrows():
                            nombre = producto_usado["Producto"]
                            cantidad_usada = producto_usado["Cantidad Total"]
                            stock_actual = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Cantidad_Stock'].iloc[0]
                            if stock_actual >= cantidad_usada:
                                nuevo_stock = stock_actual - cantidad_usada
                                inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Cantidad_Stock'] = nuevo_stock
                            else:
                                st.error(f"¡Stock insuficiente para '{nombre}'! Se necesitan {cantidad_usada} y solo hay {stock_actual}.")
                                error_stock = True
                                break
                    
                        if not error_stock:
                            df_ordenes.loc[index, 'Status'] = 'Lista para Aplicar'
                            df_ordenes.loc[index, 'Mezcla_Responsable'] = responsable_mezcla
                            df_ordenes.loc[index, 'Mezcla_Confirmada'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                            
                            exito_inv, msg_inv = guardar_datos(inventario_actualizado, ARCHIVO_INVENTARIO)
                            exito_ord, msg_ord = guardar_datos(df_ordenes, ARCHIVO_ORDENES)

                            if exito_inv and exito_ord:
                                st.success("¡Mezcla confirmada y stock actualizado!")
                                st.rerun()
                            else:
                                st.error(f"Error al guardar. Inventario: {msg_inv}, Órdenes: {msg_ord}")
                    else:
                        st.warning("Por favor, ingrese el nombre del responsable.")
else:
    st.info("No hay recetas pendientes de preparar.")

st.divider()

# --- SECCIÓN 2: HISTORIAL Y DESCARGA ---
st.subheader("📚 Historial de Mezclas Preparadas")
historial_mezclas = df_ordenes[df_ordenes['Status'] != 'Pendiente de Mezcla']
if not historial_mezclas.empty:
    columnas_a_mostrar = ['Fecha_Programada', 'Sector_Aplicacion', 'Mezcla_Responsable', 'Status']
    columnas_existentes = [col for col in columnas_a_mostrar if col in historial_mezclas.columns]
    st.dataframe(historial_mezclas[columnas_existentes].tail(10).iloc[::-1], use_container_width=True)
    
    df_para_descargar = to_excel(historial_mezclas)
    st.download_button(
        label="📥 Descargar Historial Completo de Mezclas",
        data=df_para_descargar,
        file_name="Historial_Mezclas.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("Aún no se ha preparado ninguna mezcla.")
