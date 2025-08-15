import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas")
st.write("El ingeniero programa la receta y el encargado confirma la preparación.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Maestro.xlsx'
ARCHIVO_ORDENES = 'Ordenes_de_Trabajo.xlsx'
ARCHIVO_SALIDAS = 'Historial_Salidas.xlsx'

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

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Producto', 'Unidad', 'Stock_Actual'])
df_ordenes = cargar_datos(ARCHIVO_ORDENES, ['ID_Orden', 'Status'])
df_salidas = cargar_datos(ARCHIVO_SALIDAS, [])


# --- SECCIÓN 1 (PARA EL INGENIERO): PROGRAMAR NUEVA RECETA ---
with st.expander("👨‍🔬 Programar Nueva Receta de Mezcla (Ingeniero)"):
    with st.form("programar_form"):
        st.subheader("Datos Generales")
        col1, col2, col3 = st.columns(3)
        with col1:
            fecha_aplicacion = st.date_input("Fecha Programada")
        with col2:
            sectores_del_fundo = ['W3', 'J-3', 'W1', 'W2', 'K1', 'K2', 'General']
            sector_aplicacion = st.selectbox("Lote / Sector", options=sectores_del_fundo)
        with col3:
            turno = st.selectbox("Turno", ["Día", "Noche"])
        
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Trips - araña roja")

        st.subheader("Receta")
        if not df_inventario.empty:
            productos_disponibles = df_inventario['Producto'].tolist()
            productos_para_mezcla = st.data_editor(
                pd.DataFrame([{"Producto": productos_disponibles[0], "Cantidad Total": 1.0}]),
                num_rows="dynamic",
                column_config={
                    "Producto": st.column_config.SelectboxColumn("Producto", options=productos_disponibles, required=True),
                    "Cantidad Total": st.column_config.NumberColumn("Cantidad TOTAL a Mezclar", min_value=0.0, format="%.3f")
                },
                key="editor_mezcla"
            )
        else:
            st.warning("No hay productos en el inventario para crear una receta.")
            productos_para_mezcla = pd.DataFrame()

        submitted_programar = st.form_submit_button("✅ Programar Orden de Mezcla")

        if submitted_programar:
            if productos_para_mezcla.empty or productos_para_mezcla["Producto"].isnull().any():
                st.error("Error: La receta está vacía o incompleta.")
            else:
                productos_para_mezcla = pd.merge(productos_para_mezcla, df_inventario[['Producto', 'Unidad']], on='Producto', how='left')
                id_orden = datetime.now().strftime("%Y%m%d%H%M%S")
                receta_json = productos_para_mezcla.to_json(orient='records')
                
                nueva_orden = pd.DataFrame([{"ID_Orden": id_orden, "Status": "Pendiente de Mezcla", "Fecha_Programada": fecha_aplicacion.strftime("%Y-%m-%d"), "Sector_Aplicacion": sector_aplicacion, "Objetivo": objetivo_tratamiento, "Turno": turno, "Receta_Mezcla": receta_json}])
                
                df_ordenes_final = pd.concat([df_ordenes, nueva_orden], ignore_index=True)
                exito, mensaje = guardar_datos(df_ordenes_final, ARCHIVO_ORDENES)
                
                if exito:
                    st.success(f"¡Orden de mezcla para el sector '{sector_aplicacion}' programada!")
                else:
                    st.error(f"No se pudo programar la orden. Error: {mensaje}")

st.divider()

# --- SECCIÓN 2 (PARA EL ENCARGADO DE MEZCLA): TAREAS PENDIENTES ---
st.subheader("📋 Recetas Pendientes de Preparar (Encargado de Mezcla)")
tareas_pendientes = df_ordenes[df_ordenes['Status'] == 'Pendiente de Mezcla']

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.container(border=True):
            st.markdown(f"**Orden ID: {tarea['ID_Orden']}** | Sector: {tarea['Sector_Aplicacion']} | Fecha: {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}")
            receta = json.loads(tarea['Receta_Mezcla'])
            df_receta = pd.DataFrame(receta)
            st.dataframe(df_receta, use_container_width=True)
            
            responsable_mezcla = st.text_input("Nombre del Responsable", key=f"resp_{tarea['ID_Orden']}")
            
            if st.button("✅ Terminado: Confirmar Preparación", key=f"confirm_{tarea['ID_Orden']}"):
                if responsable_mezcla:
                    inventario_actualizado = df_inventario.copy()
                    ordenes_actualizado = df_ordenes.copy()
                    lista_salidas = []
                    error_stock = False
                    for _, producto_usado in df_receta.iterrows():
                        nombre = producto_usado["Producto"]
                        cantidad_usada = producto_usado["Cantidad Total"]
                        stock_actual = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Stock_Actual'].iloc[0]
                        if stock_actual >= cantidad_usada:
                            nuevo_stock = stock_actual - cantidad_usada
                            inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Stock_Actual'] = nuevo_stock
                            
                            codigo_prod = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Codigo'].iloc[0]
                            lista_salidas.append({"Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"), "ID_Orden": tarea['ID_Orden'], "Codigo_Producto": codigo_prod, "Producto": nombre, "Cantidad_Salida": cantidad_usada, "Responsable": responsable_mezcla, "Destino": f"Aplicación en {tarea['Sector_Aplicacion']}"})
                        else:
                            st.error(f"¡Stock insuficiente para '{nombre}'! Se necesitan {cantidad_usada} y solo hay {stock_actual}.")
                            error_stock = True
                            break
                    
                    if not error_stock:
                        ordenes_actualizado.loc[index, 'Status'] = 'Lista para Aplicar'
                        ordenes_actualizado.loc[index, 'Mezcla_Responsable'] = responsable_mezcla
                        ordenes_actualizado.loc[index, 'Mezcla_Confirmada'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        
                        df_salidas_nuevas = pd.DataFrame(lista_salidas)
                        df_salidas_final = pd.concat([df_salidas, df_salidas_nuevas], ignore_index=True)

                        exito_inv, msg_inv = guardar_datos(inventario_actualizado, ARCHIVO_INVENTARIO)
                        exito_ord, msg_ord = guardar_datos(ordenes_actualizado, ARCHIVO_ORDENES)
                        exito_sal, msg_sal = guardar_datos(df_salidas_final, ARCHIVO_SALIDAS)

                        if exito_inv and exito_ord and exito_sal:
                            st.success("¡Mezcla confirmada, stock actualizado y salida registrada!")
                            st.rerun()
                        else:
                            st.error(f"Error al guardar. Inv: {msg_inv}, Órdenes: {msg_ord}, Salidas: {msg_sal}")
                else:
                    st.warning("Por favor, ingrese el nombre del responsable.")
else:
    st.info("No hay recetas pendientes de preparar.")

st.divider()

# --- SECCIÓN 3: HISTORIAL Y DESCARGA ---
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
