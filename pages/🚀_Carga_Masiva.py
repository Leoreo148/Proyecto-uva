import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Datos Históricos (Build 8.7 - Fix Duplicados)")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def desduplicar_titulos_raw(lista_sucia):
    """Añade sufijos numéricos a nombres idénticos en el Excel original."""
    nueva_lista = []
    conteos = {}
    for item in lista_sucia:
        val = str(item).strip().upper()
        if val in conteos:
            conteos[val] += 1
            nueva_lista.append(f"{val}_{conteos[val]}")
        else:
            conteos[val] = 0
            nueva_lista.append(val)
    return nueva_lista

def detectar_y_limpiar(file):
    df = pd.read_excel(file, header=None)
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        if any("COD" in str(s) for s in fila) and any("PROD" in str(s) for s in fila):
            new_df = df.iloc[i+1:].copy()
            titulos_originales = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            # Paso 1: Desduplicar nombres del Excel original
            new_df.columns = desduplicar_titulos_raw(titulos_originales)
            return new_df.reset_index(drop=True)
    return df.reset_index(drop=True)

uploaded_file = st.file_uploader("Sube el archivo Excel", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar(uploaded_file)
    st.write("📋 Columnas detectadas en el archivo:", list(df_raw.columns))

    # MAPPING INTEGRAL
    mapping = {
        'F.DE ING.': 'Fecha_Recepcion',
        'FECHA': 'Fecha_Recepcion', 
        'COD. PROD.': 'Codigo_Producto',
        'COD. PROD': 'Codigo_Producto',
        'COD ING': 'Codigo_Lote',
        'LOTE': 'Codigo_Lote',
        'CANT.ING.': 'Cantidad_Ingresada',
        'CANT.': 'Cantidad_Ingresada',
        'PREC. UNI S/.': 'Precio_Unitario_PEN',
        'PROVEEDOR': 'Proveedor',
        'FACTURA': 'Factura',
        'GUIA REMISIÓN': 'Guia_Remision',
        'DEPOSITO (BCP_COD)': 'Cod_Operacion_Pago'
    }

    # 1. Renombrar columnas según el mapping
    df_mapped = df_raw.rename(columns=mapping)

    # 2. ELIMINAR DUPLICADOS FÍSICOS (CRÍTICO)
    # Si después de renombrar tenemos dos 'Codigo_Lote', esto borra el segundo
    df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated(keep='first')]

    # 3. Selección de columnas finales para migración
    vistos = set()
    columnas_finales = []
    for col in df_mapped.columns:
        if col in mapping.values() and col not in vistos:
            columnas_finales.append(col)
            vistos.add(col)

    if 'Codigo_Producto' not in vistos or 'Codigo_Lote' not in vistos:
        st.error("❌ Columnas básicas no encontradas. Verifica el nombre de los títulos en tu Excel.")
    else:
        # Creamos el dataframe de migración con columnas garantizadas únicas
        df_migracion = df_mapped[columnas_finales].copy().reset_index(drop=True)
        
        # Limpieza de nulos
        df_migracion = df_migracion.dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        try:
            # 4. Procesamiento de fecha seguro
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])
            
            st.success(f"✅ Estructura validada: {len(df_migracion)} registros listos.")
            st.dataframe(df_migracion.head(10))

            if st.button("🚀 Iniciar Subida"):
                data_dict = df_migracion.to_dict(orient='records')
                progress = st.progress(0)
                
                for i in range(0, len(data_dict), 100):
                    batch = data_dict[i:i+100]
                    supabase.table('Ingresos').insert(batch).execute()
                    progress.progress(min((i + 100) / len(data_dict), 1.0))
                
                st.balloons()
                st.success("¡Migración de datos históricos terminada!")
                
        except Exception as e:
            st.error(f"Error en el procesamiento de datos: {e}")