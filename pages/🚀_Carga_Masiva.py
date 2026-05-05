import streamlit as st
import pandas as pd
import numpy as np
from supabase import create_client

st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración Maestra de Datos (Build 9.5 - Fix JSON)")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def limpiar_nombres_columnas(columnas):
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

def detectar_cabecera_real(df):
    for i in range(len(df)):
        fila_segura = [str(x).upper() for x in df.iloc[i].values]
        if any(palabra in celda for celda in fila_segura for palabra in ["CODIGO", "PRODUCTOS", "COD. PROD", "COD ING"]):
            new_df = df.iloc[i+1:].copy()
            new_df.columns = limpiar_nombres_columnas(df.iloc[i].values)
            return new_df.reset_index(drop=True)
    return df

# --- INTERFAZ ---
st.info("💡 **Orden de carga:** 1° Catálogo de Productos ➔ 2° Historial de Ingresos.")
tipo_carga = st.radio("Selecciona qué vas a subir a la base de datos:", 
                      ["Catálogo de Productos (Maestro)", "Historial de Ingresos (Compras)"])

uploaded_file = st.file_uploader("Sube tu archivo Excel COMPLETO", type=['xlsx'])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    nombres_hojas = xls.sheet_names
    
    st.markdown("### 📂 Selecciona la pestaña correcta del Excel:")
    hoja_seleccionada = st.selectbox("Elige la hoja que contiene los datos que indicaste arriba:", nombres_hojas)
    
    st.divider()

    with st.spinner(f"Analizando la hoja '{hoja_seleccionada}'..."):
        df_base = pd.read_excel(xls, sheet_name=hoja_seleccionada, header=None)
        df_raw = detectar_cabecera_real(df_base)
    
    st.write("📋 Columnas encontradas en esta pestaña:", [c for c in df_raw.columns if "UNNAMED" not in c and "NAN" not in c])

    if tipo_carga == "Catálogo de Productos (Maestro)":
        mapping = {
            'CODIGO': 'Codigo',
            'PRODUCTOS': 'Producto',
            'PRODUCTO': 'Producto',
            'UM': 'Unidad',
            'SUBGRUPO': 'Tipo_Accion',
            'ING. ACTIVO': 'Ingrediente_Activo'
        }
        target_table = "Productos"
        keys_obligatorias = ['Codigo', 'Producto']
    else:
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

    df_ready = df_raw.rename(columns=mapping)
    df_ready = df_ready.loc[:, ~df_ready.columns.duplicated()]
    
    columnas_finales = []
    for v in mapping.values():
        if v in df_ready.columns and v not in columnas_finales:
            columnas_finales.append(v)
    
    columnas_presentes = df_ready.columns.tolist()
    faltantes = [k for k in keys_obligatorias if k not in columnas_presentes]

    if faltantes:
        st.error(f"❌ Error: No encontré las columnas necesarias: {faltantes}")
        st.write(f"Asegúrate de haber seleccionado la hoja correcta.")
    else:
        df_migracion = df_ready[columnas_finales].dropna(subset=keys_obligatorias).copy()
        
        if 'Fecha_Recepcion' in df_migracion.columns:
            df_migracion['Fecha_Recepcion'] = pd.to_datetime(df_migracion['Fecha_Recepcion'], errors='coerce').dt.strftime('%Y-%m-%d')
            df_migracion = df_migracion.dropna(subset=['Fecha_Recepcion'])

        # --- FIX: ESCUDO ANTI-NaN PARA JSON ---
        # Convertimos todo a tipo objeto para que Pandas acepte 'None' en lugar de forzar 'NaN'
        df_migracion = df_migracion.astype(object)
        # Reemplazamos los vacíos matemáticos por un nulo que Supabase entienda
        df_migracion = df_migracion.where(pd.notnull(df_migracion), None)

        st.success(f"✅ ¡Todo listo! {len(df_migracion)} registros preparados para la tabla '{target_table}'.")
        st.dataframe(df_migracion.head(10))

        if st.button(f"🚀 Iniciar Subida a {target_table}"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            
            try:
                for i in range(0, len(data_dict), 100):
                    batch = data_dict[i:i+100]
                    supabase.table(target_table).insert(batch).execute()
                    progress.progress(min((i + 100) / len(data_dict), 1.0))
                st.balloons()
                st.success(f"¡{target_table} actualizado correctamente!")
            except Exception as e:
                st.error(f"Error al subir los datos: {e}")