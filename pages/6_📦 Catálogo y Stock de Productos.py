import streamlit as st
import pandas as pd
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Catálogo y Stock", page_icon="📦", layout="wide")
st.title("📦 Catálogo y Stock de Productos")
st.write("Cargue su inventario maestro desde Excel, defina nuevos productos y consulte o ajuste el stock actual.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Maestro.xlsx'

# --- FUNCIONES ---
def cargar_db():
    columnas = [
        'Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor',
        'Tipo_Accion', 'Stock_Actual', 'Stock_Minimo_Alerta', 'Ubicacion_Almacen'
    ]
    if os.path.exists(ARCHIVO_INVENTARIO):
        return pd.read_excel(ARCHIVO_INVENTARIO)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_db(df):
    try:
        df.to_excel(ARCHIVO_INVENTARIO, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

# --- Cargar datos al inicio ---
df_inventario = cargar_db()

# --- SECCIÓN 1: CARGA INICIAL DESDE EXCEL ---
with st.expander("⬆️ Cargar Inventario Completo desde Excel"):
    st.info("Suba aquí su archivo Excel '2025AgroqFertil.xlsx' para cargar o actualizar el catálogo de productos y el stock inicial de una sola vez.")
    
    uploaded_file = st.file_uploader("Seleccione su archivo Excel", type=["xlsx"])

    if uploaded_file is not None:
        if st.button("Procesar y Cargar Archivo"):
            with st.spinner("Leyendo y procesando el archivo Excel..."):
                try:
                    # Leer las hojas necesarias del Excel subido
                    df_cod_producto = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1)
                    df_stock = pd.read_excel(uploaded_file, sheet_name='STOCK', header=1)

                    # Seleccionar y renombrar columnas del catálogo de productos
                    df_catalogo = df_cod_producto[['CODIGO', 'PRODUCTO', 'INGREDIENTE ACTIVO', 'UNIDAD', 'PROVEEDOR', 'TIPO']].copy()
                    df_catalogo.columns = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']

                    # Seleccionar y renombrar columnas del stock
                    df_stock_actual = df_stock[['CODIGO', 'STOCK']].copy()
                    df_stock_actual.columns = ['Codigo', 'Stock_Actual']
                    
                    # Unir la información del catálogo con el stock actual
                    df_maestro_final = pd.merge(df_catalogo, df_stock_actual, on='Codigo', how='left')

                    # Añadir columnas faltantes con valores por defecto
                    df_maestro_final['Stock_Minimo_Alerta'] = 1.0 # Puedes ajustar este valor
                    df_maestro_final['Ubicacion_Almacen'] = 'General' # O dejarlo en blanco: ''
                    df_maestro_final['Stock_Actual'] = df_maestro_final['Stock_Actual'].fillna(0) # Rellenar stock no encontrado con 0

                    # Guardar el nuevo inventario maestro
                    exito, mensaje = guardar_db(df_maestro_final)
                    if exito:
                        st.success("¡Inventario maestro cargado y actualizado exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar el inventario: {mensaje}")

                except Exception as e:
                    st.error(f"Error al leer el archivo Excel. Asegúrese de que las hojas 'Cod_Producto' y 'STOCK' existan y tengan el formato correcto. Detalle: {e}")

st.divider()

# --- SECCIÓN 2: AÑADIR NUEVO PRODUCTO MANUALMENTE ---
with st.expander("➕ Añadir un Nuevo Producto al Catálogo (Manual)"):
    # (El código del formulario manual se mantiene igual)
    with st.form("nuevo_producto_form", clear_on_submit=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo = st.text_input("Código de Producto")
            producto = st.text_input("Nombre Comercial del Producto")
        with col2:
            ing_activo = st.text_input("Ingrediente Activo")
            unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL", "Unidad"])
        with col3:
            proveedor = st.text_input("Proveedor")
            tipo_accion = st.selectbox("Tipo de Acción", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Otro"])
        
        stock_inicial = st.number_input("Stock Inicial", min_value=0.0, format="%.2f", value=0.0)
        
        submitted_nuevo = st.form_submit_button("Añadir Producto")

        if submitted_nuevo:
            if producto and codigo:
                # Lógica para añadir manualmente un producto
                if codigo in df_inventario['Codigo'].values:
                    st.error(f"Error: El código '{codigo}' ya existe.")
                else:
                    nuevo_producto_df = pd.DataFrame([{'Codigo': codigo, 'Producto': producto, 'Ingrediente_Activo': ing_activo, 'Unidad': unidad, 'Proveedor': proveedor, 'Tipo_Accion': tipo_accion, 'Stock_Actual': stock_inicial, 'Stock_Minimo_Alerta': 1.0, 'Ubicacion_Almacen': 'General'}])
                    df_inventario_actualizado = pd.concat([df_inventario, nuevo_producto_df], ignore_index=True)
                    exito, mensaje = guardar_db(df_inventario_actualizado)
                    if exito:
                        st.success(f"¡Producto '{producto}' añadido!")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar: {mensaje}")
            else:
                st.warning("El Código y el Nombre son obligatorios.")

st.divider()

# --- SECCIÓN 3: VISUALIZACIÓN Y EDICIÓN DEL STOCK ---
st.header("Inventario Actual")
if not df_inventario.empty:
    st.info("Para un ajuste manual, haga doble clic en una celda de la columna 'Stock_Actual' y luego presione 'Guardar Cambios'.")
    df_editado = st.data_editor(
        df_inventario,
        column_config={
            "Codigo": st.column_config.TextColumn("Código", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", width="large", disabled=True),
            "Stock_Actual": st.column_config.NumberColumn("Stock Actual", min_value=0.0, format="%.2f"),
        },
        use_container_width=True, hide_index=True,
        key="editor_inventario"
    )
    if st.button("Guardar Cambios de Stock"):
        exito, mensaje = guardar_db(df_editado)
        if exito:
            st.success("💾 ¡Inventario actualizado!")
        else:
            st.error(f"Error al guardar: {mensaje}")
else:
    st.info("El catálogo está vacío. Añada productos manualmente o cargue su archivo Excel.")
