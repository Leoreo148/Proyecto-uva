import streamlit as st
import pandas as pd
from supabase import create_client
from datetime import datetime

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración Maestra de Datos (Build 9.8 - Auditoría Total)")

# --- CONEXIÓN ---
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
    # Buscamos la fila donde empiezan los datos reales
    palabras_clave = ["CODIGO", "PRODUCTOS", "COD. PROD", "COD ING", "COD.P", "FECHA"]
    for i in range(len(df)):
        fila_segura = [str(x).upper() for x in df.iloc[i].values]
        if any(palabra in celda for celda in fila_segura for palabra in palabras_clave):
            new_df = df.iloc[i+1:].copy()
            new_df.columns = limpiar_nombres_columnas(df.iloc[i].values)
            return new_df.reset_index(drop=True)
    return df

# --- INTERFAZ ---
st.info("💡 **Flujo recomendado:** Primero sube el Catálogo, luego los Ingresos y finalmente las Salidas.")
tipo_carga = st.radio("Selecciona qué pestaña del Excel vas a procesar:", 
                      ["Catálogo de Productos (Maestro)", 
                       "Historial de Ingresos (Compras/Stock Inicial)", 
                       "Historial de Salidas (Consumos/Campo)"])

uploaded_file = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=['xlsx'])

if uploaded_file:
    xls = pd.ExcelFile(uploaded_file)
    nombres_hojas = xls.sheet_names
    hoja_seleccionada = st.selectbox("Selecciona la hoja donde están los datos:", nombres_hojas)
    
    st.divider()

    with st.spinner(f"Analizando '{hoja_seleccionada}'..."):
        df_base = pd.read_excel(xls, sheet_name=hoja_seleccionada, header=None)
        df_raw = detectar_cabecera_real(df_base)

    # --- LÓGICA DE MAPEO AUDITADA ---
    if tipo_carga == "Catálogo de Productos (Maestro)":
        mapping = {
            'CODIGO': 'Codigo',
            'PRODUCTOS': 'Producto',
            'UM': 'Unidad',
            'SUBGRUPO': 'Tipo_Accion',
            'ING. ACTIVO': 'Ingrediente_Activo',
            'INCOMPATIBLE CON': 'Incompatible_Con'
        }
        target_table = "Productos"
        keys_obligatorias = ['Codigo', 'Producto']

    elif tipo_carga == "Historial de Ingresos (Compras/Stock Inicial)":
        mapping = {
            'COD. PROD.': 'Codigo_Producto',
            'COD ING': 'Codigo_Lote',
            'CANT.ING.': 'Cantidad_Ingresada',
            'PREC. UNI S/.': 'Precio_Unitario_PEN',
            'PREC. UNI $.': 'Precio_Unitario_USD', # <-- NUEVO
            'F.DE ING.': 'Fecha_Recepcion',
            'F DE VENC': 'Fecha_Vencimiento',      # <-- NUEVO
            'PROVEEDOR': 'Proveedor',
            'FACTURA': 'Factura',
            'GUIA REMISIÓN': 'Guia_Remision',      # <-- NUEVO
            'DEPOSITO  (BCP_COD)': 'Deposito',     # <-- NUEVO
            'OBSERVACIONES': 'Observaciones'       # <-- NUEVO
        }
        target_table = "Ingresos"
        keys_obligatorias = ['Codigo_Producto', 'Codigo_Lote', 'Cantidad_Ingresada']

    else: # HISTORIAL DE SALIDAS
        mapping = {
            'COD. PROD': 'Codigo_Producto', # Usamos esto temporalmente
            'COD ING': 'Ingreso_ID',        # Este es el ID de la tabla Ingresos
            'FECHA': 'Fecha_Aplicacion',
            'CANT APLIC.-1': 'Cantidad_Usada',
            'OBJETIVO DEL TRATAMIENTO': 'Objetivo_Tratamiento',
            'H2O': 'H2O',
            'ACTIVIDAD': 'Actividad',
            'LABOR': 'Labor',
            'DOCUMENTO': 'Documento'
        }
        target_table = "Salidas"
        keys_obligatorias = ['Ingreso_ID', 'Cantidad_Usada']

    # --- PROCESAMIENTO ---
    df_ready = df_raw.rename(columns=mapping)
    
    # Filtrar solo las columnas que existen en nuestro mapeo
    columnas_validas = [c for c in mapping.values() if c in df_ready.columns]
    
    if not all(k in df_ready.columns for k in keys_obligatorias):
        faltantes = [k for k in keys_obligatorias if k not in df_ready.columns]
        st.error(f"❌ Error: La hoja no tiene las columnas obligatorias: {faltantes}")
    else:
        df_migracion = df_ready[columnas_validas].dropna(subset=keys_obligatorias).copy()

        # Limpieza de Códigos
        if 'Codigo' in df_migracion.columns:
            df_migracion['Codigo'] = df_migracion['Codigo'].astype(str).str.strip().str.upper()
        if 'Codigo_Producto' in df_migracion.columns:
            df_migracion['Codigo_Producto'] = df_migracion['Codigo_Producto'].astype(str).str.strip().str.upper()

        # Formateo de Fechas (Detectamos todas las columnas de fecha posibles)
        columnas_fecha = ['Fecha_Recepcion', 'Fecha_Vencimiento', 'Fecha_Aplicacion']
        for col in columnas_fecha:
            if col in df_migracion.columns:
                df_migracion[col] = pd.to_datetime(df_migracion[col], errors='coerce').dt.strftime('%Y-%m-%d')
                df_migracion = df_migracion.dropna(subset=[col])

        # Escudo Anti-NaN para Supabase
        df_migracion = df_migracion.astype(object).where(pd.notnull(df_migracion), None)

        st.success(f"✅ ¡Previsualización Lista! {len(df_migracion)} registros detectados.")
        st.dataframe(df_migracion.head(10))

        if st.button(f"🚀 Iniciar Subida a {target_table}"):
            data_dict = df_migracion.to_dict(orient='records')
            progress = st.progress(0)
            status_text = st.empty()
            
            try:
                # Subida en lotes de 100 para no saturar la API
                for i in range(0, len(data_dict), 100):
                    batch = data_dict[i:i+100]
                    
                    if target_table == "Productos":
                        supabase.table(target_table).upsert(batch, on_conflict='Codigo').execute()
                    else:
                        supabase.table(target_table).insert(batch).execute()
                        
                    avance = min((i + 100) / len(data_dict), 1.0)
                    progress.progress(avance)
                    status_text.text(f"Subiendo a {target_table}... {int(avance * 100)}%")
                    
                st.balloons()
                st.success(f"¡Éxito! {target_table} actualizado con datos del Excel.")
            except Exception as e:
                st.error(f"Error en la subida: {e}")