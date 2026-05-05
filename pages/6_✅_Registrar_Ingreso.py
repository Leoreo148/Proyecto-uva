import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ValidationError, field_validator

# --- LIBRERÍAS PRO ---
from supabase import create_client, Client
from streamlit_searchbox import st_searchbox
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
from streamlit_extras.stylable_container import stylable_container
try:
    from streamlit_extras.mandatory_fill import mandatory_fill
except ImportError:
    # Si falla, creamos una función "falsa" que no haga nada para que la app no explote
    def mandatory_fill(func):
        return func

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Agroq - Gestión de Ingresos", page_icon="🚜", layout="wide")

# --- MODELO DE VALIDACIÓN (PYDANTIC) ---
class IngresoSchema(BaseModel):
    """Validador estricto para evitar basura en la base de datos."""
    Codigo_Producto: str
    Codigo_Lote: str
    Fecha_Recepcion: date
    Cantidad_Ingresada: float
    Precio_Unitario_PEN: float = 0.0
    Precio_Unitario_USD: float = 0.0
    Proveedor: Optional[str] = None
    Factura: Optional[str] = None
    Guia_Remision: Optional[str] = None
    Cod_Operacion_Pago: Optional[str] = None

    @field_validator('Cantidad_Ingresada', 'Precio_Unitario_PEN')
    def must_be_positive(cls, v):
        if v < 0: raise ValueError('Debe ser un valor positivo')
        return v

# --- CONEXIÓN SUPABASE ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- FUNCIONES DE DATOS ---
@st.cache_data(ttl=60)
def get_products():
    res = supabase.table('Productos').select("Codigo, Producto").execute()
    return pd.DataFrame(res.data)

def get_history():
    try:
        # 1. Traemos los datos de Ingresos y Productos por separado
        res_i = supabase.table('Ingresos').select("*").order('created_at', desc=True).execute()
        res_p = supabase.table('Productos').select("Codigo, Producto").execute()
        
        df_i = pd.DataFrame(res_i.data)
        df_p = pd.DataFrame(res_p.data)
        
        if df_i.empty: 
            return pd.DataFrame()
        if df_p.empty: 
            return df_i # Si no hay catálogo, al menos mostramos los códigos
        
        # 2. Unión manual en memoria (Python es rapidísimo haciendo esto)
        df_final = pd.merge(df_i, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
        
        # 3. Limpieza de columnas duplicadas
        if 'Codigo_y' in df_final.columns:
            df_final = df_final.drop(columns=['Codigo_y']).rename(columns={'Codigo_x': 'Codigo'})
            
        return df_final
    except Exception as e:
        st.error(f"Error cargando historial: {e}")
        return pd.DataFrame()

# --- LÓGICA DE CARGA MASIVA (EXCEL/CSV) ---
def process_bulk_upload(file):
    try:
        # Detectar si es CSV o Excel
        if file.name.endswith('.csv'):
            df_raw = pd.read_csv(file)
        else:
            df_raw = pd.read_excel(file)
        
        # Limpieza básica de columnas "Unnamed" y espacios
        df_raw = df_raw.loc[:, ~df_raw.columns.str.contains('^Unnamed')]
        df_raw.columns = df_raw.columns.str.strip()

        # Mapeo inteligente (ajusta según los nombres de tus columnas de Excel)
        # Aquí buscamos coincidencias con lo que vimos en tus archivos
        mapping = {
            'COD. PROD': 'Codigo_Producto',
            'LOTE': 'Codigo_Lote',
            'CANT.ING.': 'Cantidad_Ingresada',
            'PREC. UNI S/.': 'Precio_Unitario_PEN',
            'PREC. UNI $.': 'Precio_Unitario_USD',
            'F.DE ING.': 'Fecha_Recepcion',
            'PROVEEDOR': 'Proveedor',
            'FACTURA': 'Factura',
            'GUIA REMISIÓN': 'Guia_Remision',
            'DEPOSITO (BCP_COD)': 'Cod_Operacion_Pago'
        }
        
        df_mapped = df_raw.rename(columns=mapping)
        
        registros_validados = []
        errores = []

        for i, row in df_mapped.iterrows():
            try:
                # Convertir fechas de Excel a objeto date
                if isinstance(row.get('Fecha_Recepcion'), str):
                    f_rec = datetime.strptime(row['Fecha_Recepcion'], '%Y-%m-%d').date()
                else:
                    f_rec = row.get('Fecha_Recepcion')

                obj = IngresoSchema(
                    Codigo_Producto=str(row.get('Codigo_Producto')),
                    Codigo_Lote=str(row.get('Codigo_Lote')),
                    Fecha_Recepcion=f_rec,
                    Cantidad_Ingresada=float(row.get('Cantidad_Ingresada', 0)),
                    Precio_Unitario_PEN=float(row.get('Precio_Unitario_PEN', 0)),
                    Precio_Unitario_USD=float(row.get('Precio_Unitario_USD', 0)),
                    Proveedor=str(row.get('Proveedor', '')),
                    Factura=str(row.get('Factura', '')),
                    Guia_Remision=str(row.get('Guia_Remision', '')),
                    Cod_Operacion_Pago=str(row.get('Cod_Operacion_Pago', ''))
                )
                registros_validados.append(obj.model_dump(mode='json'))
            except Exception as e:
                errores.append(f"Fila {i+2}: {e}")

        return registros_validados, errores
    except Exception as e:
        st.error(f"Error procesando archivo: {e}")
        return [], [str(e)]

# --- INTERFAZ ---
st.title("📥 Gestión de Ingresos y Lotes")

tabs = st.tabs(["Individual", "Carga Masiva (Excel)", "Historial y Kardex"])

# --- TAB 1: REGISTRO INDIVIDUAL ---
with tabs[0]:
    df_p = get_products()
    
    with st.form("form_registro"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # SEARCHBOX: Buscador inteligente de productos
            def search_products(searchterm: str):
                if not searchterm: return []
                filtered = df_p[df_p['Producto'].str.contains(searchterm, case=False) | 
                                df_p['Codigo'].str.contains(searchterm, case=False)]
                return [(f"{row['Producto']} ({row['Codigo']})", row['Codigo']) for _, row in filtered.iterrows()]

            cod_prod = st_searchbox(search_products, key="prod_search", label="Buscar Producto")
            lote = st.text_input("Código de Lote", placeholder="Ej: L2026-001")
            fecha = st.date_input("Fecha Recepción", value=datetime.now().date())
            
        with col2:
            cant = st.number_input("Cantidad", min_value=0.0, step=0.1)
            p_pen = st.number_input("Precio Unitario (S/)", min_value=0.0)
            p_usd = st.number_input("Precio Unitario ($)", min_value=0.0)
            
        with col3:
            prov = st.text_input("Proveedor")
            fact = st.text_input("N° Factura")
            guia = st.text_input("Guía de Remisión")

        with stylable_container("green_button", css_styles="button {background-color: #28a745; color: white;}"):
            submit = st.form_submit_button("Guardar Registro")

        if submit:
            if not cod_prod or not lote:
                st.error("Producto y Lote son obligatorios.")
            else:
                try:
                    nuevo = IngresoSchema(
                        Codigo_Producto=cod_prod, Codigo_Lote=lote, Fecha_Recepcion=fecha,
                        Cantidad_Ingresada=cant, Precio_Unitario_PEN=p_pen, Precio_Unitario_USD=p_usd,
                        Proveedor=prov, Factura=fact, Guia_Remision=guia
                    )
                    supabase.table('Ingresos').insert(nuevo.model_dump(mode='json')).execute()
                    st.success("¡Lote registrado exitosamente!")
                    st.cache_data.clear()
                except ValidationError as e:
                    st.error(f"Error de validación: {e}")

# --- TAB 2: CARGA MASIVA ---
with tabs[1]:
    st.subheader("Subida masiva desde Excel/CSV")
    uploaded_file = st.file_uploader("Arrastra tu archivo aquí", type=['xlsx', 'csv'])
    
    if uploaded_file:
        data, errs = process_bulk_upload(uploaded_file)
        if errs:
            with st.expander("⚠️ Errores encontrados"):
                for e in errs: st.write(e)
        
        st.write(f"Registros listos para subir: {len(data)}")
        if st.button("🚀 Confirmar Subida a Supabase"):
            with st.status("Subiendo datos...", expanded=True) as status:
                # Subir en bloques de 100 para no saturar
                for i in range(0, len(data), 100):
                    batch = data[i:i+100]
                    supabase.table('Ingresos').insert(batch).execute()
                status.update(label="¡Carga masiva completada!", state="complete")
                st.cache_data.clear()

# --- TAB 3: HISTORIAL (AG-GRID) ---
with tabs[2]:
    df_hist = get_history()
    if not df_hist.empty:
        st.write("Usa los filtros de cada columna para buscar lotes específicos.")
        
        gb = GridOptionsBuilder.from_dataframe(df_hist[[
            'Fecha_Recepcion', 'Producto', 'Codigo_Lote', 'Cantidad_Ingresada', 
            'Precio_Unitario_PEN', 'Proveedor', 'Factura'
        ]])
        gb.configure_pagination(paginationAutoPageSize=True)
        gb.configure_side_bar() # Filtros laterales
        gb.configure_default_column(groupable=True, value=True, enableRowGroup=True, aggFunc='sum', editable=False)
        
        grid_options = gb.build()
        
        AgGrid(
            df_hist,
            gridOptions=grid_options,
            columns_auto_size_mode=ColumnsAutoSizeMode.FIT_CONTENTS,
            theme='balham', # Tema profesional
            height=500
        )
    else:
        st.info("No hay datos en el historial.")