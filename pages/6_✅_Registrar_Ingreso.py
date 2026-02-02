import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso por Lote", page_icon="📥", layout="wide")
st.title("📥 Registro de Ingresos (Mercadería)")
st.write("Gestione la entrada de lotes específicos vinculados a su catálogo maestro.")

# --- INICIALIZAR SESSION STATE ---
if 'editing_ingreso_id' not in st.session_state:
    st.session_state.editing_ingreso_id = None
if 'deleting_ingreso_id' not in st.session_state:
    st.session_state.deleting_ingreso_id = None

# --- FUNCIÓN DE CONEXIÓN SEGURA ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- CARGA DE DATOS OPTIMIZADA ---
@st.cache_data(ttl=60)
def cargar_datos_para_ingreso():
    """Carga productos y el historial de ingresos, vinculando nombres por código."""
    if supabase:
        try:
            # Traer catálogo maestro
            res_p = supabase.table('Productos').select("Codigo, Producto").order('Producto').execute()
            df_p = pd.DataFrame(res_p.data)
            
            # Traer ingresos
            res_i = supabase.table('Ingresos').select("*").order('created_at', desc=True).execute()
            df_i = pd.DataFrame(res_i.data)
            
            # Unir tablas para mostrar el nombre del producto
            if not df_i.empty and not df_p.empty:
                df_final = pd.merge(df_i, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
                return df_p, df_final
            return df_p, df_i
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
    return pd.DataFrame(), pd.DataFrame()

df_productos, df_historial_ingresos = cargar_datos_para_ingreso()

# --- SECCIÓN 1: REGISTRO DE NUEVO LOTE ---
with st.expander("📝 Registrar Nuevo Lote de Ingreso", expanded=True):
    if df_productos.empty:
        st.warning("⚠️ El catálogo está vacío. Por favor, registre productos en el módulo de gestión.")
    else:
        with st.form("nuevo_ingreso_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            # Mapeo: "Producto (Código)" -> Código
            dict_productos = {f"{row['Producto']} ({row['Codigo']})": row['Codigo'] for _, row in df_productos.iterrows()}
            
            with col1:
                prod_sel = st.selectbox("Seleccione Producto", options=list(dict_productos.keys()))
                codigo_lote = st.text_input("Código de Lote (Ej: L-001/2026)")
                cantidad = st.number_input("Cantidad Recibida", min_value=0.0, step=0.1)
                proveedor = st.text_input("Nombre del Proveedor")
            
            with col2:
                precio_uni = st.number_input("Precio Unitario (S/)", min_value=0.0, step=0.01)
                factura = st.text_input("N° de Factura / Guía")
                f_ingreso = st.date_input("Fecha de Recepción", value=datetime.now())
                f_vencimiento = st.date_input("Fecha de Vencimiento", value=None)

            if st.form_submit_button("📥 Confirmar Ingreso"):
                if not codigo_lote:
                    st.error("Debe asignar un código de lote.")
                else:
                    nuevo_registro = {
                        "Codigo_Producto": dict_productos[prod_sel],
                        "Codigo_Lote": codigo_lote,
                        "Cantidad": cantidad,
                        "Precio_Unitario": precio_uni,
                        "Proveedor": proveedor,
                        "Factura": factura,
                        "Fecha": f_ingreso.strftime('%Y-%m-%d'),
                        "Fecha_Vencimiento": f_vencimiento.strftime('%Y-%m-%d') if f_vencimiento else None
                    }
                    try:
                        supabase.table('Ingresos').insert(nuevo_registro).execute()
                        st.toast(f"✅ Lote {codigo_lote} registrado.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en la base de datos: {e}")

# --- SECCIÓN 2: DIÁLOGOS DE EDICIÓN Y ELIMINACIÓN ---

if st.session_state.editing_ingreso_id:
    datos_fila = df_historial_ingresos[df_historial_ingresos['id'] == st.session_state.editing_ingreso_id].iloc[0]
    
    @st.dialog("✏️ Editar Registro")
    def edit_dialog():
        with st.form("edit_form"):
            st.write(f"Editando: **{datos_fila['Codigo_Lote']}**")
            c1, c2 = st.columns(2)
            new_cant = c1.number_input("Cantidad", value=float(datos_fila['Cantidad']))
            new_pre = c2.number_input("Precio", value=float(datos_fila['Precio_Unitario']))
            new_prov = c1.text_input("Proveedor", value=str(datos_fila['Proveedor']))
            new_fact = c2.text_input("Factura", value=str(datos_fila['Factura']))
            
            if st.form_submit_button("💾 Actualizar"):
                upd = {"Cantidad": new_cant, "Precio_Unitario": new_pre, "Proveedor": new_prov, "Factura": new_fact}
                supabase.table('Ingresos').update(upd).eq('id', datos_fila['id']).execute()
                st.session_state.editing_ingreso_id = None
                st.cache_data.clear()
                st.rerun()
    edit_dialog()

if st.session_state.deleting_ingreso_id:
    @st.dialog("🗑️ Confirmar Eliminación")
    def delete_dialog():
        st.warning("¿Está seguro? Esta acción afectará el stock actual en el Kardex.")
        if st.button("Sí, Eliminar"):
            supabase.table('Ingresos').delete().eq('id', st.session_state.deleting_ingreso_id).execute()
            st.session_state.deleting_ingreso_id = None
            st.cache_data.clear()
            st.rerun()
        if st.button("Cancelar"):
            st.session_state.deleting_ingreso_id = None
            st.rerun()
    delete_dialog()

# --- SECCIÓN 3: HISTORIAL ---
st.divider()
st.header("📚 Historial de Movimientos")

if not df_historial_ingresos.empty:
    for _, row in df_historial_ingresos.head(15).iterrows():
        with st.container(border=True):
            col_d, col_m, col_a = st.columns([6, 3, 2])
            with col_d:
                st.subheader(row.get('Producto', 'Producto no identificado'))
                st.caption(f"Lote: {row['Codigo_Lote']} | Código: {row['Codigo_Producto']}")
            with col_m:
                st.metric("Ingreso", f"{row['Cantidad']:.2f}")
                st.write(f"Precio: S/ {row['Precio_Unitario']:.2f}")
            with col_a:
                st.write(f"📅 {pd.to_datetime(row['Fecha']).strftime('%d/%m/%Y')}")
                b1, b2 = st.columns(2)
                if b1.button("✏️", key=f"edit_{row['id']}"):
                    st.session_state.editing_ingreso_id = row['id']
                    st.rerun()
                if b2.button("🗑️", key=f"del_{row['id']}"):
                    st.session_state.deleting_ingreso_id = row['id']
                    st.rerun()
else:
    st.info("No se han registrado ingresos de mercadería.")