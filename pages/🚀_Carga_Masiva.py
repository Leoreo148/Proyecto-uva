import streamlit as st
import pandas as pd
from datetime import date
from supabase import create_client

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración de Datos Históricos (Versión Ultra-Compatible)")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def desduplicar_lista(lista_sucia):
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
        # Buscamos indicios de cabecera real
        if any("COD" in str(s) for s in fila) and any("PROD" in str(s) for s in fila):
            new_df = df.iloc[i+1:].copy()
            # Limpieza profunda de nombres
            titulos = [str(c).strip().replace('\n', ' ') for c in df.iloc[i].values]
            new_df.columns = desduplicar_lista(titulos)
            return new_df.reset_index(drop=True)
    return df.reset_index(drop=True)

uploaded_file = st.file_uploader("Sube el archivo Excel", type=['xlsx'])

if uploaded_file:
    df_raw = detectar_y_limpiar(uploaded_file)
    st.write("📋 Columnas encontradas en el archivo:", list(df_raw.columns))

    # MAPPING AMPLIADO (Basado en los fragmentos de Ingreso y Salida)
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

    # 1. Renombrar columnas
    df_mapped = df_raw.rename(columns=mapping)

    # 2. SELECCIÓN ÚNICA: Evitar duplicados de nombres destino
    # Si mapeamos 'FECHA' y 'F.DE ING.' a 'Fecha_Recepcion', solo nos quedamos con una.
    columnas_finales = []
    vistos = set()
    
    # Priorizamos las columnas que están en nuestro mapping
    for col in df_mapped.columns:
        if col in mapping.values() and col not in vistos:
            columnas_finales.append(col)
            vistos.add(col)

    if 'Codigo_Producto' not in vistos or 'Codigo_Lote' not in vistos:
        st.error("❌ No se encontraron las columnas críticas (Producto o Lote).")
    else:
        # Creamos el dataframe final con columnas únicas y reseteamos el índice
        df_migracion = df_mapped[columnas_finales].copy().reset_index(drop=True)
        
        # Limpieza de nulos en datos obligatorios
        df_migracion = df_migracion.dropna(subset=['Codigo_Producto', 'Codigo_Lote'])
        
        # 3. Conversión de fecha (con índice limpio y sin columnas duplicadas)
        try:
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])
            
            st.success(f"✅ ¡Estructura lista! {len(df_migracion)} filas validadas.")
            st.dataframe(df_migracion.head(10))

            if st.button("🚀 Iniciar Subida"):
                data_dict = df_migracion.to_dict(orient='records')
                progress = st.progress(0)
                
                for i in range(0, len(data_dict), 100):
                    batch = data_dict[i:i+100]
                    supabase.table('Ingresos').insert(batch).execute()
                    progress.progress(min((i + 100) / len(data_dict), 1.0))
                
                st.balloons()
                st.success("Migración completada exitosamente.")
        except Exception as e:
            st.error(f"Error al procesar fechas: {e}")
            st.info("Esto sucede si hay datos corruptos en la columna de fecha.")