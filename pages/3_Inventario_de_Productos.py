import streamlit as st
import pandas as pd

# Nombre del archivo Excel que funciona como base de datos
DB_FILE = "Inventario_Productos.xlsx"

# --- Función para Cargar o Crear la Base de Datos ---
def cargar_db():
    try:
        df = pd.read_excel(DB_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=['Producto', 'Tipo_Accion', 'Modo_Accion', 'Grupo_FRAC', 'Notas_Uso'])
    return df

# --- Título de la Página ---
st.title("🧪 Inventario de Productos y Acciones de Control")

# --- Formulario para Ingresar Datos ---
with st.form("inventory_form", clear_on_submit=True):
    producto = st.text_input("Nombre del Producto o Ingrediente Activo")
    tipo_accion = st.selectbox("Tipo de Acción Principal", ["Preventivo", "Curativo", "Erradicante"])
    modo_accion = st.selectbox("Modo de Acción", ["Contacto", "Sistémico", "Translaminar", "Otro"])
    grupo_frac = st.text_input("Grupo FRAC (Opcional)", help="Código para el manejo de resistencia")
    notas = st.text_area("Notas de Uso (Ej: rotación, dosis, etc.)")
    
    submitted = st.form_submit_button("Añadir Producto al Inventario")

# --- Lógica para Guardar los Datos ---
if submitted and producto: # Asegura que el nombre del producto no esté vacío
    df = cargar_db()
    
    nuevo_producto = pd.DataFrame([{
        'Producto': producto,
        'Tipo_Accion': tipo_accion,
        'Modo_Accion': modo_accion,
        'Grupo_FRAC': grupo_frac,
        'Notas_Uso': notas
    }])
    
    df_actualizado = pd.concat([df, nuevo_producto], ignore_index=True)
    df_actualizado.to_excel(DB_FILE, index=False)
    
    st.success("✅ ¡Producto añadido al inventario!")
elif submitted:
    st.warning("⚠️ Por favor, ingrese el nombre del producto.")


# --- Mostrar el Inventario Completo ---
st.header("Inventario Actual de Productos")
df_inventario = cargar_db()
st.dataframe(df_inventario)
