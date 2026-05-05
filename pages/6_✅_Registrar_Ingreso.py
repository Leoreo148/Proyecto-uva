import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ValidationError, field_validator
from supabase import create_client, Client
from streamlit_searchbox import st_searchbox
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
from streamlit_extras.stylable_container import stylable_container

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Ingresos", page_icon="🚜", layout="wide")

class IngresoSchema(BaseModel):
    Codigo_Producto: str
    Codigo_Lote: str
    Fecha_Recepcion: date
    Cantidad_Ingresada: float
    Precio_Unitario_PEN: float = 0.0
    Proveedor: Optional[str] = None
    Factura: Optional[str] = None

    @field_validator('Cantidad_Ingresada', 'Precio_Unitario_PEN')
    def must_be_positive(cls, v):
        if v < 0: raise ValueError('Debe ser un valor positivo')
        return v

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- DATOS ---
@st.cache_data(ttl=60)
def get_products():
    res = supabase.table('Productos').select("Codigo, Producto").execute()
    return pd.DataFrame(res.data)

def get_history():
    try:
        res_i = supabase.table('Ingresos').select("*").order('created_at', desc=True).execute()
        res_p = supabase.table('Productos').select("Codigo, Producto").execute()
        df_i, df_p = pd.DataFrame(res_i.data), pd.DataFrame(res_p.data)
        if df_i.empty: return pd.DataFrame()
        return pd.merge(df_i, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    except Exception as e:
        st.error(f"Error: {e}")
        return pd.DataFrame()

# --- INTERFAZ ---
st.title("📥 Registro Diario de Ingresos")

# FORMULARIO MANUAL
df_p = get_products()
with st.form("form_registro"):
    c1, c2, c3 = st.columns(3)
    with c1:
        def search_products(searchterm: str):
            if not searchterm: return []
            filtered = df_p[df_p['Producto'].str.contains(searchterm, case=False) | 
                            df_p['Codigo'].str.contains(searchterm, case=False)]
            return [(f"{row['Producto']} ({row['Codigo']})", row['Codigo']) for _, row in filtered.iterrows()]
        
        cod_prod = st_searchbox(search_products, key="prod_search", label="Buscar Producto")
        lote = st.text_input("Código de Lote")
        fecha = st.date_input("Fecha Recepción", value=date.today())
    with c2:
        cant = st.number_input("Cantidad", min_value=0.0)
        p_pen = st.number_input("Precio Unitario (S/)", min_value=0.0)
    with c3:
        prov = st.text_input("Proveedor")
        fact = st.text_input("N° Factura")

    if st.form_submit_button("💾 Guardar Ingreso"):
        if cod_prod and lote:
            try:
                nuevo = IngresoSchema(
                    Codigo_Producto=cod_prod, Codigo_Lote=lote, Fecha_Recepcion=fecha,
                    Cantidad_Ingresada=cant, Precio_Unitario_PEN=p_pen, Proveedor=prov, Factura=fact
                )
                supabase.table('Ingresos').insert(nuevo.model_dump(mode='json')).execute()
                st.success("¡Registrado!")
                st.cache_data.clear()
                st.rerun()
            except Exception as e: st.error(e)

# HISTORIAL
st.divider()
st.subheader("📋 Historial Reciente")
df_hist = get_history()
if not df_hist.empty:
    gb = GridOptionsBuilder.from_dataframe(df_hist[['Fecha_Recepcion', 'Producto', 'Codigo_Lote', 'Cantidad_Ingresada', 'Precio_Unitario_PEN', 'Proveedor']])
    gb.configure_pagination(paginationPageSize=10)
    gb.configure_default_column(filterable=True, sortable=True)
    AgGrid(df_hist, gridOptions=gb.build(), theme='balham', height=400)