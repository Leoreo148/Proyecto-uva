import streamlit as st
import pandas as pd
import os

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Catálogo y Stock", page_icon="📦", layout="wide")
st.title("📦 Catálogo y Stock de Productos")
st.write("Defina sus productos y consulte o ajuste el stock actual. Esta sección requiere conexión a internet.")

# --- NOMBRES DE ARCHIVOS ---
ARCHIVO_INVENTARIO = 'Inventario_Maestro.xlsx' # Nuevo nombre para mayor claridad

# --- FUNCIONES ---
def cargar_db():
    # Columnas basadas en tu hoja "Cod_Producto" y "STOCK"
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

# --- FORMULARIO PARA AÑADIR NUEVO PRODUCTO ---
with st.expander("➕ Añadir Nuevo Producto al Catálogo"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Datos del Producto")
        col1, col2, col3 = st.columns(3)
        with col1:
            codigo = st.text_input("Código de Producto")
            producto = st.text_input("Nombre Comercial del Producto")
            ing_activo = st.text_input("Ingrediente Activo")
        with col2:
            unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL", "Unidad"])
            proveedor = st.text_input("Proveedor")
            tipo_accion = st.selectbox("Tipo de Acción", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Otro"])
        with col3:
            stock_inicial = st.number_input("Stock Inicial", min_value=0.0, format="%.2f")
            stock_minimo = st.number_input("Stock Mínimo de Alerta", min_value=0.0, format="%.2f")
            ubicacion = st.text_input("Ubicación en Almacén")
        
        submitted_nuevo = st.form_submit_button("Añadir Producto al Catálogo")

if submitted_nuevo:
    if producto and codigo:
        if codigo in df_inventario['Codigo'].values:
            st.error(f"Error: El código '{codigo}' ya existe en el catálogo.")
        else:
            nuevo_producto = pd.DataFrame([{
                'Codigo': codigo, 'Producto': producto, 'Ingrediente_Activo': ing_activo,
                'Unidad': unidad, 'Proveedor': proveedor, 'Tipo_Accion': tipo_accion,
                'Stock_Actual': stock_inicial, 'Stock_Minimo_Alerta': stock_minimo,
                'Ubicacion_Almacen': ubicacion
            }])
            df_inventario = pd.concat([df_inventario, nuevo_producto], ignore_index=True)
            exito, mensaje = guardar_db(df_inventario)
            if exito:
                st.success(f"✅ ¡Producto '{producto}' añadido al catálogo!")
                st.rerun()
            else:
                st.error(f"Error al guardar: {mensaje}")
    else:
        st.warning("⚠️ Por favor, ingrese al menos el Código y el Nombre del producto.")

st.divider()

# --- VISUALIZACIÓN Y EDICIÓN DEL STOCK ---
st.header("Inventario Actual")
if not df_inventario.empty:
    df_editado = st.data_editor(
        df_inventario,
        column_config={
            "Codigo": st.column_config.TextColumn("Código", disabled=True),
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "Stock_Actual": st.column_config.NumberColumn("Stock Actual", min_value=0.0, format="%.2f", help="Haga doble clic para ajustar el stock manualmente."),
            "Stock_Minimo_Alerta": st.column_config.NumberColumn("Alerta de Stock Mínimo", min_value=0.0, format="%.2f"),
        },
        use_container_width=True, hide_index=True,
        key="editor_inventario"
    )
    if st.button("Guardar Cambios de Stock"):
        exito, mensaje = guardar_db(df_editado)
        if exito:
            st.success("💾 ¡Inventario actualizado exitosamente!")
        else:
            st.error(f"Error al guardar: {mensaje}")
else:
    st.info("El catálogo está vacío. Añada un producto usando el formulario de arriba.")

