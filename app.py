import streamlit as st
from supabase import create_client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Project-uva - Acceso", page_icon="🔐", layout="centered")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error de configuración en secrets: {e}")
        return None

supabase = init_supabase()

# --- FUNCIÓN PARA VERIFICAR CREDENCIALES ---
def verificar_usuario(usuario, clave):
    if not supabase:
        return None
    try:
        # Consultamos en la tabla Usuarios de Supabase
        res = supabase.table("Usuarios").select("*").eq("Usuario", usuario).eq("Clave", clave).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]  # Retorna el diccionario con los datos del usuario encontrado
        return None
    except Exception as e:
        st.error(f"Error al consultar la base de datos: {e}")
        return None

# --- INICIALIZAR VARIABLES DE SESIÓN ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
    st.session_state["usuario"] = None
    st.session_state["rol"] = None
    st.session_state["nombre"] = None

# --- INTERFAZ DE LOGEO ---
if not st.session_state["autenticado"]:
    st.markdown("<h1 style='text-align: center;'>🍇 Sistema de Control - Fundo</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: gray;'>Ingrese sus credenciales para desbloquear los módulos</p>", unsafe_allow_html=True)
    
    with st.form("formulario_login"):
        user_input = st.text_input("Usuario de Campo:", placeholder="Ej: sanidad")
        pin_input = st.text_input("PIN de Acceso (4 dígitos):", type="password", placeholder="****")
        
        btn_ingresar = st.form_submit_button("🔓 Desbloquear Sistema")
        
        if btn_ingresar:
            if user_input and pin_input:
                # Limpiamos espacios y convertimos el usuario a minúsculas para evitar fallos de tipeo
                datos_usuario = verificar_usuario(user_input.strip().lower(), pin_input.strip())
                
                if datos_usuario:
                    st.session_state["autenticado"] = True
                    st.session_state["usuario"] = datos_usuario["Usuario"]
                    st.session_state["rol"] = datos_usuario["Rol"]
                    st.session_state["nombre"] = datos_usuario["Nombre_Completo"]
                    st.success(f"¡Acceso concedido! Bienvenido, {datos_usuario['Nombre_Completo']}.")
                    st.rerun()
                else:
                    st.error("Usuario o PIN incorrectos. Verifique los datos.")
            else:
                st.warning("Por favor, rellene ambos campos.")
else:
    # Vista que aparece cuando ya iniciaron sesión correctamente
    st.markdown(f"# 🎉 ¡Bienvenido al sistema, {st.session_state['nombre']}!")
    st.subheader(f"Tu perfil activo es: **{st.session_state['rol']}**")
    st.write("Las credenciales se han validado correctamente con la base de datos central de Supabase.")
    st.info("👈 Ahora puedes usar la barra lateral para navegar de forma segura por los módulos de tu área de trabajo.")
    
    st.write("")
    if st.button("🔒 Cerrar Sesión"):
        st.session_state["autenticado"] = False
        st.session_state["usuario"] = None
        st.session_state["rol"] = None
        st.session_state["nombre"] = None
        st.rerun()