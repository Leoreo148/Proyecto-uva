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
        res = supabase.table("Usuarios").select("*").eq("Usuario", usuario).eq("Clave", clave).execute()
        if res.data and len(res.data) > 0:
            return res.data[0]
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
    
    with st.expander("ℹ️ Ver lista de usuarios del Fundo"):
        st.markdown("""
        **Usuarios habilitados para el sistema:**
        * `admin` (Segundo - Gerencia)
        * `sanidad` (José - Jefe Sanidad)
        * `costos` (Edgar - Finanzas)
        * `mezclas` (Miguel - Almacén)
        * `campo_a` (Empleado Evaluador)
        
        *(Tu PIN de 4 dígitos es personal)*
        """)

    with st.form("formulario_login"):
        user_input = st.text_input("Usuario de Campo:", placeholder="Ej: sanidad")
        pin_input = st.text_input("PIN de Acceso (4 dígitos):", type="password", placeholder="****")
        
        btn_ingresar = st.form_submit_button("🔓 Desbloquear Sistema")
        
        if btn_ingresar:
            if user_input and pin_input:
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
    
    # 1. Definición de páginas apuntando exactamente a tus archivos físicos
    p_raleo = st.Page("modulos/1_Control_Raleo.py", title="Control Raleo", icon="✂️")
    p_baya = st.Page("modulos/1_Diametro_Baya.py", title="Diámetro Baya", icon="🍇")
    p_fenologia = st.Page("modulos/1_Evaluación Fenológica.py", title="Evaluación Fenológica", icon="🌱")
    p_sanidad = st.Page("modulos/1_Evaluacion_Sanitaria.py", title="Evaluación Sanitaria", icon="📝")
    p_mosca = st.Page("modulos/1_Monitoreo_Mosca_Fruta.py", title="Monitoreo Mosca", icon="🪰")
    
    p_tractor = st.Page("modulos/2_Gestión_de_Aplicación_y_Horas.py", title="Gestión Tractor", icon="🚜")
    
    p_dash_sanidad = st.Page("modulos/3_Dashboard_Sanidad.py", title="Dashboard Sanidad", icon="📊")
    
    p_mezclas = st.Page("modulos/4_Gestión de Mezclas.py", title="Gestión de Mezclas", icon="⚗️")
    p_kardex = st.Page("modulos/4_Gestión_de_Productos_y_Kardex.py", title="Productos y Kardex", icon="📦")
    p_ingreso = st.Page("modulos/4_Registrar_Ingreso.py", title="Registrar Ingreso", icon="✅")
    
    p_dash_finanzas = st.Page("modulos/5_Dashboard_Finanzas.py", title="Dashboard Finanzas", icon="💵")
    p_rend_raleo = st.Page("modulos/5_Rendimiento_Raleo.py", title="Rendimiento Raleo", icon="📈")
    
    p_dash_general = st.Page("modulos/6_Dashboard_General.py", title="Dashboard General Fundo", icon="🏢")
    p_carga_masiva = st.Page("modulos/99_Carga_Masiva.py", title="Carga Masiva", icon="🚀")

    # 2. Armar el menú inteligente y en ruteo por cada Rol
    if rol == "Sanidad":
        paginas = [p_dash_sanidad]
        
    elif rol == "Logistica":
        # Miguel (mezclas) ahora ve exclusivamente el control de almacenes y mezclas
        paginas = [p_kardex, p_ingreso, p_mezclas]
        
    elif rol == "Finanzas":
        # Edgar (costos) ve los balances monetarios y el inventario para auditorías
        paginas = [p_dash_finanzas, p_rend_raleo, p_kardex]
        
    elif rol == "Evaluador":
        paginas = [p_sanidad, p_mosca, p_fenologia, p_baya]
        
    elif rol == "Admin":
        # El Ingeniero Segundo ve absolutamente todo organizado por departamentos
        paginas = {
            "Control Central": [p_dash_general],
            "Operaciones Campo": [p_sanidad, p_mosca, p_fenologia, p_baya, p_raleo],
            "Logística y Almacén": [p_kardex, p_ingreso, p_mezclas],
            "Maquinaria": [p_tractor],
            "Reportes y Finanzas": [p_dash_finanzas, p_rend_raleo, p_dash_sanidad],
            "Mantenimiento": [p_carga_masiva]
        }
    else:
        paginas = []

    # 3. Lanzar la barra lateral dinámica y el botón de Cerrar Sesión
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state['nombre']}**")
        st.markdown(f"🏷️ Puesto: *{rol}*")
        if st.button("🔒 Cerrar Sesión", use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["usuario"] = None
            st.session_state["rol"] = None
            st.session_state["nombre"] = None
            st.rerun()

    if paginas:
        menu = st.navigation(paginas)
        menu.run()
    else:
        st.warning("No tienes módulos asignados. Contacta al administrador.")