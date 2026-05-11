import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Salidas y Mezclas", page_icon="⚗️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .stHeader { background-color: #1e3d33; }
    div[data-testid="stExpander"] { background-color: #ffffff; border-radius: 10px; border: 1px solid #e0e0e0; }
    .seccion-titulo { color: #1e3d33; font-weight: 600; margin-top: 15px; margin-bottom: 10px; border-bottom: 2px solid #2ecc71; padding-bottom: 5px;}
    </style>
    """, unsafe_allow_html=True)

st.title("⚗️ Centro de Mezclas y Salidas (Build 9.5 - Belessia)")
st.write("Programación integral de campo y control técnico de descargas.")

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS AUDITADA ---
@st.cache_data(ttl=60)
def cargar_datos_operativos():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    p = supabase.table('Productos').select("Codigo, Producto, Unidad").execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Fecha_Vencimiento, Precio_Unitario_PEN").execute()
    
    try:
        s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
        df_s = pd.DataFrame(s.data)
    except:
        df_s = pd.DataFrame()
        
    try:
        o = supabase.table('Ordenes_de_Trabajo').select("*").order('created_at', desc=True).execute()
        df_o = pd.DataFrame(o.data)
    except:
        df_o = pd.DataFrame()

    return pd.DataFrame(p.data), pd.DataFrame(i.data), df_s, df_o

def obtener_stock_por_lote(df_p, df_i, df_s):
    if df_i.empty: return pd.DataFrame()
    
    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_lotes = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada'] - df_lotes['Cantidad_Usada']
    else:
        df_lotes = df_i.copy()
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada']

    df_final = pd.merge(df_lotes, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    
    if 'Fecha_Vencimiento' in df_final.columns:
        df_final['Fecha_Vencimiento'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
        
    return df_final

df_prod, df_ing, df_sal, df_ord = cargar_datos_operativos()
df_fefo = obtener_stock_por_lote(df_prod, df_ing, df_sal)

OBJETIVOS_COMUNES = ["Control de Plagas", "Fertilización", "Control de Enfermedades", "Herbicida", "Riego", "Otro"]
LABORES_COMUNES = ["Motorista", "Aplicador Manual", "Riego tecnificado", "Foliar Tractor"]

# --- INTERFAZ ---
tab1, tab2 = st.tabs(["🚀 Salida Rápida (Directa)", "📋 Órdenes de Mezcla (Recetas y Maquinaria)"])

# ==========================================
# TAB 1: SALIDA DIRECTA RÁPIDA 
# ==========================================
with tab1:
    st.subheader("Descargo Directo de Almacén")
    if df_fefo.empty or not (df_fefo['Stock_Actual'] > 0).any():
        st.error("❌ No hay stock disponible.")
    else:
        df_disponible = df_fefo[df_fefo['Stock_Actual'] > 0].sort_values('Fecha_Vencimiento')
        opciones_lotes = {
            f"{r['Producto']} | Lote: {r['Codigo_Lote']} (Saldo: {r['Stock_Actual']:.2f} {r['Unidad']})": r 
            for _, r in df_disponible.iterrows()
        }

        with st.form("salida_directa"):
            c1, c2 = st.columns([2, 1])
            lote_sel = c1.selectbox("Producto y Lote:", list(opciones_lotes.keys()))
            lote_info = opciones_lotes[lote_sel]
            cant_salida = c2.number_input(f"Cantidad ({lote_info['Unidad']}):", min_value=0.01, max_value=float(lote_info['Stock_Actual']), value=1.0)
            
            st.divider()
            st.markdown("##### 📝 Datos Técnicos")
            c3, c4, c5 = st.columns(3)
            fecha = c3.date_input("Fecha", value=date.today())
            sector = c4.text_input("Sector Destino", placeholder="Ej: W3")
            objetivo = c5.selectbox("Objetivo", OBJETIVOS_COMUNES)
            
            c6, c7, c8 = st.columns(3)
            vol_h2o = c6.number_input("Volumen Agua (L)", min_value=0, value=1000)
            labor = c7.selectbox("Labor / Actividad", LABORES_COMUNES)
            doc_guia = c8.text_input("Documento / Guía", placeholder="Ej: G.R.E. T001...")

            if st.form_submit_button("⚡ Registrar Salida Directa", type="primary"):
                nueva_salida = {
                    "Fecha_Aplicacion": str(fecha),
                    "Ingreso_ID": int(lote_info['id']),
                    "Cantidad_Usada": cant_salida,
                    "Sector_Destino": sector,
                    "Objetivo_Tratamiento": objetivo
                    # "H2O": vol_h2o,
                    # "Labor": labor,
                    # "Documento": doc_guia
                }
                supabase.table('Salidas').insert(nueva_salida).execute()
                st.success("✅ Salida registrada e inventario actualizado.")
                st.cache_data.clear()
                st.rerun()

# ==========================================
# TAB 2: ÓRDENES DE MEZCLA MAESTRAS 
# ==========================================
with tab2:
    with st.expander("👨‍🔬 Programar Mezcla y Parámetros de Tractor", expanded=False):
        if not df_fefo.empty:
            with st.form("nueva_ot_pro"):
                
                # --- 1. DATOS GENERALES ---
                st.markdown('<div class="seccion-titulo">1. Datos Generales y Área</div>', unsafe_allow_html=True)
                ca1, ca2, ca3, ca4 = st.columns(4)
                f_ot = ca1.date_input("Fecha Programada")
                sec_ot = ca2.text_input("Lotes / Sector", placeholder="Ej: W3")
                ha_ot = ca3.number_input("Hectáreas", min_value=0.01, value=1.80)
                turno_ot = ca4.selectbox("Turno", ["Día", "Noche"])
                
                obj_ot = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Trips - araña roja")

                # --- 2. MAQUINARIA ---
                st.markdown('<div class="seccion-titulo">2. Asignación de Maquinaria</div>', unsafe_allow_html=True)
                cm1, cm2, cm3 = st.columns(3)
                tract_ot = cm1.text_input("Tractor Utilizado", placeholder="Ej: Antonio Carraro")
                imple_ot = cm2.text_input("Pulverizador / Tanque", value="Full Maquinarias")
                oper_ot = cm3.text_input("Operario Asignado")

                # --- 3. MÉTODO DE APLICACIÓN Y AGUA ---
                st.markdown('<div class="seccion-titulo">3. Método de Aplicación y Caldo</div>', unsafe_allow_html=True)
                cw1, cw2, cw3, cw4 = st.columns(4)
                tipo_app = cw1.selectbox("Tipo de Aplicación", ["Nebulizado (Turbo)", "Pulverizado", "Barras", "Pistolas/Drench", "Mochila Manual"])
                vol_total = cw2.number_input("Volumen Total (Lts)", value=2200)
                vol_ha = cw3.number_input("Volumen Lts/Ha", value=1200)
                ph_agua = cw4.number_input("pH Agua", value=6.0, step=0.1)

                # --- 4. CALIBRACIÓN ---
                st.markdown('<div class="seccion-titulo">4. Calibración y Boquillas</div>', unsafe_allow_html=True)
                cb1, cb2, cb3 = st.columns(3)
                marcha = cb1.number_input("Marcha Tractor (N°)", min_value=1, value=1)
                velocidad = cb2.number_input("Velocidad Km/h", value=0.0)
                presion = cb3.number_input("Presión (Bar/Lb)", value=9.0)

                ct1, ct2 = st.columns([1, 2])
                n_boq = ct1.number_input("N° Total de Boquillas", value=18)
                color_boq = ct2.text_input("Color de Boquillas", value="9 negras, 9 marrones")
                
                obs_ot = st.text_input("Observaciones Generales", value="Aplicación con turbo y con boquillas intercaladas una negra y una marron")

                # --- 5. RECETA DE INSUMOS ---
                st.markdown('<div class="seccion-titulo">5. Receta de Fitosanitarios / Foliares</div>', unsafe_allow_html=True)
                editor = st.data_editor(
                    pd.DataFrame([{"Insumo": list(opciones_lotes.keys())[0], "Cantidad": 0.0}]),
                    num_rows="dynamic",
                    column_config={
                        "Insumo": st.column_config.SelectboxColumn("Seleccionar Lote de Almacén", options=list(opciones_lotes.keys()), required=True),
                        "Cantidad": st.column_config.NumberColumn("Total Producto (Kg/L)", min_value=0.0)
                    }
                )

                if st.form_submit_button("📡 Enviar Orden Maestra al Campo", type="primary"):
                    receta = []
                    for _, row in editor.iterrows():
                        info = opciones_lotes[row['Insumo']]
                        receta.append({"id": int(info['id']), "p": info['Producto'], "l": info['Codigo_Lote'], "c": row['Cantidad']})
                    
                    # Empaquetamos toda la metadata física en un formato legible para el Excel final
                    reporte_tecnico = f"""
                    [ÁREA]: {ha_ot} Ha | [TURNO]: {turno_ot}
                    [MÉTODO]: {tipo_app} | [AGUA]: Vol Total: {vol_total} L | Vol/Ha: {vol_ha} L | pH: {ph_agua}
                    [CALIBRACIÓN]: Marcha: {marcha} | Velocidad: {velocidad} km/h | Presión: {presion} Bar
                    [BOQUILLAS]: {n_boq} totales ({color_boq})
                    [EQUIPO]: Tractor: {tract_ot} | Tanque: {imple_ot} | Operario: {oper_ot}
                    [OBSERVACIONES]: {obs_ot}
                    """
                    
                    ot_data = {
                        "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                        "Status": "En Preparación",
                        "Fecha_Programada": str(f_ot),
                        "Sector_Aplicacion": sec_ot,
                        "Objetivo": obj_ot,
                        "Receta_Mezcla_Lotes": receta,
                        "Observaciones_Aplicacion": reporte_tecnico 
                    }
                    
                    try:
                        supabase.table('Ordenes_de_Trabajo').insert(ot_data).execute()
                        st.success("📡 Orden maestra creada. Almacén puede preparar y el tractorista ya la verá en su app.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al enviar la orden: {e}")

    # VISOR DE PENDIENTES EN ALMACÉN
    st.divider()
    df_pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()
    
    if df_pendientes.empty:
        st.info("No hay mezclas pendientes de preparación en almacén.")
    else:
        for _, ot in df_pendientes.iterrows():
            with st.container(border=True):
                col_i, col_a = st.columns([7, 3])
                with col_i:
                    st.subheader(f"🆔 {ot['ID_Orden_Personalizado']}")
                    st.write(f"📍 **Lote:** {ot['Sector_Aplicacion']} | 🎯 **Tratamiento:** {ot['Objetivo']}")
                    
                    # Mostramos brevemente los parámetros configurados para la mezcla
                    with st.expander("Ver Parámetros de Aplicación Configurados"):
                        st.text(ot.get('Observaciones_Aplicacion', 'Sin parámetros adicionales registrados.'))
                        
                    st.dataframe(pd.DataFrame(ot['Receta_Mezcla_Lotes']), hide_index=True)
                
                with col_a:
                    resp = st.text_input("Firma Responsable Almacén", key=f"r_{ot['id']}")
                    if st.button("✅ Confirmar Despacho", key=f"b_{ot['id']}", type="primary"):
                        if resp:
                            try:
                                batch = []
                                for item in ot['Receta_Mezcla_Lotes']:
                                    batch.append({
                                        "Fecha_Aplicacion": ot['Fecha_Programada'],
                                        "Ingreso_ID": item['id'],
                                        "Cantidad_Usada": item['c'],
                                        "Sector_Destino": ot['Sector_Aplicacion'],
                                        "Objetivo_Tratamiento": ot['Objetivo']
                                    })
                                
                                supabase.table('Salidas').insert(batch).execute()
                                
                                # Avanzamos el status para que ahora le toque al tractorista
                                supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                                
                                st.success("¡Despacho confirmado! Inventario descontado.")
                                st.cache_data.clear()
                                st.rerun()
                                
                            except Exception as e:
                                st.error(f"Error al guardar en Base de Datos: {e}")