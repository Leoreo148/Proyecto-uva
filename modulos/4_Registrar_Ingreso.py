import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ValidationError, field_validator
from supabase import create_client

# 🚨 CANDADO VIP: EXCLUSIVO PARA ALMACÉN
if "autenticado" not in st.session_state or not st.session_state["autenticado"]:
    st.warning("⚠️ Por favor, inicie sesión en la página principal.")
    st.stop()

if st.session_state["rol"] not in ["Admin", "Logistica", "Programador"]:
    st.error("🚫 Acceso denegado. Este módulo es exclusivo para el área de Almacén y Mezclas (Miguel).")
    st.stop()

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Ingresos Pro", page_icon="📥", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f4f7f6; }
    div[data-testid="stForm"] {
        background-color: #ffffff;
        border-radius: 15px;
        padding: 20px;
        border: 1px solid #e0e0e0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    .total-card {
        background: linear-gradient(135deg, #1e3d33, #2d6a4f);
        border-radius: 12px;
        padding: 16px 24px;
        color: white;
        text-align: center;
        margin-top: 8px;
    }
    .total-card h3 { margin: 0; font-size: 14px; opacity: 0.85; font-weight: 400; }
    .total-card h1 { margin: 4px 0 0 0; font-size: 32px; font-weight: 700; }
    .estado-badge-verde { background: #d4edda; color: #155724; padding: 3px 10px; border-radius: 20px; font-size: 13px; font-weight: 600; }
    .estado-badge-rojo  { background: #f8d7da; color: #721c24; padding: 3px 10px; border-radius: 20px; font-size: 13px; font-weight: 600; }
    .estado-badge-gris  { background: #e2e3e5; color: #383d41; padding: 3px 10px; border-radius: 20px; font-size: 13px; font-weight: 600; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ESQUEMA DE DATOS AUDITADO ---
class IngresoSchema(BaseModel):
    Codigo_Producto: str
    Codigo_Lote: str
    Fecha_Recepcion: date
    Fecha_Vencimiento: Optional[date] = None
    Cantidad_Ingresada: float
    Precio_Unitario_PEN: float = 0.0
    Proveedor: Optional[str] = None
    Factura: Optional[str] = None
    Guia_Remision: Optional[str] = None
    Observaciones: Optional[str] = None
    Responsable: Optional[str] = None
    Estado_Registro: Optional[str] = "Completo 🟢"
    Motivo_Anulacion: Optional[str] = None

    @field_validator('Cantidad_Ingresada', 'Precio_Unitario_PEN')
    def must_be_positive(cls, v):
        if v < 0: raise ValueError('Debe ser un valor positivo')
        return v

# --- 3. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 4. FUNCIONES DE CARGA (con caché específico) ---
@st.cache_data(ttl=60)
def get_products():
    res = supabase.table('Productos').select("Codigo, Producto").execute()
    df = pd.DataFrame(res.data)
    return df if not df.empty else pd.DataFrame(columns=['Codigo', 'Producto'])

@st.cache_data(ttl=30)
def get_history():
    try:
        res_i = supabase.table('Ingresos').select("*").order('created_at', desc=True).limit(100).execute()
        res_p = supabase.table('Productos').select("Codigo, Producto").execute()
        df_i, df_p = pd.DataFrame(res_i.data), pd.DataFrame(res_p.data)
        if df_i.empty: return pd.DataFrame()
        if df_p.empty:
            df_i['Producto'] = "N/A"
            return df_i
        return pd.merge(df_i, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    except:
        return pd.DataFrame()

# --- 5. INTERFAZ PRINCIPAL ---
st.markdown("""
<div style="background: linear-gradient(135deg, #1e3d33, #2d6a4f); color:white; padding:1.5rem; border-radius:1rem; margin-bottom:2rem;">
    <h2 style="margin:0">📥 Registro Maestro de Ingresos</h2>
    <p style="margin:4px 0 0 0; opacity:0.8;">Auditoría de almacén, control de compras y recepciones provisionales.</p>
</div>
""", unsafe_allow_html=True)

df_p = get_products()

# --- DIÁLOGO PARA CREAR PRODUCTO NUEVO ---
@st.dialog("📦 Registrar Nuevo Producto en el Catálogo")
def modal_crear_producto():
    st.write("Crea el 'molde' del producto antes de ingresarlo al almacén.")
    with st.form("form_crear_maestro"):
        st.markdown("**1. Datos Generales**")
        c_mod1, c_mod2, c_mod3 = st.columns([1.5, 2, 1.5])
        n_cod = c_mod1.text_input("Código (Ej: A260)*", help="Debe ser único")
        n_nom = c_mod2.text_input("Nombre Comercial*")
        n_marca = c_mod3.text_input("Marca / Laboratorio")
        n_ingrediente = st.text_input("Ingrediente(s) Activo(s)", placeholder="Ej: cymoxanil, mancozeb")

        st.markdown("**2. Clasificación Técnica**")
        c_mod4, c_mod5, c_mod6 = st.columns(3)
        CATEGORIAS = ["Insecticida", "Acaricida", "Fungicida", "Bactericida", "Herbicida", "Defoliante",
                      "Coadyuvante", "Regulador de pH", "Nematicida", "Foliar", "Fertilizante", "Otro"]
        n_tipo = c_mod4.multiselect("Categoría", CATEGORIAS, placeholder="Ej: Insecticida")
        FORMULACIONES = ["pH — Reguladores de pH", "WSB — Bolsas hidrosolubles", "SG  — Gránulos solubles",
                         "WG  — Gránulos dispersables", "WP  — Polvos mojables", "SC  — Suspensiones concentradas",
                         "CS  — Suspensiones encapsuladas", "SE  — Suspoemulsiones", "OD  — Suspensiones concentradas oleosas",
                         "EW  — Emulsiones acuosas", "EC  — Emulsiones concentradas", "SL  — Líquidos solubles",
                         "Surfactante / Mojante", "Abono foliar", "Antideriva"]
        n_form = c_mod5.selectbox("Formulación", FORMULACIONES)
        n_uni = c_mod6.selectbox("Unidad Base", ["L", "Kg", "Gal", "Saco"])

        st.markdown("**3. Seguridad y Documentación**")
        c_mod7, c_mod8 = st.columns(2)
        n_banda = c_mod7.selectbox("Banda Toxicológica", ["Verde (Ligeramente Tóxico)", "Azul (Moderadamente Tóxico)",
                                                           "Amarillo (Altamente Tóxico)", "Rojo (Extremadamente Tóxico)", "No Aplica"])
        n_ficha = c_mod8.text_input("URL Ficha Técnica", placeholder="https://link-al-pdf.com...")

        if st.form_submit_button("Guardar en Catálogo Maestro", use_container_width=True):
            if n_cod and n_nom:
                try:
                    ingredientes_limpios = ", ".join([i.strip().capitalize() for i in n_ingrediente.split(",") if i.strip()]) if n_ingrediente else None
                    nuevo_prod = {
                        "Codigo": n_cod.strip().upper(), "Producto": n_nom.strip().upper(),
                        "Unidad": n_uni, "Tipo_Accion": ", ".join(n_tipo) if n_tipo else "Otro",
                        "Marca": n_marca.strip().upper() if n_marca else None,
                        "Ingrediente_Activo": ingredientes_limpios, "Formulacion": n_form,
                        "Banda_Toxicologica": n_banda, "Ficha_Tecnica_URL": n_ficha.strip() if n_ficha else None
                    }
                    supabase.table('Productos').insert(nuevo_prod).execute()
                    st.success(f"¡{n_nom} agregado al catálogo con éxito!")
                    # ✅ MEJORA 4: Limpieza de caché específica, no global
                    get_products.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error (¿Código duplicado?): {e}")
            else:
                st.warning("⚠️ Código y Nombre son obligatorios.")

# --- 6. FORMULARIO DE REGISTRO ---
with st.form("form_registro", clear_on_submit=True):
    st.markdown("##### 📝 Información del Producto")
    c1, c2, c3, c_total = st.columns([2, 1.5, 1.5, 1.2])

    with c1:
        # ✅ MEJORA 1: Buscador vectorizado (rápido para miles de productos)
        if not df_p.empty:
            df_p_clean = df_p[df_p['Producto'].notna() & (df_p['Producto'].astype(str) != 'nan')]
            opciones_label = (df_p_clean['Producto'].str.strip() + " (" + df_p_clean['Codigo'].str.strip() + ")").tolist()
            dict_productos = dict(zip(opciones_label, df_p_clean['Codigo'].tolist()))
        else:
            dict_productos = {}

        seleccion = st.selectbox("Seleccionar Producto", options=list(dict_productos.keys()),
                                 index=None, placeholder="🔍 Escribe para buscar...")
        cod_prod = dict_productos[seleccion] if seleccion else None
        lote = st.text_input("Código de Lote / Batch")

    with c2:
        cant = st.number_input("Cantidad Ingresada", min_value=0.0, step=0.01, key="cant_input")
        p_pen = st.number_input("Precio Unitario (S/)", min_value=0.0, step=0.01, key="precio_input")

    with c3:
        fecha_rec = st.date_input("Fecha de Recepción", value=date.today())
        fecha_venc = st.date_input("Fecha de Vencimiento", value=date.today().replace(year=date.today().year + 2))

    with c_total:
        # ✅ MEJORA 3: Cálculo automático en tiempo real del costo total
        total_calculado = cant * p_pen
        st.markdown(f"""
        <div class="total-card">
            <h3>💰 Total Factura</h3>
            <h1>S/ {total_calculado:,.2f}</h1>
        </div>
        """, unsafe_allow_html=True)

    st.divider()
    st.markdown("##### 🚛 Datos Logísticos y Auditoría")
    c4, c5, c6, c7 = st.columns(4)

    with c4: prov = st.text_input("Proveedor")
    with c5: fact = st.text_input("N° de Factura", help="Sin factura = ingreso Provisional")
    with c6: guia = st.text_input("Guía de Remisión")
    with c7: resp = st.text_input("Responsable (Recepción)*", placeholder="Tu nombre")

    obs = st.text_area("Observaciones Adicionales", placeholder="Ej: Sacos con humedad, entrega parcial, etc.")

    if st.form_submit_button("💾 Confirmar Ingreso a Almacén", use_container_width=True):
        if cod_prod and lote and cant > 0:
            if not resp:
                st.warning("⚠️ Por favor, indica quién es el responsable de la recepción.")
            else:
                try:
                    estado_actual = "Provisional 🔴" if not fact else "Completo 🟢"
                    nuevo = IngresoSchema(
                        Codigo_Producto=cod_prod, Codigo_Lote=lote, Fecha_Recepcion=fecha_rec,
                        Fecha_Vencimiento=fecha_venc, Cantidad_Ingresada=cant, Precio_Unitario_PEN=p_pen,
                        Proveedor=prov, Factura=fact, Guia_Remision=guia, Observaciones=obs,
                        Responsable=resp, Estado_Registro=estado_actual
                    )
                    supabase.table('Ingresos').insert(nuevo.model_dump(mode='json')).execute()
                    st.success(f"✅ Ingreso registrado como **{estado_actual}** | Total: **S/ {total_calculado:,.2f}**")
                    # ✅ MEJORA 4: Solo limpiamos el caché del historial, no de todo el sistema
                    get_history.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
        else:
            st.error("⚠️ Producto, Lote y Cantidad son campos obligatorios.")

st.write("")
col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
if col_btn2.button("💡 ¿El producto no existe? Crea uno nuevo aquí", use_container_width=True):
    modal_crear_producto()

# --- 7. HISTORIAL Y AUDITORÍA DE MOVIMIENTOS ---
st.divider()
st.subheader("📋 Historial de Movimientos y Auditoría")
df_hist = get_history()

if not df_hist.empty:
    cols_visibles = ['Estado_Registro', 'Fecha_Recepcion', 'Proveedor', 'Producto',
                     'Codigo_Lote', 'Cantidad_Ingresada', 'Precio_Unitario_PEN',
                     'Factura', 'Responsable', 'Motivo_Anulacion']
    cols_reales = [c for c in cols_visibles if c in df_hist.columns]
    df_mostrar = df_hist[cols_reales].copy()

    # ✅ MEJORA 2: Tabla nativa de Streamlit, moderna y ligera
    seleccion_tabla = st.dataframe(
        df_mostrar,
        use_container_width=True,
        hide_index=True,
        height=350,
        on_select="rerun",
        selection_mode="single-row",
        column_config={
            "Estado_Registro":    st.column_config.TextColumn("Estado", width="medium"),
            "Fecha_Recepcion":    st.column_config.DateColumn("Fecha", format="DD/MM/YYYY"),
            "Cantidad_Ingresada": st.column_config.NumberColumn("Cantidad", format="%.2f"),
            "Precio_Unitario_PEN":st.column_config.NumberColumn("Precio (S/)", format="S/ %.2f"),
            "Motivo_Anulacion":   st.column_config.TextColumn("Motivo Anulación", width="large"),
        }
    )

    # --- 8. ACCIONES POST-RECEPCIÓN ---
    filas_sel = seleccion_tabla.selection.rows
    if filas_sel:
        idx = filas_sel[0]
        sel_row = df_hist.iloc[idx]

        st.write("---")
        st.markdown(f"**Gestión del Lote seleccionado:** `{sel_row.get('Codigo_Lote', '')}` — {sel_row.get('Producto', '')}")

        c_acc1, c_acc2 = st.columns(2)

        # BOTÓN 1: COMPLETAR DATOS (Si es provisional)
        if sel_row.get('Estado_Registro') == 'Provisional 🔴':
            with c_acc1.expander("📝 Completar Factura / Precio"):
                with st.form(f"form_completar_{sel_row.get('id', '')}"):
                    n_fact = st.text_input("Nueva Factura")
                    n_precio = st.number_input("Precio Final (S/)", min_value=0.0, value=float(sel_row.get('Precio_Unitario_PEN', 0)))
                    if st.form_submit_button("Actualizar y Cerrar Registro"):
                        real_id = df_hist[df_hist['Codigo_Lote'] == sel_row['Codigo_Lote']].iloc[0]['id']
                        supabase.table('Ingresos').update({
                            "Factura": n_fact, "Precio_Unitario_PEN": n_precio, "Estado_Registro": "Completo 🟢"
                        }).eq('id', int(real_id)).execute()
                        st.success("✅ Registro actualizado.")
                        get_history.clear()
                        st.rerun()

        # BOTÓN 2: ANULAR INGRESO (Cero borrados, por trazabilidad)
        if sel_row.get('Estado_Registro') != 'ANULADO ❌':
            with c_acc2.expander("⚠️ Anular Movimiento"):
                with st.form(f"form_anular_{sel_row.get('id', '')}"):
                    st.warning("Esto pondrá el stock de este ingreso en cero (trazabilidad).")
                    motivo = st.text_input("Motivo de la anulación (Obligatorio)*")
                    if st.form_submit_button("Confirmar Anulación"):
                        if motivo:
                            real_id = df_hist[df_hist['Codigo_Lote'] == sel_row['Codigo_Lote']].iloc[0]['id']
                            supabase.table('Ingresos').update({
                                "Cantidad_Ingresada": 0, "Estado_Registro": "ANULADO ❌", "Motivo_Anulacion": motivo
                            }).eq('id', int(real_id)).execute()
                            st.success("Movimiento anulado por trazabilidad.")
                            get_history.clear()
                            st.rerun()
                        else:
                            st.error("Debes escribir un motivo para la auditoría.")
else:
    st.info("No se encontraron registros de ingresos previos.")