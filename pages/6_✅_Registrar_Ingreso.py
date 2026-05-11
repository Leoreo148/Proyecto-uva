import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ValidationError, field_validator
from supabase import create_client, Client
from streamlit_searchbox import st_searchbox
from st_aggrid import AgGrid, GridOptionsBuilder, ColumnsAutoSizeMode
from streamlit_extras.stylable_container import stylable_container

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Ingresos Pro", page_icon="📥", layout="wide")

# Inyectamos CSS para suavizar el blanco y mejorar el contraste
st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    .stHeader { background-color: #1e3d33; }
    div[data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ESQUEMA DE DATOS AUDITADO (Basado en Excel) ---
class IngresoSchema(BaseModel):
    Codigo_Producto: str
    Codigo_Lote: str
    Fecha_Recepcion: date
    Fecha_Vencimiento: Optional[date] = None # <-- NUEVO
    Cantidad_Ingresada: float
    Precio_Unitario_PEN: float = 0.0
    Proveedor: Optional[str] = None
    Factura: Optional[str] = None
    Guia_Remision: Optional[str] = None      # <-- NUEVO
    Observaciones: Optional[str] = None       # <-- NUEVO

    @field_validator('Cantidad_Ingresada', 'Precio_Unitario_PEN')
    def must_be_positive(cls, v):
        if v < 0: raise ValueError('Debe ser un valor positivo')
        return v

# --- 3. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. FUNCIONES DE CARGA ---
@st.cache_data(ttl=60)
def get_products():
    res = supabase.table('Productos').select("Codigo, Producto").execute()
    df = pd.DataFrame(res.data)
    return df if not df.empty else pd.DataFrame(columns=['Codigo', 'Producto'])

def get_history():
    try:
        res_i = supabase.table('Ingresos').select("*").order('created_at', desc=True).limit(100).execute()
        res_p = supabase.table('Productos').select("Codigo, Producto").execute()
        df_i, df_p = pd.DataFrame(res_i.data), pd.DataFrame(res_p.data)
        if df_i.empty: return pd.DataFrame()
        if df_p.empty: 
            df_i['Producto'] = "N/A"
            return df_i
        return pd.merge(df_i, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    except Exception as e:
        return pd.DataFrame()

# --- 5. INTERFAZ DE USUARIO ---
with stylable_container(key="title_container", css_styles="""{ background-color: #1e3d33; color: white; padding: 1.5rem; border-radius: 1rem; margin-bottom: 2rem; }"""):
    st.title("📥 Registro Maestro de Ingresos")
    st.write("Auditoría de almacén y control de compras.")

df_p = get_products()

# FORMULARIO DE REGISTRO
with st.form("form_registro", clear_on_submit=True):
    st.markdown("##### 📝 Información del Producto")
    c1, c2, c3 = st.columns(3)
    
    with c1:
        def search_products(searchterm: str):
            # 1. Verificamos que haya algo escrito y que los datos existan
            if not searchterm or df_p.empty: 
                return []
            
            # 2. El truco: agregamos 'na=False' para que los nulos no rompan el filtro
            # También usamos .astype(str) por si acaso hay códigos numéricos
            mask = (
                df_p['Producto'].astype(str).str.contains(searchterm, case=False, na=False) | 
                df_p['Codigo'].astype(str).str.contains(searchterm, case=False, na=False)
            )
            
            filtered = df_p[mask]
            
            # 3. Retornamos máximo 15 resultados para que el celular no sufra
            return [(f"{row['Producto']} ({row['Codigo']})", row['Codigo']) for _, row in filtered.head(15).iterrows()]
        
        cod_prod = st_searchbox(search_products, key="prod_search", label="Seleccionar Producto")
        lote = st.text_input("Código de Lote / Batch")
    
    with c2:
        cant = st.number_input("Cantidad Ingresada", min_value=0.0, step=0.01)
        p_pen = st.number_input("Precio Unitario (S/)", min_value=0.0, step=0.01)
    
    with c3:
        fecha_rec = st.date_input("Fecha de Recepción", value=date.today())
        fecha_venc = st.date_input("Fecha de Vencimiento", value=date.today().replace(year=date.today().year + 2))

    st.divider()
    st.markdown("##### 🚛 Datos Logísticos y Documentos")
    c4, c5, c6 = st.columns(3)
    
    with c4:
        prov = st.text_input("Proveedor")
    with c5:
        fact = st.text_input("N° de Factura")
    with c6:
        guia = st.text_input("Guía de Remisión")
    
    obs = st.text_area("Observaciones Adicionales", placeholder="Ej: Sacos con humedad, entrega parcial, etc.")

    if st.form_submit_button("💾 Confirmar Ingreso a Almacén", use_container_width=True):
        if cod_prod and lote and cant > 0:
            try:
                nuevo = IngresoSchema(
                    Codigo_Producto=cod_prod, Codigo_Lote=lote, Fecha_Recepcion=fecha_rec,
                    Fecha_Vencimiento=fecha_venc, Cantidad_Ingresada=cant, Precio_Unitario_PEN=p_pen,
                    Proveedor=prov, Factura=fact, Guia_Remision=guia, Observaciones=obs
                )
                supabase.table('Ingresos').insert(nuevo.model_dump(mode='json')).execute()
                st.success("✅ Ingreso registrado correctamente en la base de datos.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar: {e}")
        else:
            st.error("⚠️ Producto, Lote y Cantidad son campos obligatorios.")

# HISTORIAL DINÁMICO
st.divider()
st.subheader("📋 Historial de Movimientos")
df_hist = get_history()

if not df_hist.empty:
    cols_visibles = ['Fecha_Recepcion', 'Producto', 'Codigo_Lote', 'Cantidad_Ingresada', 'Precio_Unitario_PEN', 'Proveedor', 'Factura']
    cols_reales = [c for c in cols_visibles if c in df_hist.columns]
    
    gb = GridOptionsBuilder.from_dataframe(df_hist[cols_reales])
    gb.configure_pagination(paginationPageSize=10)
    gb.configure_default_column(filterable=True, sortable=True)
    AgGrid(df_hist[cols_reales], gridOptions=gb.build(), theme='balham', height=400)
else:
    st.info("No se encontraron registros de ingresos previos.")