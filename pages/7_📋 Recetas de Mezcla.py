import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas")
st.write("El encargado confirma la preparación de las recetas, actualizando el stock y registrando la salida de productos.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Maestro.xlsx'
ARCHIVO_ORDENES = 'Ordenes_de_Trabajo.xlsx'
ARCHIVO_SALIDAS = 'Historial_Salidas.xlsx' # <-- ARCHIVO PARA EL HISTORIAL DE SALIDAS

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

# --- Cargar datos al inicio ---
df_inventario = cargar_datos(ARCHIVO_INVENTARIO, ['Codigo', 'Producto', 'Stock_Actual'])
df_ordenes = cargar_datos(ARCHIVO_ORDENES, ['ID_Orden', 'Status'])
df_salidas = cargar_datos(ARCHIVO_SALIDAS, [])

# --- SECCIÓN DE TAREAS PENDIENTES ---
st.subheader("📋 Recetas Pendientes de Preparar")
tareas_pendientes = df_ordenes[df_ordenes['Status'] == 'Pendiente de Mezcla']

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.expander(f"**Orden ID: {tarea['ID_Orden']}** | Sector: {tarea['Sector_Aplicacion']}"):
            receta = json.loads(tarea['Receta_Mezcla'])
            df_receta = pd.DataFrame(receta)
            st.dataframe(df_receta, use_container_width=True)

            with st.form(key=f"form_mezcla_{tarea['ID_Orden']}"):
                responsable_mezcla = st.text_input("Nombre del Responsable")
                submitted = st.form_submit_button("✅ Confirmar Preparación y Registrar Salida")

                if submitted:
                    if responsable_mezcla:
                        inventario_actualizado = df_inventario.copy()
                        ordenes_actualizado = df_ordenes.copy()
                        lista_salidas = []
                        stock_suficiente = True

                        for _, producto_usado in df_receta.iterrows():
                            nombre = producto_usado["Producto"]
                            cantidad_usada = producto_usado["Cantidad_Total"]
                            stock_actual = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Stock_Actual'].iloc[0]

                            if stock_actual >= cantidad_usada:
                                nuevo_stock = stock_actual - cantidad_usada
                                inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Stock_Actual'] = nuevo_stock
                                
                                # Preparar el registro para el historial de salidas
                                codigo_prod = inventario_actualizado.loc[inventario_actualizado['Producto'] == nombre, 'Codigo'].iloc[0]
                                lista_salidas.append({
                                    "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                    "ID_Orden": tarea['ID_Orden'],
                                    "Codigo_Producto": codigo_prod,
                                    "Producto": nombre,
                                    "Cantidad_Salida": cantidad_usada,
                                    "Destino": tarea['Sector_Aplicacion'],
                                    "Responsable": responsable_mezcla
                                })
                            else:
                                st.error(f"¡Stock insuficiente para '{nombre}'! Se necesitan {cantidad_usada} y solo hay {stock_actual}.")
                                stock_suficiente = False
                                break
                        
                        if stock_suficiente:
                            # Actualizar el estado de la orden
                            ordenes_actualizado.loc[index, 'Status'] = 'Lista para Aplicar'
                            ordenes_actualizado.loc[index, 'Mezcla_Responsable'] = responsable_mezcla
                            ordenes_actualizado.loc[index, 'Mezcla_Confirmada'] = datetime.now().strftime("%Y-%m-%d %H:%M")

                            # Crear y guardar el historial de salidas
                            df_salidas_nuevas = pd.DataFrame(lista_salidas)
                            df_salidas_final = pd.concat([df_salidas, df_salidas_nuevas], ignore_index=True)
                            
                            # Guardar los tres archivos
                            exito_inv, msg_inv = guardar_datos(inventario_actualizado, ARCHIVO_INVENTARIO)
                            exito_ord, msg_ord = guardar_datos(ordenes_actualizado, ARCHIVO_ORDENES)
                            exito_sal, msg_sal = guardar_datos(df_salidas_final, ARCHIVO_SALIDAS)

                            if exito_inv and exito_ord and exito_sal:
                                st.success("¡Mezcla confirmada, stock actualizado y salida registrada!")
                                st.rerun()
                            else:
                                st.error(f"Ocurrió un error al guardar. Inv: {msg_inv}, Órdenes: {msg_ord}, Salidas: {msg_sal}")
                    else:
                        st.warning("Por favor, ingrese el nombre del responsable.")
else:
    st.info("No hay recetas pendientes de preparar.")
