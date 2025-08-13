import streamlit as st
import pandas as pd
import os
import hashlib

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Usuarios", page_icon="👤", layout="wide")
st.title("👤 Gestión de Usuarios")

# --- NOMBRE DEL ARCHIVO ---
ARCHIVO_USUARIOS = 'usuarios.xlsx'

# --- FUNCIÓN PARA HASHEAR CONTRASEÑAS ---
def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

# --- FUNCIONES PARA CARGAR Y GUARDAR ---
def cargar_usuarios():
    columnas = ['username', 'password_hash', 'role']
    if os.path.exists(ARCHIVO_USUARIOS):
        return pd.read_excel(ARCHIVO_USUARIOS)
    else:
        return pd.DataFrame(columns=columnas)

def guardar_usuarios(df):
    df.to_excel(ARCHIVO_USUARIOS, index=False)

# --- Cargar datos al inicio ---
df_usuarios = cargar_usuarios()

# --- FORMULARIO PARA AÑADIR NUEVO USUARIO ---
st.subheader("Añadir Nuevo Usuario")
with st.form("nuevo_usuario_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        nuevo_username = st.text_input("Nombre de Usuario")
    with col2:
        nueva_password = st.text_input("Contraseña", type="password")
    with col3:
        nuevo_rol = st.selectbox("Rol", ["Admin", "Trabajador"])

    submitted = st.form_submit_button("Añadir Usuario")

if submitted:
    if nuevo_username and nueva_password:
        if nuevo_username in df_usuarios['username'].values:
            st.error("Error: El nombre de usuario ya existe.")
        else:
            hashed_pass = hash_password(nueva_password)
            nuevo_usuario_df = pd.DataFrame([{
                'username': nuevo_username,
                'password_hash': hashed_pass,
                'role': nuevo_rol
            }])
            df_usuarios = pd.concat([df_usuarios, nuevo_usuario_df], ignore_index=True)
            guardar_usuarios(df_usuarios)
            st.success(f"¡Usuario '{nuevo_username}' creado exitosamente!")
    else:
        st.warning("Por favor, complete todos los campos.")

st.divider()

# --- VISUALIZACIÓN DE USUARIOS EXISTENTES ---
st.subheader("Usuarios Registrados")
if not df_usuarios.empty:
    # Mostramos solo el nombre de usuario y el rol, nunca la contraseña hasheada
    st.dataframe(df_usuarios[['username', 'role']], use_container_width=True)
else:
    st.info("Aún no hay usuarios registrados.")
