import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso por Lote", page_icon="📥", layout="wide")
st.title("📥 Registrar Ingreso de Mercadería por Lote")
st.write("Gestione las compras de insumos vinculadas al catálogo maestro de productos.")

# --- INICIALIZAR SESSION STATE ---
if 'editing_ingreso_id' not in st.session_state:
    st.session_state.editing_ingreso_id = None
if 'deleting_ingreso_id' not in st.session_state:
    st.session_state.deleting_ingreso_id = None

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
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
            
            # Unir tablas en Python para mostrar el nombre del producto sin guardarlo dos veces
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
        st.warning("⚠️ No hay productos en el catálogo. Primero añada productos en el módulo de Gestión.")
    else:
        with st.form("nuevo_ingreso_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            # Crear diccionario para el selectbox: "Nombre del Producto (Código)" -> Codigo
            dict_productos = {f"{row['Producto']} ({row['Codigo']})": row['Codigo'] for _, row in df_productos.iterrows()}
            
            with col1:
                prod_seleccionado = st.selectbox("Seleccione Producto", options=list(dict_productos.keys()))
                codigo_lote = st.text_input("Código de Lote (Ej: L-001/2026)", help="Identificador único del lote del fabricante.")
                cantidad = st.number_input("Cantidad Recibida", min_value=0.0, step=0.1)
                proveedor = st.text_input("Nombre del Proveedor")
            
            with col2:
                precio_unitario = st.number_input("Precio Unitario (S/)", min_value=0.0, step=0.1)
                factura = st.text_input("N° de Factura / Guía")
                fecha_ingreso = st.date_input("Fecha de Recepción", value=datetime.now())
                fecha_vencimiento = st.date_input("Fecha de Vencimiento", value=None)

            if st.form_submit_button("📥 Registrar Ingreso"):
                if not codigo_lote:
                    st.error("El Código de Lote es obligatorio.")
                else:
                    nuevo_ingreso = {
                        "Codigo_Producto": dict_productos[prod_seleccionado],
                        "Codigo_Lote": codigo_lote,
                        "Cantidad": cantidad,
                        "Precio_Unitario": precio_unitario,
                        "Proveedor": proveedor,
                        "Factura": factura,
                        "Fecha": fecha_ingreso.strftime('%Y-%m-%d'),
                        "Fecha_Vencimiento": fecha_vencimiento.strftime('%Y-%m-%d') if fecha_vencimiento else None
                    }
                    try:
                        supabase.table('Ingresos').insert(nuevo_ingreso).execute()
                        st.success(f"Lote {codigo_lote} registrado correctamente.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

# --- SECCIÓN 2: DIÁLOGOS DE EDICIÓN Y ELIMINACIÓN ---

# Edición
if st.session_state.editing_ingreso_id:
    datos_fila = df_historial_ingresos[df_historial_ingresos['id'] == st.session_state.editing_ingreso_id].iloc[0]
    
    @st.dialog("✏️ Editar Registro")
    def edit_dialog():
        with st.form("edit_form"):
            st.write(f"Editando Lote: **{datos_fila['Codigo_Lote']}**")
            col1, col2 = st.columns(2)
            with col1:
                new_cant = st.number_input("Cantidad", value=float(datos_fila['Cantidad']))
                new_prov = st.text_input("Proveedor", value=str(datos_fila['Proveedor']))
            with col2:
                new_pre = st.number_input("Precio", value=float(datos_fila['Precio_Unitario']))
                new_fact = st.text_input("Factura", value=str(datos_fila['Factura']))
            
            if st.form_submit_button("💾 Guardar"):
                update_data = {
                    "Cantidad": new_cant, "Proveedor": new_prov,
                    "Precio_Unitario": new_pre, "Factura": new_fact
                }
                supabase.table('Ingresos').update(update_data).eq('id', datos_fila['id']).execute()
                st.session_state.editing_ingreso_id = None
                st.cache_data.clear()
                st.rerun()
    edit_dialog()

# Eliminación
if st.session_state.deleting_ingreso_id:
    @st.dialog("🗑️ Confirmar")
    def delete_dialog():
        st.warning("¿Eliminar este registro de forma permanente?")
        if st.button("Confirmar Eliminación"):
            supabase.table('Ingresos').delete().eq('id', st.session_state.deleting_ingreso_id).execute()
            st.session_state.deleting_ingreso_id = None
            st.cache_data.clear()
            st.rerun()
        if st.button("Cancelar"):
            st.session_state.deleting_ingreso_id = None
            st.rerun()
    delete_dialog()

# --- SECCIÓN 3: HISTORIAL VISUAL ---
st.divider()
st.header("📚 Historial de Ingresos")

if not df_historial_ingresos.empty:
    for _, row in df_historial_ingresos.head(10).iterrows():
        with st.container(border=True):
            c1, c2, c3 = st.columns([6, 3, 2])
            with c1:
                # El nombre 'Producto' ahora viene del merge con la tabla maestro
                st.subheader(f"{row.get('Producto', 'Producto no encontrado')}")
                st.caption(f"Lote: {row['Codigo_Lote']} | Código: {row['Codigo_Producto']}")
            with c2:
                st.metric("Stock Ingresado", f"{row['Cantidad']:.2f}")
                st.write(f"💵 S/ {row['Precio_Unitario']:.2f} / unidad")
            with c3:
                st.write(f"📅 {pd.to_datetime(row['Fecha']).strftime('%d/%m/%Y')}")
                # Botones de acción
                b1, b2 = st.columns(2)
                if b1.button("✏️", key=f"e_{row['id']}"):
                    st.session_state.editing_ingreso_id = row['id']
                    st.rerun()
                if b2.button("🗑️", key=f"d_{row['id']}"):
                    st.session_state.deleting_ingreso_id = row['id']
                    st.rerun()
else:
    st.info("No hay registros de ingreso aún.")