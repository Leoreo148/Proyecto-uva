import streamlit as st
import pandas as pd
import os

st.set_page_config(page_title="Gestión de Inventario", page_icon="📦", layout="wide")
st.title("📦 Gestión de Inventario de Productos")
st.write("Añada, vea y actualice el stock de sus productos. Esta sección requiere conexión a internet.")

DB_FILE = "Inventario_Productos.xlsx"

def cargar_db():
    columnas = [
        'Producto', 'Tipo_Accion', 'Modo_Accion', 'Grupo_FRAC', 
        'Notas_Uso', 'Cantidad_Stock', 'Unidad', 'Stock_Minimo_Alerta'
    ]
    try:
        df = pd.read_excel(DB_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=columnas)
    return df

def guardar_db(df):
    try:
        df.to_excel(DB_FILE, index=False, engine='openpyxl')
        return True, "Guardado exitoso."
    except Exception as e:
        return False, str(e)

df_inventario = cargar_db()

with st.expander("➕ Añadir Nuevo Producto al Inventario"):
    with st.form("nuevo_producto_form", clear_on_submit=True):
        st.subheader("Datos del Producto")
        col1, col2 = st.columns(2)
        with col1:
            producto = st.text_input("Nombre del Producto")
            tipo_accion = st.selectbox("Tipo de Acción", ["Insecticida", "Fungicida", "Herbicida", "Fertilizante", "Otro"])
            modo_accion = st.selectbox("Modo de Acción", ["Contacto", "Sistémico", "Translaminar", "Otro"])
            grupo_frac = st.text_input("Grupo FRAC (Opcional)")
        with col2:
            cantidad_inicial = st.number_input("Cantidad Inicial en Stock", min_value=0.0, format="%.2f")
            unidad = st.selectbox("Unidad de Medida", ["L", "kg", "g", "mL"])
            stock_minimo = st.number_input("Stock Mínimo de Alerta", min_value=0.0, format="%.2f")
            notas = st.text_area("Notas de Uso")
        
        submitted_nuevo = st.form_submit_button("Añadir Producto")

if submitted_nuevo:
    if producto:
        nuevo_producto = pd.DataFrame([{'Producto': producto, 'Tipo_Accion': tipo_accion, 'Modo_Accion': modo_accion, 'Grupo_FRAC': grupo_frac, 'Notas_Uso': notas, 'Cantidad_Stock': cantidad_inicial, 'Unidad': unidad, 'Stock_Minimo_Alerta': stock_minimo}])
        df_inventario = pd.concat([df_inventario, nuevo_producto], ignore_index=True)
        exito, mensaje = guardar_db(df_inventario)
        if exito:
            st.success(f"✅ ¡Producto '{producto}' añadido al inventario!")
            st.rerun()
        else:
            st.error(f"Error al guardar: {mensaje}")
    else:
        st.warning("⚠️ Por favor, ingrese el nombre del producto.")

st.divider()
st.header("Inventario Actual")
if not df_inventario.empty:
    df_editado = st.data_editor(
        df_inventario,
        column_config={"Producto": st.column_config.TextColumn("Producto", disabled=True), "Tipo_Accion": st.column_config.TextColumn("Tipo", disabled=True), "Cantidad_Stock": st.column_config.NumberColumn("Stock Actual", min_value=0.0, format="%.2f"), "Stock_Minimo_Alerta": st.column_config.NumberColumn("Alerta de Stock Mínimo", min_value=0.0, format="%.2f")},
        use_container_width=True, hide_index=True, num_rows="dynamic", key="editor_inventario"
    )
    if st.button("Guardar Cambios"):
        exito, mensaje = guardar_db(df_editado)
        if exito:
            st.success("💾 ¡Inventario actualizado exitosamente!")
        else:
            st.error(f"Error al guardar: {mensaje}")
else:
    st.info("El inventario está vacío. Añada un producto usando el formulario de arriba.")
