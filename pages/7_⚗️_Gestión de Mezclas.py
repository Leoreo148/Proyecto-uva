eimport streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
import openpyxl
from io import BytesIO

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas y Pre-Mezclas por Lote")
st.write("El ingeniero programa la receta y cálculos de pre-mezcla. El encargado confirma la preparación.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

COLS_PRODUCTOS = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
COLS_INGRESOS = ['Codigo_Lote', 'Fecha', 'Tipo', 'Proveedor', 'Factura', 'Producto', 'Codigo_Producto', 'Cantidad', 'Precio_Unitario', 'Fecha_Vencimiento']
COLS_SALIDAS = ['Fecha', 'Lote_Sector', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento', 'Codigo_Lote']

# --- FUNCIONES CORE (REUTILIZADAS) ---
def cargar_kardex():
    if os.path.exists(KARDEX_FILE):
        try:
            xls = pd.ExcelFile(KARDEX_FILE)
            df_productos = pd.read_excel(xls, sheet_name=SHEET_PRODUCTS) if SHEET_PRODUCTS in xls.sheet_names else pd.DataFrame(columns=COLS_PRODUCTOS)
            df_ingresos = pd.read_excel(xls, sheet_name=SHEET_INGRESOS) if SHEET_INGRESOS in xls.sheet_names else pd.DataFrame(columns=COLS_INGRESOS)
            df_salidas = pd.read_excel(xls, sheet_name=SHEET_SALIDAS) if SHEET_SALIDAS in xls.sheet_names else pd.DataFrame(columns=COLS_SALIDAS)
        except Exception as e:
            st.error(f"Error al leer el archivo Kardex: {e}")
            return pd.DataFrame(columns=COLS_PRODUCTOS), pd.DataFrame(columns=COLS_INGRESOS), pd.DataFrame(columns=COLS_SALIDAS)
    else:
        return pd.DataFrame(columns=COLS_PRODUCTOS), pd.DataFrame(columns=COLS_INGRESOS), pd.DataFrame(columns=COLS_SALIDAS)
    return df_productos, df_ingresos, df_salidas

def guardar_kardex(df_productos, df_ingresos, df_salidas):
    with pd.ExcelWriter(KARDEX_FILE, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name=SHEET_PRODUCTS, index=False)
        df_ingresos.to_excel(writer, sheet_name=SHEET_INGRESOS, index=False)
        df_salidas.to_excel(writer, sheet_name=SHEET_SALIDAS, index=False)
    return True

def calcular_stock_por_lote(df_ingresos, df_salidas):
    if df_ingresos.empty:
        cols_lotes = ['Codigo_Lote', 'Cantidad_Ingresada', 'Stock_Restante', 'Codigo_Producto', 'Producto', 'Precio_Unitario', 'Fecha_Vencimiento']
        return pd.DataFrame(columns=cols_lotes)
    ingresos_por_lote = df_ingresos.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Ingresada'})
    if not df_salidas.empty and 'Codigo_Lote' in df_salidas.columns:
        salidas_por_lote = df_salidas.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Consumida'})
        stock_lotes = pd.merge(ingresos_por_lote, salidas_por_lote, on='Codigo_Lote', how='left').fillna(0)
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada'] - stock_lotes['Cantidad_Consumida']
    else:
        stock_lotes = ingresos_por_lote
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada']
    lote_info = df_ingresos.drop_duplicates(subset=['Codigo_Lote'])[['Codigo_Lote', 'Codigo_Producto', 'Producto', 'Precio_Unitario', 'Fecha_Vencimiento']]
    stock_lotes_detallado = pd.merge(stock_lotes, lote_info, on='Codigo_Lote', how='left')
    return stock_lotes_detallado

def cargar_ordenes():
    if os.path.exists(ORDENES_FILE):
        return pd.read_excel(ORDENES_FILE)
    return pd.DataFrame(columns=['ID_Orden', 'Status'])

def guardar_ordenes(df):
    df.to_excel(ORDENES_FILE, index=False, engine='openpyxl')

# --- CARGA DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()
df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)
df_ordenes = cargar_ordenes()

# --- SECCIÓN 1 (INGENIERO): PROGRAMAR NUEVA RECETA ---
with st.expander("👨‍🔬 Programar Nueva Receta de Mezcla (Ingeniero)"):
    lotes_activos = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0].copy()
    opciones_lotes = []
    if not lotes_activos.empty:
        lotes_activos['Fecha_Vencimiento'] = pd.to_datetime(lotes_activos['Fecha_Vencimiento'], errors='coerce').dt.strftime('%Y-%m-%d')
        lotes_activos = lotes_activos.sort_values(by='Fecha_Vencimiento', ascending=True)
        for _, row in lotes_activos.iterrows():
            label = (f"{row['Producto']} ({row['Codigo_Lote']}) | Stock: {row['Stock_Restante']:.5f} | Vence: {row['Fecha_Vencimiento'] or 'N/A'}")
            opciones_lotes.append(label)

    with st.form("programar_form"):
        st.subheader("Datos Generales de la Orden")
        col1, col2, col3 = st.columns(3)
        with col1: fecha_aplicacion = st.date_input("Fecha Programada")
        with col2: sector_aplicacion = st.text_input("Lote / Sector de Aplicación")
        with col3: turno = st.selectbox("Turno", ["Día", "Noche"])
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control de Oídio y Trips")
        
        st.subheader("Receta y Pre-Mezcla")
        if not opciones_lotes:
            st.warning("No hay lotes con stock disponible para crear una receta.")
            productos_para_mezcla = None
        else:
            productos_para_mezcla = st.data_editor(
                pd.DataFrame([{"Lote_Seleccionado": opciones_lotes[0], "Total_Producto": 1.0, "Total_Pre_Mezcla": 10.0}]),
                num_rows="dynamic",
                column_config={
                    "Lote_Seleccionado": st.column_config.SelectboxColumn("Seleccione el Lote a Usar", options=opciones_lotes, required=True),
                    "Total_Producto": st.column_config.NumberColumn("Total Producto (kg o L)", min_value=0.00001, format="%.5f"),
                    "Agua": st.column_config.NumberColumn("Agua (L)", min_value=0.001, format="%.2f")
                    "Total_Pre_Mezcla": st.column_config.NumberColumn("Total Pre-Mezcla (L)", min_value=0.0001, format="%.2f")
                }, key="editor_mezcla_premezcla"
            )

        submitted_programar = st.form_submit_button("✅ Programar Orden de Mezcla")

        if submitted_programar and productos_para_mezcla is not None:
            receta_final = []
            error_validacion = False
            for _, row in productos_para_mezcla.iterrows():
                codigo_lote = row['Lote_Seleccionado'].split('(')[1].split(')')[0].strip()
                stock_disponible = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote]['Stock_Restante'].iloc[0]
                
                if row['Total_Producto'] > stock_disponible:
                    st.error(f"Stock insuficiente para el lote {codigo_lote}. Solicitado: {row['Total_Producto']}, Disponible: {stock_disponible}")
                    error_validacion = True
                    break
                
                if row['Total_Producto'] > row['Total_Pre_Mezcla']:
                    st.error(f"El Total de Producto ({row['Total_Producto']}) no puede ser mayor al Total de Pre-Mezcla ({row['Total_Pre_Mezcla']}).")
                    error_validacion = True
                    break

                info_lote = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote].iloc[0]
                agua_necesaria = row['Total_Pre_Mezcla'] - row['Total_Producto']
                
                receta_final.append({
                    'Codigo_Lote': codigo_lote,
                    'Producto': info_lote['Producto'],
                    'Codigo_Producto': info_lote['Codigo_Producto'],
                    'Cantidad_Usada': row['Total_Producto'],
                    'Agua_Necesaria_L': agua_necesaria,
                    'Volumen_Pre_Mezcla_L': row['Total_Pre_Mezcla']
                })
            
            if not error_validacion:
                id_orden = datetime.now().strftime("OT-%Y%m%d%H%M%S")
                nueva_orden = pd.DataFrame([{"ID_Orden": id_orden, "Status": "Pendiente de Mezcla", "Fecha_Programada": fecha_aplicacion.strftime("%Y-%m-%d"), "Sector_Aplicacion": sector_aplicacion, "Objetivo": objetivo_tratamiento, "Turno": turno, "Receta_Mezcla_Lotes": json.dumps(receta_final)}])
                df_ordenes_final = pd.concat([df_ordenes, nueva_orden], ignore_index=True)
                guardar_ordenes(df_ordenes_final)
                st.success(f"¡Orden de mezcla '{id_orden}' programada exitosamente!")
                st.rerun()

st.divider()

# --- SECCIÓN 2 (ENCARGADO): TAREAS PENDIENTES ---
st.subheader("📋 Recetas Pendientes de Preparar (Encargado de Mezcla)")
tareas_pendientes = df_ordenes[df_ordenes['Status'] == 'Pendiente de Mezcla'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.container(border=True):
            st.markdown(f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Fecha:** {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            df_receta = pd.DataFrame(receta)
            
            # Renombrar columnas para la visualización
            df_display = df_receta.rename(columns={
                'Cantidad_Usada': 'Total Producto',
                'Agua_Necesaria_L': 'Agua (L)',
                'Volumen_Pre_Mezcla_L': 'Total Pre-Mezcla (L)'
            })

            st.dataframe(
                df_display[['Producto', 'Total Producto', 'Agua (L)', 'Total Pre-Mezcla (L)']],
                use_container_width=True,
                column_config={"Total Producto": st.column_config.NumberColumn(format="%.5f")}
            )
            
            if st.button("✅ Confirmar Preparación y Registrar Salida", key=f"confirm_{tarea['ID_Orden']}"):
                nuevas_salidas = []
                for item in receta:
                    nuevas_salidas.append({'Fecha': datetime.now().strftime("%Y-%m-%d"), 'Lote_Sector': tarea['Sector_Aplicacion'], 'Turno': tarea['Turno'], 'Producto': item['Producto'], 'Cantidad': item['Cantidad_Usada'], 'Codigo_Producto': item['Codigo_Producto'], 'Objetivo_Tratamiento': tarea['Objetivo'], 'Codigo_Lote': item['Codigo_Lote']})
                df_nuevas_salidas = pd.DataFrame(nuevas_salidas)
                df_salidas_final = pd.concat([df_salidas, df_nuevas_salidas], ignore_index=True)
                guardar_kardex(df_productos, df_ingresos, df_salidas_final)
                df_ordenes.loc[index, 'Status'] = 'Lista para Aplicar'
                guardar_ordenes(df_ordenes)
                st.success(f"Salida para la orden '{tarea['ID_Orden']}' registrada. Stock actualizado.")
                st.rerun()
else:
    st.info("No hay recetas pendientes de preparar.")
