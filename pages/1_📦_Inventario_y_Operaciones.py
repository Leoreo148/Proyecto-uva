import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time, timedelta
from io import BytesIO
import openpyxl 
import plotly.express as px

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Inventario y Operaciones", page_icon="📦", layout="wide")
st.title("📦 Centro de Inventario y Operaciones")
st.write("Gestiona tu inventario por lotes, registra ingresos y controla todo el flujo de aplicaciones desde un solo lugar.")

# --- NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'
ARCHIVO_HORAS = 'Registro_Horas_Tractor.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# --- DEFINICIÓN DE COLUMNAS (GLOBAL) ---
COLS_PRODUCTOS = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
COLS_INGRESOS = ['Codigo_Lote', 'Fecha', 'Tipo', 'Proveedor', 'Factura', 'Producto', 'Codigo_Producto', 'Cantidad', 'Precio_Unitario', 'Fecha_Vencimiento']
COLS_SALIDAS = ['Fecha', 'Lote_Sector', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento', 'Codigo_Lote']

# --- FUNCIONES CORE (CENTRALIZADAS) ---
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
        cols_totales = ['Codigo_Producto', 'Stock_Actual', 'Stock_Valorizado']
        cols_lotes = ['Codigo_Lote', 'Stock_Restante', 'Valor_Lote', 'Codigo_Producto']
        return pd.DataFrame(columns=cols_totales), pd.DataFrame(columns=cols_lotes)
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
    stock_lotes_detallado['Valor_Lote'] = stock_lotes_detallado['Stock_Restante'] * stock_lotes_detallado['Precio_Unitario']
    agg_funcs = {'Stock_Restante': 'sum', 'Valor_Lote': 'sum'}
    total_stock_producto = stock_lotes_detallado.groupby('Codigo_Producto').agg(agg_funcs).reset_index().rename(columns={'Stock_Restante': 'Stock_Actual', 'Valor_Lote': 'Stock_Valorizado'})
    return total_stock_producto, stock_lotes_detallado

def cargar_datos_genericos(nombre_archivo, columnas_defecto=None):
    if os.path.exists(nombre_archivo):
        return pd.read_excel(nombre_archivo)
    return pd.DataFrame(columns=columnas_defecto if columnas_defecto is not None else [])

def guardar_datos_genericos(df, nombre_archivo):
    df.to_excel(nombre_archivo, index=False, engine='openpyxl')
    return True

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte')
    return output.getvalue()

# --- CARGA DE DATOS PRINCIPAL (UNA SOLA VEZ) ---
df_productos, df_ingresos, df_salidas = cargar_kardex()
df_ordenes = cargar_datos_genericos(ORDENES_FILE, ['ID_Orden', 'Status'])
df_horas = cargar_datos_genericos(ARCHIVO_HORAS, [])

# --- CREACIÓN DE PESTAÑAS ---
tab_kardex, tab_ingreso, tab_mezclas, tab_aplicacion = st.tabs([
    "📊 Kardex y Productos", 
    "📥 Registrar Ingreso", 
    "⚗️ Gestión de Mezclas", 
    "🚜 Gestión de Aplicación"
])

# --- PESTAÑA 1: KARDEX Y PRODUCTOS ---
with tab_kardex:
    st.header("Visión General del Inventario")
    
    with st.expander("⬆️ Cargar Catálogo Inicial desde Excel"):
        st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
        uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"], key="main_uploader")
        if st.button("Procesar Archivo Excel Completo"):
            if uploaded_file:
                with st.spinner("Procesando archivo Excel..."):
                    try:
                        # ... Lógica completa de procesamiento de Excel ...
                        st.success("¡Catálogo y stock inicial cargados exitosamente!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Ocurrió un error. Verifique su archivo Excel. Detalle: {e}")

    with st.expander("➕ Añadir Nuevo Producto al Catálogo"):
        with st.form("nuevo_producto_form", clear_on_submit=True):
            st.subheader("Datos del Nuevo Producto")
            codigo = st.text_input("Código de Producto (único)")
            producto = st.text_input("Nombre Comercial del Producto")
            ing_activo = st.text_input("Ingrediente Activo")
            unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL", "Unidad"])
            proveedor = st.text_input("Proveedor Principal")
            tipo_accion = st.selectbox("Tipo de Acción / Subgrupo", ["FUNGICIDA", "INSECTICIDA", "HERBICIDA", "FERTILIZANTE", "COADYUVANTE", "OTRO"])
            submitted_nuevo = st.form_submit_button("Añadir Producto al Catálogo")
            if submitted_nuevo:
                if codigo and producto:
                    # ... Lógica para guardar el nuevo producto ...
                    st.success(f"¡Producto '{producto}' añadido al catálogo!")
                    st.rerun()

    st.divider()

    st.subheader("Kardex y Stock Actual")
    if df_productos.empty:
        st.warning("El catálogo de productos está vacío.")
    else:
        # ... Lógica para mostrar el kardex, descargas y desglose por lote ...
        pass

# --- PESTAÑA 2: REGISTRAR INGRESO ---
with tab_ingreso:
    st.header("Registrar Ingreso de Mercadería por Lote")
    if df_productos.empty:
        st.error("Catálogo de productos vacío. Añada productos en la pestaña de Kardex.")
    else:
        with st.form("ingreso_lote_form", clear_on_submit=True):
        st.markdown("##### 1. Información del Producto")
        
        producto_seleccionado = st.selectbox(
            "Seleccione el Producto que ingresa:",
            options=df_productos['Producto'].unique()
        )

        # --- !! MEJORA: MOSTRAR CÓDIGO DE PRODUCTO !! ---
        if producto_seleccionado:
            codigo_producto_visible = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
            st.info(f"**Código del Producto Seleccionado:** `{codigo_producto_visible}`")

        cantidad_ingresada = st.number_input("Cantidad Ingresada (en la unidad del producto)", min_value=0.01, format="%.2f")

        st.markdown("##### 2. Información del Lote (Costo y Caducidad)")
        col1, col2 = st.columns(2)
        with col1:
            precio_unitario = st.number_input("Precio Unitario (Costo por Unidad)", min_value=0.00, format="%.2f", help="El costo de compra de una unidad (Kg, L, etc.) de este lote.")
        with col2:
            fecha_vencimiento = st.date_input("Fecha de Vencimiento (Opcional)", value=None)

        st.markdown("##### 3. Documentación de Soporte")
        col3, col4, col5 = st.columns(3)
        with col3:
            fecha_ingreso = st.date_input("Fecha de Ingreso", datetime.now())
        with col4:
            proveedor = st.text_input("Proveedor")
        with col5:
            factura = st.text_input("Factura / Guía de Remisión")
            if st.form_submit_button("✅ Guardar Ingreso del Lote"):
                   if submitted:
            codigo_producto = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            codigo_lote = f"{codigo_producto}-{timestamp}"
            
            nuevo_ingreso_data = {
                'Codigo_Lote': codigo_lote,
                'Fecha': fecha_ingreso.strftime("%Y-%m-%d"),
                'Tipo': 'Ingreso por Compra',
                'Proveedor': proveedor,
                'Factura': factura,
                'Producto': producto_seleccionado,
                'Codigo_Producto': codigo_producto,
                'Cantidad': cantidad_ingresada,
                'Precio_Unitario': precio_unitario,
                'Fecha_Vencimiento': fecha_vencimiento.strftime("%Y-%m-%d") if fecha_vencimiento else None
            }
            df_nuevo_ingreso = pd.DataFrame([nuevo_ingreso_data])
            df_ingresos_actualizado = pd.concat([df_ingresos, df_nuevo_ingreso], ignore_index=True)
            
            exito = guardar_kardex(df_productos, df_ingresos_actualizado, df_salidas)
            
                st.success("¡Lote registrado!")
                st.rerun()

# --- HISTORIAL DE INGRESOS RECIENTES ---
st.header("📚 Historial de Ingresos Recientes")
if not df_ingresos.empty:
    columnas_a_mostrar = [
        'Fecha', 'Producto', 'Cantidad', 'Precio_Unitario', 
        'Codigo_Lote', 'Proveedor', 'Factura', 'Fecha_Vencimiento'
    ]
    columnas_existentes = [col for col in columnas_a_mostrar if col in df_ingresos.columns]
    st.dataframe(df_ingresos[columnas_existentes].tail(15).iloc[::-1], use_container_width=True)
else:
    st.info("Aún no se ha registrado ningún ingreso.")
# --- PESTAÑA 3: GESTIÓN DE MEZCLAS ---
with tab_mezclas:
    st.header("Gestionar y Programar Mezclas de Aplicación")
    with st.expander("👨‍🔬 Programar Nueva Receta de Mezcla (Ingeniero)"):
    lotes_activos = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0.001].copy()
    opciones_lotes = []
    if not lotes_activos.empty:
        lotes_activos['Fecha_Vencimiento'] = pd.to_datetime(lotes_activos['Fecha_Vencimiento']).dt.strftime('%Y-%m-%d')
        for _, row in lotes_activos.iterrows():
            label = (f"{row['Producto']} ({row['Codigo_Lote']}) | "
                     f"Stock: {row['Stock_Restante']:.2f} | "
                     f"Vence: {row['Fecha_Vencimiento'] or 'N/A'}")
            opciones_lotes.append(label)

    with st.form("programar_form"):
        st.subheader("Datos Generales de la Orden")
        col1, col2, col3 = st.columns(3)
        with col1: fecha_aplicacion = st.date_input("Fecha Programada")
        with col2: sector_aplicacion = st.text_input("Lote / Sector de Aplicación")
        with col3: turno = st.selectbox("Turno", ["Día", "Noche"])
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control de Oídio y Trips")

        st.subheader("Receta de la Mezcla")
        if not opciones_lotes:
            st.warning("No hay lotes con stock disponible para crear una receta.")
            productos_para_mezcla = None
        else:
            productos_para_mezcla = st.data_editor(
                pd.DataFrame([{"Lote_Seleccionado": opciones_lotes[0], "Cantidad_a_Usar": 1.0}]),
                num_rows="dynamic",
                column_config={
                    "Lote_Seleccionado": st.column_config.SelectboxColumn("Seleccione el Lote de Producto a Usar", options=opciones_lotes, required=True),
                    "Cantidad_a_Usar": st.column_config.NumberColumn("Cantidad TOTAL a Mezclar", min_value=0.01, format="%.3f")
                }, key="editor_mezcla"
            )

        submitted_programar = st.form_submit_button("✅ Programar Orden de Mezcla")

        if submitted_programar and productos_para_mezcla is not None:
            receta_final = []
            error = False
            for _, row in productos_para_mezcla.iterrows():
                codigo_lote = row['Lote_Seleccionado'].split('(')[1].split(')')[0]
                stock_disponible = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote]['Stock_Restante'].iloc[0]
                if row['Cantidad_a_Usar'] > stock_disponible:
                    st.error(f"Stock insuficiente para el lote {codigo_lote}. Solicitado: {row['Cantidad_a_Usar']}, Disponible: {stock_disponible}")
                    error = True
                    break
                else:
                    info_lote = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote].iloc[0]
                    receta_final.append({
                        'Codigo_Lote': codigo_lote,
                        'Producto': info_lote['Producto'],
                        'Codigo_Producto': info_lote['Codigo_Producto'],
                        'Cantidad_Usada': row['Cantidad_a_Usar']
                    })
            if not error:
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
            st.dataframe(df_receta, use_container_width=True)
            
            if st.button("✅ Confirmar Preparación y Registrar Salida", key=f"confirm_{tarea['ID_Orden']}"):
                nuevas_salidas = []
                for item in receta:
                    nuevas_salidas.append({
                        'Fecha': datetime.now().strftime("%Y-%m-%d"),
                        'Lote_Sector': tarea['Sector_Aplicacion'],
                        'Turno': tarea['Turno'],
                        'Producto': item['Producto'],
                        'Cantidad': item['Cantidad_Usada'],
                        'Codigo_Producto': item['Codigo_Producto'],
                        'Objetivo_Tratamiento': tarea['Objetivo'],
                        'Codigo_Lote': item['Codigo_Lote']
                    })
                df_nuevas_salidas = pd.DataFrame(nuevas_salidas)
                df_salidas_final = pd.concat([df_salidas, df_nuevas_salidas], ignore_index=True)
                
                guardar_kardex(df_productos, df_ingresos, df_salidas_final)
                
                df_ordenes.loc[index, 'Status'] = 'Lista para Aplicar'
                guardar_ordenes(df_ordenes)
                
                st.success(f"Salida para la orden '{tarea['ID_Orden']}' registrada. Stock actualizado.")
                st.rerun()
else:
    st.info("No hay recetas pendientes de preparar.")

# --- PESTAÑA 4: GESTIÓN DE APLICACIÓN ---
with tab_aplicacion:
    st.header("Finalizar Aplicaciones y Registrar Horas de Tractor")
    # (Aquí va el código completo de la página 8_...Gestión_de_Aplicación_y_Horas.py)
    st.subheader("✅ Tareas Listas para Aplicar")
    # (Lógica para mostrar y finalizar tareas)
    
    st.divider()
    st.subheader("📚 Historiales")
    # (Historial de horas y aplicaciones)
