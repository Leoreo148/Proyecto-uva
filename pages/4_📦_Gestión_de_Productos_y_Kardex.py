import streamlit as st
import pandas as pd
import os
from datetime import datetime
# El motor 'openpyxl' es necesario para que pandas lea y escriba archivos .xlsx
import openpyxl 

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Productos y Kardex", page_icon="📦", layout="wide")
st.title("📦 Gestión de Productos y Kardex")
st.write("Catálogo de productos del fundo y visualización del stock calculado a partir de los movimientos de ingreso y salida.")

# --- CONSTANTES Y NOMBRES DE ARCHIVOS ---
KARDEX_FILE = 'kardex_fundo.xlsx'
SHEET_PRODUCTS = 'Productos'
SHEET_INGRESOS = 'Ingresos'
SHEET_SALIDAS = 'Salidas'

# --- FUNCIONES CORE DEL KARDEX ---

def cargar_kardex():
    """
    Carga todas las hojas del archivo Kardex. Si no existen, crea DataFrames vacíos
    con las columnas correctas.
    """
    cols_productos = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']
    cols_ingresos = ['Fecha', 'Tipo', 'Proveedor', 'Guia_Remision', 'Factura', 'Producto', 'Cantidad', 'Codigo_Producto']
    cols_salidas = ['Fecha', 'Lote_Sector', 'Guia_Remision', 'Turno', 'Producto', 'Cantidad', 'Codigo_Producto', 'Objetivo_Tratamiento']

    if os.path.exists(KARDEX_FILE):
        try:
            xls = pd.ExcelFile(KARDEX_FILE)
            df_productos = pd.read_excel(xls, sheet_name=SHEET_PRODUCTS)
            df_ingresos = pd.read_excel(xls, sheet_name=SHEET_INGRESOS)
            df_salidas = pd.read_excel(xls, sheet_name=SHEET_SALIDAS)
        except Exception as e:
            st.error(f"Error al leer una de las hojas del Kardex: {e}. Se crearán hojas vacías.")
            df_productos = pd.DataFrame(columns=cols_productos)
            df_ingresos = pd.DataFrame(columns=cols_ingresos)
            df_salidas = pd.DataFrame(columns=cols_salidas)
    else:
        df_productos = pd.DataFrame(columns=cols_productos)
        df_ingresos = pd.DataFrame(columns=cols_ingresos)
        df_salidas = pd.DataFrame(columns=cols_salidas)

    return df_productos, df_ingresos, df_salidas

def guardar_kardex(df_productos, df_ingresos, df_salidas):
    """
    Guarda todos los dataframes en un único archivo Excel con múltiples hojas.
    """
    with pd.ExcelWriter(KARDEX_FILE, engine='openpyxl') as writer:
        df_productos.to_excel(writer, sheet_name=SHEET_PRODUCTS, index=False)
        df_ingresos.to_excel(writer, sheet_name=SHEET_INGRESOS, index=False)
        df_salidas.to_excel(writer, sheet_name=SHEET_SALIDAS, index=False)
    return True

def calcular_stock(df_ingresos, df_salidas):
    """
    Calcula el stock actual para cada producto basándose en el historial de
    ingresos y salidas.
    """
    if df_ingresos.empty and df_salidas.empty:
        return pd.DataFrame(columns=['Codigo_Producto', 'Stock_Actual'])

    ingresos_agg = df_ingresos.groupby('Codigo_Producto')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Total_Ingresos'})
    salidas_agg = df_salidas.groupby('Codigo_Producto')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Total_Salidas'})
    stock_df = pd.merge(ingresos_agg, salidas_agg, on='Codigo_Producto', how='outer').fillna(0)
    stock_df['Stock_Actual'] = stock_df['Total_Ingresos'] - stock_df['Total_Salidas']
    
    return stock_df[['Codigo_Producto', 'Stock_Actual']]

# --- CARGA INICIAL DE DATOS ---
df_productos, df_ingresos, df_salidas = cargar_kardex()

# --- INTERFAZ DE USUARIO ---

# --- SECCIÓN 1: CARGA INICIAL DESDE EXCEL (MODIFICADA) ---
with st.expander("⬆️ Cargar Catálogo Inicial desde un único archivo Excel"):
    st.info("Utilice esta sección para cargar su catálogo de productos y stock inicial desde su archivo `2025AgroqFertil.xlsx`.")
    
    uploaded_file = st.file_uploader("Suba su archivo Excel", type=["xlsx"])

    if st.button("Procesar Archivo Excel Completo"):
        if uploaded_file:
            with st.spinner("Procesando archivo Excel..."):
                try:
                    # Leer la hoja de productos. El encabezado está en la fila 2 (índice 1).
                    df_new_productos = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1)
                    df_new_productos = df_new_productos.rename(columns={
                        'CODIGO': 'Codigo', 'PRODUCTOS': 'Producto', 'ING. ACTIVO': 'Ingrediente_Activo',
                        'UM': 'Unidad', 'PROVEEDOR': 'Proveedor', 'SUBGRUPO': 'Tipo_Accion'
                    })
                    # Eliminar filas vacías si las hubiera
                    df_new_productos.dropna(subset=['Codigo', 'Producto'], inplace=True)

                    # Leer la hoja de stock. El encabezado está en la fila 3 (índice 2).
                    df_initial_stock = pd.read_excel(uploaded_file, sheet_name='STOCK', header=2)
                    df_initial_stock = df_initial_stock.rename(columns={'CANT': 'Cantidad', 'CODIGO': 'Codigo_Producto'})
                    df_initial_stock.dropna(subset=['Codigo_Producto'], inplace=True)

                    # Formatear el stock inicial como el primer movimiento de ingreso
                    df_initial_stock['Fecha'] = datetime.now().strftime("%Y-%m-%d")
                    df_initial_stock['Tipo'] = 'Ajuste de Inventario Inicial'
                    df_initial_stock['Proveedor'] = 'N/A'
                    df_initial_stock['Guia_Remision'] = 'N/A'
                    df_initial_stock['Factura'] = 'N/A'
                    df_merged = pd.merge(df_initial_stock, df_new_productos[['Codigo', 'Producto']], left_on='Codigo_Producto', right_on='Codigo', how='left')
                    
                    # Seleccionar y ordenar las columnas para la hoja de Ingresos
                    cols_ingresos = ['Fecha', 'Tipo', 'Proveedor', 'Guia_Remision', 'Factura', 'Producto', 'Cantidad', 'Codigo_Producto']
                    df_new_ingresos = df_merged[cols_ingresos]
                    
                    # Guardar los datos procesados en el archivo Kardex
                    guardar_kardex(df_productos=df_new_productos, df_ingresos=df_new_ingresos, df_salidas=pd.DataFrame(columns=df_salidas.columns))
                    st.success("¡Catálogo y stock inicial cargados exitosamente!")
                    st.rerun()

                except Exception as e:
                    st.error(f"Ocurrió un error. Verifique que su archivo Excel contenga las hojas 'Cod_Producto' y 'STOCK' con los nombres exactos. Detalle: {e}")
        else:
            st.warning("Por favor, suba su archivo Excel para continuar.")

# --- SECCIÓN 2: AÑADIR NUEVO PRODUCTO MANUALMENTE ---
with st.expander("➕ Añadir un Nuevo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Datos del Nuevo Producto")
        codigo = st.text_input("Código de Producto (único)", help="Ej: F001")
        producto = st.text_input("Nombre Comercial del Producto")
        ing_activo = st.text_input("Ingrediente Activo")
        unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL", "Unidad"])
        proveedor = st.text_input("Proveedor Principal")
        tipo_accion = st.selectbox("Tipo de Acción / Subgrupo", ["FUNGICIDA", "INSECTICIDA", "HERBICIDA", "FERTILIZANTE", "COADYUVANTE", "OTRO"])
        
        submitted_nuevo = st.form_submit_button("Añadir Producto al Catálogo")

        if submitted_nuevo:
            if codigo and producto:
                if codigo not in df_productos['Codigo'].values:
                    nuevo_producto_df = pd.DataFrame([{'Codigo': codigo, 'Producto': producto, 'Ingrediente_Activo': ing_activo, 'Unidad': unidad, 'Proveedor': proveedor, 'Tipo_Accion': tipo_accion}])
                    df_productos_actualizado = pd.concat([df_productos, nuevo_producto_df], ignore_index=True)
                    guardar_kardex(df_productos=df_productos_actualizado, df_ingresos=df_ingresos, df_salidas=df_salidas)
                    st.success(f"¡Producto '{producto}' añadido al catálogo!")
                    st.rerun()
                else:
                    st.error(f"Error: El código '{codigo}' ya existe en el catálogo.")
            else:
                st.warning("El Código y el Nombre del producto son obligatorios.")

st.divider()

# --- SECCIÓN 3: VISUALIZACIÓN DEL KARDEX Y STOCK CALCULADO ---
st.header("Kardex y Stock Actual")

if df_productos.empty:
    st.warning("El catálogo de productos está vacío. Añada un producto manualmente o cargue el catálogo inicial.")
else:
    df_stock_actual = calcular_stock(df_ingresos, df_salidas)
    df_vista_kardex = pd.merge(df_productos, df_stock_actual, left_on='Codigo', right_on='Codigo_Producto', how='left').fillna(0)
    df_vista_kardex = df_vista_kardex[['Codigo', 'Producto', 'Stock_Actual', 'Unidad', 'Tipo_Accion', 'Proveedor']]

    st.info("El stock es calculado automáticamente a partir de los ingresos y salidas. No es editable directamente.")
    
    filtro_texto = st.text_input("Buscar producto por nombre o código:")
    if filtro_texto:
        df_vista_kardex = df_vista_kardex[df_vista_kardex['Producto'].str.contains(filtro_texto, case=False) | df_vista_kardex['Codigo'].str.contains(filtro_texto, case=False)]

    st.dataframe(df_vista_kardex, use_container_width=True, hide_index=True)
    
    st.subheader("Ver Historial de Movimientos de un Producto")
    producto_seleccionado = st.selectbox("Seleccione un producto para ver su historial:", options=df_productos['Producto'])

    if producto_seleccionado:
        codigo_seleccionado = df_productos[df_productos['Producto'] == producto_seleccionado]['Codigo'].iloc[0]
        historial_ingresos = df_ingresos[df_ingresos['Codigo_Producto'] == codigo_seleccionado]
        historial_salidas = df_salidas[df_salidas['Codigo_Producto'] == codigo_seleccionado]

        col_ing, col_sal = st.columns(2)
        with col_ing:
            st.markdown("##### Historial de Ingresos")
            st.dataframe(historial_ingresos, use_container_width=True, hide_index=True)
        with col_sal:
            st.markdown("##### Historial de Salidas")
            st.dataframe(historial_salidas, use_container_width=True, hide_index=True)
