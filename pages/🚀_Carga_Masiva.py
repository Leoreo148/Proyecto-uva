import streamlit as st
import pandas as pd
from supabase import create_client
import re

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración Maestra de Datos (Build 9.1)")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def limpiar_nombres_columnas(columnas):
    """Limpia espacios, saltos de línea y añade sufijos a duplicados."""
    nueva_lista = []
    conteos = {}
    for col in columnas:
        c = str(col).strip().upper().replace('\n', ' ')
        if c in conteos:
            conteos[c] += 1
            nueva_lista.append(f"{c}_{conteos[c]}")
        else:
            conteos[c] = 0
            nueva_lista.append(c)
    return nueva_lista

def detectar_cabecera_real(file):
    """Escanea el Excel buscando la fila donde empiezan los datos."""
    df = pd.read_excel(file, header=None)
    for i in range(len(df)):
        fila = df.iloc[i].astype(str).str.upper().tolist()
        # Buscamos palabras que SÍ están en tus archivos (CODIGO, PRODUCTOS, COD ING)
        if any(k in s for k in ["CODIGO", "PRODUCTOS", "COD. PROD", "COD ING"] for s in fila):
            new_df = df.iloc[i+1:].copy()
            new_df.columns = limpiar_nombres_columnas(df.iloc[i].values)
            return new_df.reset_index(drop=True)
    return df

# --- INTERFAZ ---
st.info("💡 **Orden de carga:** 1° Catálogo de Productos ➔ 2° Historial de Ingresos.")
tipo_carga = st.radio("Selecciona qué vas a subir:", 
                      ["Catálogo de Productos (Maestro)", "Historial de Ingresos (Compras)"])

uploaded_file = st.file_uploader(f"Sube el Excel de {tipo_carga}", type=['xlsx'])

if uploaded_file:
    with st.spinner("Leyendo archivo..."):
        df_raw = detectar_cabecera_real(uploaded_file)
    
    st.write("📋 Columnas encontradas en tu Excel:", [c for c in df_raw.columns if "UNNAMED" not in c and "NAN" not in c])

    if tipo_carga == "Catálogo de Productos (Maestro)":
        # Mapeo exacto para tu hoja 'Cod_Producto'
        mapping = {
            'CODIGO': 'Codigo',
            'PRODUCTOS': 'Producto', # Tu Excel usa plural
            'PRODUCTO': 'Producto',
            'UM': 'Unidad',
            'SUBGRUPO': 'Tipo_Accion',
            'ING. ACTIVO': 'Ingrediente_Activo'
        }
        target_table = "Productos"
        keys_obligatorias = ['Codigo', 'Producto']
    else:
        # Mapeo exacto para tu hoja 'Ingreso'
        mapping = {
            'COD. PROD.': 'Codigo_Producto',
            'COD. PROD': 'Codigo_Producto',
            'COD ING': 'Codigo_Lote',
            'LOTE': 'Codigo_Lote',
            'CANT.ING.': 'Cantidad_Ingresada',
            'PREC. UNI S/.': 'Precio_Unitario_PEN',
            'F.DE ING.': 'Fecha_Recepcion',
            'PROVEEDOR': 'Proveedor',
            'FACTURA': 'Factura'
        }
        target_table = "Ingresos"
        keys_obligatorias = ['Codigo_Producto', 'Codigo_Lote']

    # Aplicar Mapeo
    df_ready = df_raw.rename(columns=mapping)
    df_ready = df_ready.loc[:, ~df_ready.columns.duplicated()]
    
    # Filtrar solo columnas válidas para Supabase
    columnas_finales = [v for v in mapping.values() if v in df_ready.columns]
    
    # VALIDACIÓN FINAL
    columnas_presentes = df_ready.columns.tolist()
    faltantes = [k for k in keys_obligatorias if k not in columnas_presentes]

    if faltantes:
        st.error(f"❌ Error: No encontré las columnas necesarias: {faltantes}")
        st.write("Asegúrate de que en tu Excel los títulos estén escritos exactamente como: CODIGO, PRODUCTOS, etc.")
    else:
        df_migracion = df_ready[columnas_finales].dropna(subset=keys_obligatorias).copy()
        
        # Limpieza de fechas para Ingresos
        if 'Fecha_Recepcion' in df_migracion.columns:
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])

        st.success(f"✅ ¡Todo listo! {len(df_migracion)} registros preparados para la tabla '{target_table}'.")
        st.dataframe(df_migracion.head(10))

        if st.button(f"🚀 Iniciar Subida a {target_table}"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            for i in range(0, len(data_dict), 100):
                batch = data_dict[i:i+100]
                supabase.table(target_table).insert(batch).execute()
                progress.progress(min((i + 100) / len(data_dict), 1.0))
            st.balloons()
            st.success(f"¡{target_table} actualizado! Ya puedes ir al Inventario.")