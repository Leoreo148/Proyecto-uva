import streamlit as st
import pandas as pd
import math
from supabase import create_client
from datetime import datetime

# 🚨 CANDADO DE SEGURIDAD
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Carga Masiva Pro", page_icon="🚀", layout="wide")
st.title("🚀 Migración Maestra de Datos")
st.caption("Flujo recomendado: Primero sube el **Catálogo de Productos**, luego los **Ingresos**.")

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────
def limpiar_nombres_columnas(columnas):
    nueva_lista, conteos = [], {}
    for col in columnas:
        c = str(col).strip().upper().replace('\n', ' ')
        if c in conteos:
            conteos[c] += 1
            nueva_lista.append(f"{c}_{conteos[c]}")
        else:
            conteos[c] = 0
            nueva_lista.append(c)
    return nueva_lista

def detectar_cabecera_real(df, palabras_clave):
    """Busca la fila de encabezados reales recorriendo las primeras 15 filas."""
    for i in range(min(15, len(df))):
        fila_str = [str(x).upper().strip() for x in df.iloc[i].values]
        if any(palabra in celda for celda in fila_str for palabra in palabras_clave):
            new_df = df.iloc[i + 1:].copy()
            new_df.columns = limpiar_nombres_columnas(df.iloc[i].values)
            return new_df.reset_index(drop=True)
    return df

# ─────────────────────────────────────────────
# INTERFAZ PRINCIPAL
# ─────────────────────────────────────────────
tipo_carga = st.radio(
    "¿Qué quieres importar?",
    ["📦 Catálogo de Productos (Maestro)", "📥 Historial de Ingresos (Compras)"],
    horizontal=True
)

uploaded_file = st.file_uploader("Sube tu archivo Excel (.xlsx)", type=["xlsx"])

if not uploaded_file:
    st.stop()

xls = pd.ExcelFile(uploaded_file)
hoja_sel = st.selectbox("Selecciona la hoja del Excel con los datos:", xls.sheet_names)
st.divider()

# ─────────────────────────────────────────────
# CONFIGURACIÓN POR TIPO DE CARGA
# ─────────────────────────────────────────────
if tipo_carga == "📦 Catálogo de Productos (Maestro)":
    PALABRAS_CLAVE   = ["CODIGO", "PRODUCTOS", "UM", "SUBGRUPO"]
    MAPPING          = {
        "CODIGO":       "Codigo",
        "PRODUCTOS":    "Producto",
        "UM":           "Unidad",
        "GRUPO":        "Grupo",
        "SUBGRUPO":     "Tipo_Accion",
        "ING. ACTIVO":  "Ingrediente_Activo",
    }
    TARGET_TABLE     = "Productos"
    KEYS_OBL         = ["Codigo", "Producto"]
    FECHAS           = []
    UPSERT_CONFLICT  = "Codigo"   # si ya existe ese código, lo actualiza

else:  # Ingresos
    PALABRAS_CLAVE   = ["COD. PROD.", "COD ING", "F.DE ING.", "CANT.ING."]
    MAPPING          = {
        "COD. PROD.":       "Codigo_Producto",
        "COD ING":          "Codigo_Lote",
        "F.DE ING.":        "Fecha_Recepcion",
        "CANT.ING.":        "Cantidad_Ingresada",
        "PREC. UNI S/.":    "Precio_Unitario_PEN",
        "PREC. UNI $.":     "Precio_Unitario_USD",
        "F DE VENC":        "Fecha_Vencimiento",     # opcional: puede estar vacío
        "PROVEEDOR":        "Proveedor",
        "FACTURA":          "Factura",
        "GUIA REMISIÓN":    "Guia_Remision",
        "DEPOSITO  (BCP_COD)": "Deposito",
        "OBSERVACIONES":    "Observaciones",
    }
    TARGET_TABLE     = "Ingresos"
    KEYS_OBL         = ["Codigo_Producto", "Codigo_Lote", "Cantidad_Ingresada"]
    FECHAS           = ["Fecha_Recepcion"]   # Vencimiento es OPCIONAL, no se exige
    FECHAS_OPT       = ["Fecha_Vencimiento"] # Opcional: si está vacía, se deja None
    UPSERT_CONFLICT  = None                  # Ingresos: insert normal (sin upsert)

# ─────────────────────────────────────────────
# PROCESAMIENTO DEL EXCEL
# ─────────────────────────────────────────────
with st.spinner(f"Analizando hoja '{hoja_sel}'..."):
    df_base = pd.read_excel(xls, sheet_name=hoja_sel, header=None)
    df_raw  = detectar_cabecera_real(df_base, PALABRAS_CLAVE)

if df_raw.empty:
    st.error("❌ No se pudo detectar la cabecera de la hoja. Verifica que elegiste la hoja correcta.")
    st.stop()

# Renombrar solo las columnas que están en el mapping
df_ready = df_raw.rename(columns=MAPPING)

# Columnas que existen en el resultado
cols_validas = [c for c in MAPPING.values() if c in df_ready.columns]

# Verificar columnas obligatorias
faltantes = [k for k in KEYS_OBL if k not in df_ready.columns]
if faltantes:
    st.error(f"❌ La hoja no tiene las columnas obligatorias: {faltantes}")
    st.write("**Columnas detectadas:**", df_ready.columns.tolist())
    st.stop()

df_mig = df_ready[cols_validas].copy()

# Eliminar filas donde las claves obligatorias estén vacías
df_mig = df_mig.dropna(subset=KEYS_OBL)

# Limpieza de códigos (siempre en mayúscula)
for col in ["Codigo", "Codigo_Producto", "Codigo_Lote"]:
    if col in df_mig.columns:
        df_mig[col] = df_mig[col].astype(str).str.strip().str.upper()

# Limpieza de texto general
for col in df_mig.select_dtypes(include="object").columns:
    df_mig[col] = df_mig[col].astype(str).str.strip()
    df_mig[col] = df_mig[col].replace({"nan": None, "NaT": None, "": None})

# ── Fechas OBLIGATORIAS (se eliminan si no se pueden parsear)
for col in FECHAS:
    if col in df_mig.columns:
        df_mig[col] = pd.to_datetime(df_mig[col], errors="coerce").dt.strftime("%Y-%m-%d")
        antes = len(df_mig)
        df_mig = df_mig.dropna(subset=[col])
        eliminados = antes - len(df_mig)
        if eliminados:
            st.warning(f"⚠️ Se eliminaron {eliminados} filas porque '{col}' no tenía fecha válida.")

# ── Fechas OPCIONALES (se dejan None si están vacías, no se elimina la fila)
for col in (FECHAS_OPT if "FECHAS_OPT" in dir() else []):
    if col in df_mig.columns:
        df_mig[col] = pd.to_datetime(df_mig[col], errors="coerce").dt.strftime("%Y-%m-%d")
        # NaT → None (no eliminamos la fila)
        df_mig[col] = df_mig[col].where(df_mig[col].notna(), None)

# ✅ Escudo Anti-NaN ultra robusto: convierte CUALQUIER nan/NaN/None a None de Python
# Esto cubre floats, strings 'nan', 'NaT', etc.
def limpiar_nan(valor):
    if valor is None:
        return None
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if isinstance(valor, str) and valor.strip().lower() in ('nan', 'nat', 'none', ''):
        return None
    return valor

def limpiar_registro(record: dict) -> dict:
    return {k: limpiar_nan(v) for k, v in record.items()}

df_mig = df_mig.astype(object).where(pd.notnull(df_mig), None)

# ✅ Deduplicar por la clave de upsert ANTES de enviar
# Si el Excel tiene el mismo código dos veces (celdas fusionadas, duplicados),
# PostgreSQL falla con "ON CONFLICT DO UPDATE command cannot affect row a second time".
# Nos quedamos con la última aparición de cada código (la más completa).
if UPSERT_CONFLICT and UPSERT_CONFLICT in df_mig.columns:
    antes_dedup = len(df_mig)
    df_mig = df_mig.drop_duplicates(subset=[UPSERT_CONFLICT], keep="last").reset_index(drop=True)
    eliminados_dup = antes_dedup - len(df_mig)
    if eliminados_dup > 0:
        st.warning(f"⚠️ Se encontraron y eliminaron **{eliminados_dup} filas duplicadas** (mismo código). Se conservó la última aparición de cada una.")

# Ingrediente activo: capitalizar bonito si existe
if "Ingrediente_Activo" in df_mig.columns:
    df_mig["Ingrediente_Activo"] = df_mig["Ingrediente_Activo"].apply(
        lambda x: ", ".join([i.strip().capitalize() for i in str(x).split(",") if i.strip()]) if x else None
    )

# ─────────────────────────────────────────────
# PREVISUALIZACIÓN
# ─────────────────────────────────────────────
total_detectados = len(df_mig)
st.success(f"✅ {total_detectados} registros listos para importar.")

col_prev, col_info = st.columns([3, 1])
with col_prev:
    st.dataframe(df_mig.head(15), use_container_width=True, hide_index=True)
with col_info:
    st.markdown("### 📋 Resumen")
    st.metric("Registros a importar", total_detectados)
    st.metric("Columnas mapeadas", len(cols_validas))
    if UPSERT_CONFLICT:
        st.info(f"🔄 **Modo:** Upsert\n\nSi ya existe un registro con el mismo `{UPSERT_CONFLICT}`, lo **actualiza**. Si no existe, lo **crea**.")
    else:
        st.info("➕ **Modo:** Inserción\n\nCada fila del Excel se insertará como un nuevo registro.")

# ─────────────────────────────────────────────
# BOTÓN DE CARGA
# ─────────────────────────────────────────────
st.divider()
if st.button(f"🚀 Iniciar Importación a '{TARGET_TABLE}'", type="primary", use_container_width=True):
    data_dict    = [limpiar_registro(r) for r in df_mig.to_dict(orient="records")]
    progress     = st.progress(0)
    status_text  = st.empty()
    insertados   = 0
    errores      = []
    BATCH_SIZE   = 100

    for i in range(0, len(data_dict), BATCH_SIZE):
        batch = data_dict[i:i + BATCH_SIZE]
        try:
            if UPSERT_CONFLICT:
                supabase.table(TARGET_TABLE).upsert(batch, on_conflict=UPSERT_CONFLICT).execute()
            else:
                supabase.table(TARGET_TABLE).insert(batch).execute()
            insertados += len(batch)
        except Exception as e:
            errores.append(f"Lote {i//BATCH_SIZE + 1}: {str(e)[:120]}")

        avance = min((i + BATCH_SIZE) / len(data_dict), 1.0)
        progress.progress(avance)
        status_text.text(f"Subiendo... {int(avance * 100)}%  ({min(i + BATCH_SIZE, len(data_dict))}/{len(data_dict)} registros)")

    progress.progress(1.0)

    # ── Reporte final
    st.divider()
    col_r1, col_r2 = st.columns(2)
    col_r1.metric("✅ Registros importados", insertados)
    col_r2.metric("❌ Lotes con error", len(errores))

    if errores:
        with st.expander("Ver errores detallados"):
            for err in errores:
                st.error(err)
        st.warning("Algunos lotes no se pudieron subir. Revisa los errores arriba y avisa al administrador del sistema.")
    else:
        st.balloons()
        st.success(f"🎉 ¡Importación completada! {insertados} registros cargados en '{TARGET_TABLE}'.")