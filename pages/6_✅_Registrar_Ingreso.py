import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Registrar Ingreso por Lote", page_icon="📥", layout="wide")
st.title("📥 Registrar Ingreso de Mercadería por Lote")
st.write("Registre cada compra o ingreso como un lote único con su propio costo y fecha de vencimiento.")

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

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_para_ingreso():
    """Carga el catálogo de productos y el historial completo de ingresos desde Supabase."""
    if supabase:
        try:
            res_productos = supabase.table('Productos').select("Codigo, Producto").order('Producto').execute()
            df_productos = pd.DataFrame(res_productos.data)
            
            res_ingresos = supabase.table('Ingresos').select("*").order('created_at', desc=True).execute()
            df_ingresos_todos = pd.DataFrame(res_ingresos.data)
            
            return df_productos, df_ingresos_todos
        except Exception as e:
            st.error(f"Error al cargar datos de Supabase: {e}")
    return pd.DataFrame(), pd.DataFrame()

# --- CARGA DE DATOS ---
df_productos, df_historial_ingresos = cargar_datos_para_ingreso()

# --- INTERFAZ DE REGISTRO DE INGRESO (Formulario principal sin cambios) ---
with st.expander("📝 Registrar Nuevo Lote de Ingreso", expanded=True):
    # (El código del formulario para añadir un nuevo ingreso se mantiene igual)
    # ...
    pass

# --- DIÁLOGOS DE EDICIÓN Y ELIMINACIÓN ---
# Diálogo de Edición
if st.session_state.editing_ingreso_id:
    ingreso_a_editar = df_historial_ingresos[df_historial_ingresos['id'] == st.session_state.editing_ingreso_id].iloc[0]
    
    @st.dialog("✏️ Editar Registro de Ingreso")
    def edit_dialog():
        with st.form("edit_ingreso_form"):
            st.write(f"**Editando Lote:** {ingreso_a_editar['Codigo_Lote']}")
            
            # Convertir fechas de string a objeto date para el widget
            fecha_ingreso_val = datetime.strptime(ingreso_a_editar['Fecha'], '%Y-%m-%d').date()
            fecha_vencimiento_val = datetime.strptime(ingreso_a_editar['Fecha_Vencimiento'], '%Y-%m-%d').date() if ingreso_a_editar['Fecha_Vencimiento'] else None

            st.markdown("##### Información del Lote")
            col1, col2 = st.columns(2)
            with col1:
                new_cantidad = st.number_input("Cantidad", value=float(ingreso_a_editar['Cantidad']))
                new_proveedor = st.text_input("Proveedor", value=ingreso_a_editar['Proveedor'])
                new_fecha_ingreso = st.date_input("Fecha de Ingreso", value=fecha_ingreso_val)
            with col2:
                new_precio = st.number_input("Precio Unitario", value=float(ingreso_a_editar['Precio_Unitario']))
                new_factura = st.text_input("Factura", value=ingreso_a_editar['Factura'])
                new_fecha_venc = st.date_input("Fecha de Vencimiento", value=fecha_vencimiento_val)

            col_submit1, col_submit2 = st.columns(2)
            if col_submit1.form_submit_button("💾 Guardar Cambios"):
                try:
                    update_data = {
                        'Cantidad': new_cantidad,
                        'Proveedor': new_proveedor,
                        'Fecha': new_fecha_ingreso.strftime('%Y-%m-%d'),
                        'Precio_Unitario': new_precio,
                        'Factura': new_factura,
                        'Fecha_Vencimiento': new_fecha_venc.strftime('%Y-%m-%d') if new_fecha_venc else None
                    }
                    supabase.table('Ingresos').update(update_data).eq('id', st.session_state.editing_ingreso_id).execute()
                    st.toast("✅ Registro actualizado.")
                    st.session_state.editing_ingreso_id = None
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al actualizar: {e}")
            
            if col_submit2.form_submit_button("❌ Cancelar"):
                st.session_state.editing_ingreso_id = None
                st.rerun()
    edit_dialog()

# Diálogo de Eliminación
if st.session_state.deleting_ingreso_id:
    ingreso_a_eliminar = df_historial_ingresos[df_historial_ingresos['id'] == st.session_state.deleting_ingreso_id].iloc[0]
    @st.dialog("🗑️ Confirmar Eliminación")
    def delete_dialog():
        st.warning(f"¿Estás seguro de que quieres eliminar el ingreso del lote **'{ingreso_a_eliminar['Codigo_Lote']}'**?")
        st.write(f"Producto: **{ingreso_a_eliminar['Producto']}** | Cantidad: **{ingreso_a_eliminar['Cantidad']}**")
        st.write("Esta acción no se puede deshacer.")
        col1, col2 = st.columns(2)
        if col1.button("Sí, Eliminar Permanentemente"):
            supabase.table('Ingresos').delete().eq('id', st.session_state.deleting_ingreso_id).execute()
            st.toast("✅ Registro eliminado.")
            st.session_state.deleting_ingreso_id = None
            st.cache_data.clear()
            st.rerun()
        if col2.button("No, Cancelar"):
            st.session_state.deleting_ingreso_id = None
            st.rerun()
    delete_dialog()

# --- HISTORIAL DE INGRESOS RECIENTES ---
st.divider()
st.header("📚 Historial de Ingresos Recientes")
if not df_historial_ingresos.empty:
    columnas_a_mostrar = [
        'Fecha', 'Producto', 'Cantidad', 'Precio_Unitario', 
        'Codigo_Lote', 'Proveedor', 'Factura', 'Fecha_Vencimiento'
    ]
    df_display = df_historial_ingresos[['id'] + [col for col in columnas_a_mostrar if col in df_historial_ingresos.columns]]

    # Creamos una cuadrícula para mostrar los datos con botones
    for index, row in df_display.head(15).iterrows():
        with st.container(border=True):
            col_data, col_buttons = st.columns([10, 2])
            with col_data:
                cols = st.columns(4)
                cols[0].metric("Fecha", pd.to_datetime(row['Fecha']).strftime('%d/%m/%Y'))
                cols[1].metric("Producto", str(row['Producto']))
                cols[2].metric("Cantidad", f"{row['Cantidad']:.2f}")
                cols[3].metric("Precio Unitario", f"S/ {row['Precio_Unitario']:.2f}")
                st.caption(f"Lote: {row['Codigo_Lote']} | Factura: {row['Factura']} | Proveedor: {row['Proveedor']}")

            with col_buttons:
                st.write("") # Espacio para alinear botones
                st.write("")
                b_col1, b_col2 = st.columns(2)
                if b_col1.button("✏️", key=f"edit_{row['id']}", help="Editar este registro"):
                    st.session_state.editing_ingreso_id = row['id']
                    st.rerun()
                if b_col2.button("🗑️", key=f"delete_{row['id']}", help="Eliminar este registro"):
                    st.session_state.deleting_ingreso_id = row['id']
                    st.rerun()
else:
    st.info("Aún no se ha registrado ningún ingreso.")
