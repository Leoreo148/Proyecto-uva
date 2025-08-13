import streamlit as st
import pandas as pd
import os

# --- Nombre del archivo Excel ---
DB_FILE = "Inventario_Productos.xlsx"

# --- Función para Cargar o Crear la Base de Datos ---
def cargar_db():
    # Columnas que debe tener nuestro inventario
    columnas_requeridas = [
        'Producto', 'Tipo_Accion', 'Modo_Accion', 'Grupo_FRAC', 
        'Notas_Uso', 'Cantidad_Stock', 'Unidad', 'Stock_Minimo_Alerta'
    ]
    try:
        df = pd.read_excel(DB_FILE)
    except FileNotFoundError:
        # Si el archivo no existe, crea un DataFrame vacío con todas las columnas
        df = pd.DataFrame(columns=columnas_requeridas)
    return df

# --- Función para Guardar la Base de Datos ---
def guardar_db(df):
    df.to_excel(DB_FILE, index=False)

# --- Cargar los datos al inicio ---
df_inventario = cargar_db()

# --- Título de la Página ---
st.set_page_config(page_title="Gestión de Inventario", page_icon="📦", layout="wide")
st.title("📦 Gestión de Inventario de Productos")

# --- Formulario para Añadir un Nuevo Producto ---
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
        nuevo_producto = pd.DataFrame([{
            'Producto': producto,
            'Tipo_Accion': tipo_accion,
            'Modo_Accion': modo_accion,
            'Grupo_FRAC': grupo_frac,
            'Notas_Uso': notas,
            'Cantidad_Stock': cantidad_inicial,
            'Unidad': unidad,
            'Stock_Minimo_Alerta': stock_minimo
        }])
        df_inventario = pd.concat([df_inventario, nuevo_producto], ignore_index=True)
        guardar_db(df_inventario)
        st.success(f"✅ ¡Producto '{producto}' añadido al inventario!")
        st.rerun() # Recarga la página para mostrar la tabla actualizada
    else:
        st.warning("⚠️ Por favor, ingrese el nombre del producto.")

st.divider()

# --- Mostrar y Editar el Inventario Actual ---
st.header("Inventario Actual")
if not df_inventario.empty:
    df_editado = st.data_editor(
        df_inventario,
        column_config={
            "Producto": st.column_config.TextColumn("Producto", disabled=True),
            "Tipo_Accion": st.column_config.TextColumn("Tipo", disabled=True),
            "Cantidad_Stock": st.column_config.NumberColumn("Stock Actual", min_value=0.0, format="%.2f"),
            "Stock_Minimo_Alerta": st.column_config.NumberColumn("Alerta de Stock Mínimo", min_value=0.0, format="%.2f"),
        },
        use_container_width=True,
        hide_index=True,
        num_rows="dynamic", # Permite añadir y eliminar filas
        key="editor_inventario"
    )

    if st.button("Guardar Cambios"):
        guardar_db(df_editado)
        st.success("💾 ¡Inventario actualizado exitosamente!")
else:
    st.info("El inventario está vacío. Añada un producto usando el formulario de arriba.")
