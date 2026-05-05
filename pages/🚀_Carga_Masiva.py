import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva", page_icon="🚀")
st.title("🚀 Importación Masiva de Datos (Excel)")
st.info("Esta sección es para la migración inicial de datos desde tus archivos históricos.")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

uploaded_file = st.file_uploader("Sube tu Excel o CSV", type=['xlsx', 'csv'])

if uploaded_file:
    df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith('xlsx') else pd.read_csv(uploaded_file)
    
    # DIAGNÓSTICO: Ver columnas reales
    st.write("Columnas detectadas en tu archivo:", list(df.columns))
    
    # MAPPING (Asegúrate que coincidan con las de arriba)
    mapping = {
        'COD. PROD': 'Codigo_Producto',
        'LOTE': 'Codigo_Lote',
        'CANT.ING.': 'Cantidad_Ingresada',
        'PREC. UNI S/.': 'Precio_Unitario_PEN',
        'F.DE ING.': 'Fecha_Recepcion',
        'PROVEEDOR': 'Proveedor',
        'FACTURA': 'Factura'
    }
    
    df_ready = df.rename(columns=mapping)
    
    # Filtrar solo las columnas que existen en el mapping
    cols_to_keep = [v for k, v in mapping.items() if v in df_ready.columns]
    df_ready = df_ready[cols_to_keep].dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
    
    # Convertir fechas
    df_ready['Fecha_Recepcion'] = pd.to_datetime(df_ready['Fecha_Recepcion']).dt.strftime('%Y-%m-%d')

    st.write(f"Registros listos para procesar: {len(df_ready)}")
    st.dataframe(df_ready.head())

    if st.button("🔥 Ejecutar Subida"):
        data = df_ready.to_dict(orient='records')
        with st.status("Subiendo a Supabase..."):
            for i in range(0, len(data), 100):
                supabase.table('Ingresos').insert(data[i:i+100]).execute()
        st.success("¡Migración completada!")