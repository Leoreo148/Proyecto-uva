import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Datos Históricos")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# --- FUNCIÓN PARA ELIMINAR DUPLICADOS MANUALMENTE ---
def desduplicar_columnas(columnas):
    nueva_lista = []
    conteos = {}
    for col in columnas:
        col_str = str(col).strip().upper()
        if col_str in conteos:
            conteos[col_str] += 1
            nueva_lista.append(f"{col_str}.{conteos[col_str]}")
        else:
            conteos[col_str] = 0
            nueva_lista.append(col_str)
    return nueva_lista

def detectar_y_limpiar(file):
    df = pd.read_excel(file, header=None)
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        # Buscamos la fila que contiene los encabezados reales
        if any("COD" in str(s) for s in fila) and any("PROD" in str(s) for s in fila):
            new_df = df.iloc[i+1:].copy()
            titulos_sucios = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            # Aplicamos la desduplicación manual
            new_df.columns = desduplicar_columnas(titulos_sucios)
            return new_df
    return df

uploaded_file = st.file_uploader("Sube el archivo Excel", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar(uploaded_file)
    
    st.write("📋 Columnas procesadas:", list(df_raw.columns))

    # MAPPING ACTUALIZADO (Ajustado a los nombres que salieron en tu error)
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

    df_ready = df_raw.rename(columns=mapping)

    # Si después del mapeo quedaron dos columnas llamadas 'Fecha_Recepcion', nos quedamos con la primera
    df_ready = df_ready.loc[:, ~df_ready.columns.duplicated()]

    if 'Codigo_Producto' not in df_ready.columns or 'Codigo_Lote' not in df_ready.columns:
        st.error("No se encontraron 'Codigo_Producto' o 'Codigo_Lote'. Revisa los títulos del Excel.")
    else:
        # Filtramos solo lo que nos sirve
        cols_finales = [v for v in mapping.values() if v in df_ready.columns]
        df_migracion = df_ready[cols_finales].copy()

        # Limpieza de nulos
        df_migracion = df_migracion.dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        # Conversión de fecha segura (ahora sin errores de duplicados)
        df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
        df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])

        st.success(f"✅ Estructura validada. {len(df_migracion)} filas listas.")
        st.dataframe(df_migracion.head(10))

        if st.button("🚀 Iniciar Subida"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            status = st.empty()
            
            for i in range(0, len(data_dict), 100):
                batch = data_dict[i:i+100]
                supabase.table('Ingresos').insert(batch).execute()
                p = min((i + 100) / len(data_dict), 1.0)
                progress.progress(p)
                status.text(f"Progreso: {int(p*100)}%")
            
            st.balloons()
            st.success("¡Migración exitosa!")