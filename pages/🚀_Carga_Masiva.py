import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Datos Históricos")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def detectar_y_limpiar(file):
    # Leemos el Excel
    df = pd.read_excel(file, header=None)
    
    # Buscamos la fila de cabecera real
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        # Buscamos indicios de que esta es la fila de títulos
        if any("COD" in str(s) for s in fila) and any("PROD" in str(s) for s in fila):
            new_df = df.iloc[i+1:].copy()
            # Limpiamos nombres de columnas
            titulos = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            new_df.columns = titulos
            return new_df
    return df

uploaded_file = st.file_uploader("Sube el archivo Excel", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar(uploaded_file)
    
    # Limpieza preventiva de nombres de columnas duplicados antes del mapping
    df_raw.columns = pd.io.common.dedup_names(df_raw.columns, is_case_sensitive=False)
    df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]

    st.write("📋 Columnas detectadas en el archivo:", list(df_raw.columns))

    # MAPPING INTELIGENTE (Priorizando nombres de la hoja de Ingresos)
    # Si existen FECHA y F.DE ING, el mapping debe ser único
    mapping = {
        'F.DE ING.': 'Fecha_Recepcion',
        'FECHA': 'Fecha_Recepcion', 
        'COD. PROD.': 'Codigo_Producto',
        'COD. PROD': 'Codigo_Producto',
        'COD ING': 'Codigo_Lote',
        'LOTE': 'Codigo_Lote',
        'CANT.ING.': 'Cantidad_Ingresada',
        'PREC. UNI S/.': 'Precio_Unitario_PEN',
        'PROVEEDOR': 'Proveedor',
        'FACTURA': 'Factura'
    }

    # Aplicamos el renombramiento
    df_ready = df_raw.rename(columns=mapping)

    # SEGURIDAD: Si hay columnas duplicadas con el mismo nombre de destino, nos quedamos con la primera
    df_ready = df_ready.loc[:, ~df_ready.columns.duplicated()]

    if 'Codigo_Producto' not in df_ready.columns or 'Codigo_Lote' not in df_ready.columns:
        st.error("No se encontraron las columnas base (Producto/Lote). Verifica que estés en la pestaña correcta.")
    else:
        # 1. Filtramos columnas que existen en nuestra tabla de Supabase
        cols_finales = [v for v in mapping.values() if v in df_ready.columns]
        df_migracion = df_ready[cols_finales].copy()

        # 2. Limpieza de datos críticos
        df_migracion = df_migracion.dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        # 3. Conversión de fecha segura
        # Al haber eliminado duplicados arriba, esto ya no debería fallar
        df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
        df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])

        st.success(f"✅ ¡Estructura lista! Se procesarán {len(df_migracion)} filas.")
        st.dataframe(df_migracion.head(10))

        if st.button("🚀 Iniciar Subida"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            
            for i in range(0, len(data_dict), 100):
                batch = data_dict[i:i+100]
                supabase.table('Ingresos').insert(batch).execute()
                progress.progress(min((i + 100) / len(data_dict), 1.0))
            
            st.balloons()
            st.success("Migración completada.")