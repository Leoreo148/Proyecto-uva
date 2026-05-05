import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client
import re

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Datos Históricos (Build 8.8 - Limpieza Numérica)")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNCIONES DE LIMPIEZA ---
def desduplicar_titulos_raw(lista_sucia):
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

def limpiar_numero(valor):
    """Elimina cualquier carácter que no sea número o punto decimal."""
    if pd.isna(valor): return 0.0
    # Convertir a string y quitar todo excepto números y el punto
    s = str(valor)
    s_limpia = re.sub(r'[^0-9.]', '', s)
    try:
        return float(s_limpia) if s_limpia else 0.0
    except:
        return 0.0

def detectar_y_limpiar_excel(file):
    df = pd.read_excel(file, header=None)
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        if any("COD" in str(s) for s in fila) and any("PROD" in str(s) for s in fila):
            new_df = df.iloc[i+1:].copy()
            titulos = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            new_df.columns = desduplicar_titulos_raw(titulos)
            return new_df.reset_index(drop=True)
    return df.reset_index(drop=True)

# --- INTERFAZ ---
uploaded_file = st.file_uploader("Sube el archivo Excel", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar_excel(uploaded_file)
    
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
        'FACTURA': 'Factura'
    }

    df_mapped = df_raw.rename(columns=mapping)
    df_mapped = df_mapped.loc[:, ~df_mapped.columns.duplicated(keep='first')]

    vistos = set()
    columnas_finales = []
    for col in df_mapped.columns:
        if col in mapping.values() and col not in vistos:
            columnas_finales.append(col)
            vistos.add(col)

    if 'Codigo_Producto' not in vistos or 'Codigo_Lote' not in vistos:
        st.error("No se detectaron las columnas básicas.")
    else:
        df_migracion = df_mapped[columnas_finales].copy().reset_index(drop=True)
        df_migracion = df_migracion.dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        try:
            # 1. Limpieza de FECHAS
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])
            
            # 2. LIMPIEZA NUMÉRICA (Solución al error double precision)
            if 'Cantidad_Ingresada' in df_migracion.columns:
                df_migracion['Cantidad_Ingresada'] = df_migracion['Cantidad_Ingresada'].apply(limpiar_numero)
            
            if 'Precio_Unitario_PEN' in df_migracion.columns:
                df_migracion['Precio_Unitario_PEN'] = df_migracion['Precio_Unitario_PEN'].apply(limpiar_numero)

            st.success(f"✅ ¡Datos normalizados! {len(df_migracion)} filas listas.")
            st.dataframe(df_migracion.head(10))

            if st.button("🚀 Iniciar Subida"):
                data_dict = df_migracion.to_dict(orient='records')
                progress = st.progress(0)
                
                for i in range(0, len(data_dict), 100):
                    batch = data_dict[i:i+100]
                    supabase.table('Ingresos').insert(batch).execute()
                    progress.progress(min((i + 100) / len(data_dict), 1.0))
                
                st.balloons()
                st.success("¡Migración terminada exitosamente!")
                
        except Exception as e:
            st.error(f"Error técnico: {e}")