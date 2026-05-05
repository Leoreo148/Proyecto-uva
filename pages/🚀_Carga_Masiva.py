import streamlit as st
import pandas as pd
from supabase import create_client
import re

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración Maestra de Datos")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def desduplicar_columnas(columnas):
    nueva_lista = []
    conteos = {}
    for col in columnas:
        col_str = str(col).strip().upper()
        if col_str in conteos:
            conteos[col_str] += 1
            nueva_lista.append(f"{col_str}_{conteos[col_str]}")
        else:
            conteos[col_str] = 0
            nueva_lista.append(col_str)
    return nueva_lista

def detectar_y_limpiar(file):
    # Intentamos leer el Excel
    df = pd.read_excel(file, header=None)
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        # Buscamos indicios de cabecera (Palabras que aparecen en tus hojas)
        if any(k in str(s) for k in ["CODIGO", "PRODUCTO", "COD. PROD"] for s in fila):
            new_df = df.iloc[i+1:].copy()
            titulos = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            new_df.columns = desduplicar_columnas(titulos)
            return new_df.reset_index(drop=True)
    return df

# --- INTERFAZ DE SELECCIÓN ---
tipo_carga = st.radio("¿Qué datos vas a subir hoy?", 
                      ["Catálogo de Productos (Maestro)", "Historial de Ingresos (Compras)"])

uploaded_file = st.file_uploader(f"Sube el Excel de {tipo_carga}", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar(uploaded_file)
    st.write("📋 Columnas detectadas:", list(df_raw.columns))

    if tipo_carga == "Catálogo de Productos (Maestro)":
        # Mapeo para la tabla 'Productos' (Basado en tu hoja Cod_Producto)
        mapping = {
            'CODIGO': 'Codigo',
            'PRODUCTOS': 'Producto',
            'UM': 'Unidad',
            'SUBGRUPO': 'Tipo_Accion',
            'ING. ACTIVO': 'Ingrediente_Activo'
        }
        target_table = "Productos"
        subset_keys = ['Codigo', 'Producto']
    else:
        # Mapeo para la tabla 'Ingresos' (Basado en tu hoja Ingreso)
        mapping = {
            'COD. PROD.': 'Codigo_Producto',
            'COD. PROD': 'Codigo_Producto',
            'COD ING': 'Codigo_Lote',
            'LOTE': 'Codigo_Lote',
            'CANT.ING.': 'Cantidad_Ingresada',
            'PREC. UNI S/.': 'Precio_Unitario_PEN',
            'F.DE ING.': 'Fecha_Recepcion'
        }
        target_table = "Ingresos"
        subset_keys = ['Codigo_Producto', 'Codigo_Lote']

    df_ready = df_raw.rename(columns=mapping)
    df_ready = df_ready.loc[:, ~df_ready.columns.duplicated()]
    
    # Filtrar solo columnas que existen en el mapping y en el DF
    cols_finales = [v for v in mapping.values() if v in df_ready.columns]
    
    if not all(k in df_ready.columns for k in subset_keys):
        st.error(f"Faltan columnas críticas para {tipo_carga}. Revisa los nombres en el Excel.")
    else:
        df_migracion = df_ready[cols_finales].dropna(subset=subset_keys).copy()
        
        # Limpieza de fechas si es Ingresos
        if 'Fecha_Recepcion' in df_migracion.columns:
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])

        st.success(f"✅ {len(df_migracion)} registros listos para la tabla '{target_table}'.")
        st.dataframe(df_migracion.head(10))

        if st.button(f"🚀 Subir a {target_table}"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            for i in range(0, len(data_dict), 100):
                batch = data_dict[i:i+100]
                supabase.table(target_table).insert(batch).execute()
                progress.progress(min((i + 100) / len(data_dict), 1.0))
            st.balloons()
            st.success(f"¡{tipo_carga} cargado con éxito!")