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
                    # Leemos las hojas necesarias, indicando que el encabezado está en la segunda fila (índice 1)
                    df_cod_producto = pd.read_excel(uploaded_file, sheet_name='Cod_Producto', header=1)
                    df_stock = pd.read_excel(uploaded_file, sheet_name='STOCK', header=2) # El encabezado en STOCK está más abajo

                    # --- CORRECCIÓN: Usamos los nombres de columna exactos de TU archivo ---
                    df_catalogo = df_cod_producto[['CODIGO', 'PRODUCTOS', 'ING. ACTIVO', 'UM', 'PROVEEDOR', 'SUBGRUPO']].copy()
                    df_catalogo.columns = ['Codigo', 'Producto', 'Ingrediente_Activo', 'Unidad', 'Proveedor', 'Tipo_Accion']

                    # En la hoja STOCK, los nombres están en varias columnas, los unimos y buscamos el stock
                    # Esta lógica es más compleja para manejar la estructura de tu archivo
                    df_stock_formateado = pd.DataFrame()
                    if 'PRODUCTO' in df_stock.columns and 'CANT' in df_stock.columns:
                         df_stock_formateado = df_stock[['PRODUCTO', 'CANT']].rename(columns={'PRODUCTO': 'Producto', 'CANT': 'Stock_Actual'})
                    
                    # Unir la información del catálogo con el stock actual
                    df_maestro_final = pd.merge(df_catalogo, df_stock_formateado, on='Producto', how='left')
                    
                    # Añadir columnas faltantes y limpiar
                    df_maestro_final['Stock_Minimo_Alerta'] = 1.0
                    df_maestro_final['Ubicacion_Almacen'] = 'General'
                    df_maestro_final['Stock_Actual'] = df_maestro_final['Stock_Actual'].fillna(0)
                    
                    exito, mensaje = guardar_db(df_maestro_final)
                    if exito:
                        st.success("¡Inventario maestro cargado y actualizado exitosamente!")
                        st.rerun()
                    else:
                        st.error(f"Error al guardar el inventario: {mensaje}")

                except Exception as e:
                    st.error(f"Error al leer el archivo Excel. Asegúrese de que las hojas 'Cod_Producto' y 'STOCK' existan y tengan el formato correcto. Detalle: {e}")

st.divider()

# --- El resto del código para añadir manualmente y ver el stock se mantiene igual ---
# (Puedes copiar y pegar el resto del código del archivo anterior aquí si lo necesitas)
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
