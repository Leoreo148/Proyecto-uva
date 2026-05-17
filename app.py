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
    # --- VISTA CUANDO EL USUARIO YA INICIÓ SESIÓN ---
    rol = st.session_state["rol"]
    
    # 1. Definir TODAS las páginas (rutas limpias, íconos separados)
    p_sanidad = st.Page("modulos/1_Evaluacion_Sanitaria.py", title="Evaluación Sanitaria", icon="📝")
    p_mosca = st.Page("modulos/1_Monitoreo_Mosca.py", title="Monitoreo Mosca", icon="🪰")
    p_fenologia = st.Page("modulos/1_Evaluacion_Fenologica.py", title="Evaluación Fenológica", icon="🌱")
    p_baya = st.Page("modulos/1_Diametro_Baya.py", title="Diámetro Baya", icon="🍇")
    p_raleo = st.Page("modulos/1_Control_Raleo.py", title="Control Raleo", icon="✂️")
    p_tractor = st.Page("modulos/2_Gestion_Tractor.py", title="Gestión Tractor", icon="🚜")
    
    # (Tus futuros dashboards que crearemos)
    # p_dash_sanidad = st.Page("modulos/3_📊_Dashboard_Sanidad.py", title="Dashboard Sanidad", icon="📊")
    # p_dash_finanzas = st.Page("modulos/5_💵_Dashboard_Finanzas.py", title="Finanzas y Costos", icon="💵")
    # p_rendimiento = st.Page("modulos/5_📈_Rendimiento_Raleo.py", title="Planillas Raleo", icon="📈")

    # 2. Armar el menú personalizado según el Rol de Supabase
    if rol == "Sanidad":
        # José solo ve sus módulos, lo demás ni siquiera existe para él
        paginas = [p_sanidad, p_mosca, p_fenologia, p_baya] # Agrega aquí p_dash_sanidad cuando lo crees
        
    elif rol == "Admin":
        # Segundo (El Jefe) ve todo, y encima se lo agrupamos por categorías bonitas
        paginas = {
            "Operaciones Campo": [p_sanidad, p_mosca, p_fenologia, p_baya, p_raleo],
            "Maquinaria": [p_tractor],
            # "Jefatura": [p_dash_sanidad, p_dash_finanzas, p_rendimiento]
        }
        
    elif rol == "Evaluador":
        # El Empleado A solo ve recolectores de datos
        paginas = [p_sanidad, p_mosca, p_fenologia, p_baya]
        
    else:
        # Por seguridad, si hay un rol raro, no ve nada
        paginas = []

    # 3. Lanzar la barra lateral dinámica y el botón de Cerrar Sesión
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state['nombre']}**")
        st.markdown(f"🏷️ Puesto: *{rol}*")
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state["autenticado"] = False
            st.rerun()

    if paginas:
        menu = st.navigation(paginas)
        menu.run()
    else:
        st.warning("No tienes módulos asignados. Contacta al administrador.")