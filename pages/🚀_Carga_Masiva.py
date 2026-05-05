import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Inventario Histórico")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- LÓGICA DE DETECCIÓN DE CABECERAS ---
def limpiar_excel(df):
    """Busca la fila donde realmente están los títulos."""
    # Buscamos una fila que contenga palabras clave como 'COD' o 'PRODUCTO'
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper()
        if any(fila.str.contains("COD", na=False)) or any(fila.str.contains("PROD", na=False)):
            # Encontramos la fila de títulos
            new_df = df.iloc[i+1:].copy() # Los datos empiezan una fila después
            new_df.columns = df.iloc[i].values # Ponemos los títulos correctos
            return new_df
    return df

uploaded_file = st.file_uploader("Sube tu Excel histórico", type=['xlsx', 'csv'])

if uploaded_file:
    # Leemos sin procesar primero
    df_raw = pd.read_excel(uploaded_file)
    
    # 1. Intentar limpiar el Excel si hay filas vacías arriba
    st.write("🔍 Analizando estructura del archivo...")
    df_clean = limpiar_excel(df_raw)
    
    # Limpiar espacios en los nombres de las columnas
    df_clean.columns = [str(c).strip().upper() for c in df_clean.columns]
    
    st.write("Columnas detectadas ahora:", list(df_clean.columns))
    
    # 2. MAPPING AGRESIVO (Añade aquí todas las variaciones que veas en tus Excels)
    mapping = {
        'COD. PROD': 'Codigo_Producto',
        'COD.PROD': 'Codigo_Producto',
        'CODIGO': 'Codigo_Producto',
        'LOTE': 'Codigo_Lote',
        'LOTES': 'Codigo_Lote',
        'CANT.ING.': 'Cantidad_Ingresada',
        'CANTIDAD': 'Cantidad_Ingresada',
        'PREC. UNI S/.': 'Precio_Unitario_PEN',
        'PRECIO': 'Precio_Unitario_PEN',
        'F.DE ING.': 'Fecha_Recepcion',
        'FECHA': 'Fecha_Recepcion',
        'PROVEEDOR': 'Proveedor',
        'FACTURA': 'Factura'
    }
    
    df_ready = df_clean.rename(columns=mapping)
    
    # 3. FILTRADO SEGURO
    # Buscamos qué columnas del mapping sí logramos rescatar
    cols_finales = [v for v in mapping.values() if v in df_ready.columns]
    
    if 'Codigo_Producto' not in df_ready.columns or 'Codigo_Lote' not in df_ready.columns:
        st.error("❌ No pude encontrar las columnas 'COD. PROD' o 'LOTE'. Revisa el nombre en tu Excel.")
        st.info("Sugerencia: Asegúrate de que los títulos no tengan celdas combinadas arriba.")
    else:
        # Limpiar filas basura al final
        df_ready = df_ready[cols_finales].dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        # Formatear fecha
        df_ready['Fecha_Recepcion'] = pd.to_datetime(df_ready['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
        df_ready = df_ready.dropna(subset=['Fecha_Recepcion']) # Adiós a las fechas mal escritas

        st.success(f"✅ ¡Estructura validada! {len(df_ready)} registros listos.")
        st.dataframe(df_ready.head(10))

        if st.button("🔥 Iniciar Subida a Base de Datos"):
            data = df_ready.to_dict(orient='records')
            barra = st.progress(0)
            with st.status("Subiendo datos en bloques...") as status:
                for i in range(0, len(data), 100):
                    batch = data[i:i+100]
                    supabase.table('Ingresos').insert(batch).execute()
                    barra.progress(min((i + 100) / len(data), 1.0))
            st.balloons()
            st.success("¡Migración terminada con éxito!")