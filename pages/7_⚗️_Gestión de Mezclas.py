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
    </style>
    """, unsafe_allow_html=True)

st.title("⚗️ Centro de Mezclas y Salidas (Build 9.2)")
st.write("Control técnico de descargas: Trazabilidad total de aplicaciones en campo.")

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS AUDITADA ---
@st.cache_data(ttl=60)
def cargar_datos_operativos():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # Maestros
    p = supabase.table('Productos').select("Codigo, Producto, Unidad").execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Fecha_Vencimiento, Precio_Unitario_PEN").execute()
    
    # Salidas e Historial
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
    
    # Cálculo de stock disponible por ID único de ingreso
    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_lotes = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna({'Cantidad_Usada': 0})
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada'] - df_lotes['Cantidad_Usada']
    else:
        df_lotes = df_i.copy()
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada']

    df_final = pd.merge(df_lotes, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')
    
    # --- 🛡️ EL ESCUDO ANTI-ERRORES DE FECHA ---
    # Convertimos todo a formato Fecha. Si hay algo vacío o roto (errors='coerce'), 
    # lo vuelve 'NaT' (Not a Time) para que Pandas lo pueda ordenar sin colapsar.
    if 'Fecha_Vencimiento' in df_final.columns:
        df_final['Fecha_Vencimiento'] = pd.to_datetime(df_final['Fecha_Vencimiento'], errors='coerce')
        
    return df_final

# --- PROCESAMIENTO ---
df_prod, df_ing, df_sal, df_ord = cargar_datos_operativos()
df_fefo = obtener_stock_por_lote(df_prod, df_ing, df_sal)

OBJETIVOS_COMUNES = ["Fertilización", "Control de Plagas", "Control de Enfermedades", "Herbicida", "Riego", "Otro"]
LABORES_COMUNES = ["Motorista", "Aplicador Manual", "Riego tecnificado", "Foliar Tractor"]

# --- INTERFAZ ---
tab1, tab2 = st.tabs(["🚀 Salida Rápida (Directa)", "📋 Órdenes de Mezcla (Recetas)"])

# ==========================================
# TAB 1: SALIDA DIRECTA RÁPIDA (CON AUDITORÍA EXCEL)
# ==========================================
with tab1:
    st.subheader("Descargo Directo de Almacén")
    if df_fefo.empty or not (df_fefo['Stock_Actual'] > 0).any():
        st.error("❌ No hay stock disponible.")
    else:
        # FEFO: Mostramos los lotes que vencen primero arriba
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
            st.markdown("##### 📝 Datos Técnicos (Sync Excel)")
            c3, c4, c5 = st.columns(3)
            fecha = c3.date_input("Fecha", value=date.today())
            sector = c4.text_input("Sector Destino", placeholder="Ej: Lote 05")
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
                    "Objetivo_Tratamiento": objetivo,
                    "H2O": vol_h2o,
                    "Labor": labor,
                    "Documento": doc_guia
                }
                supabase.table('Salidas').insert(nueva_salida).execute()
                st.success("✅ Salida registrada e inventario actualizado.")
                st.cache_data.clear()
                st.rerun()

# ==========================================
# TAB 2: ÓRDENES DE MEZCLA (TRABAJO EN EQUIPO)
# ==========================================
with tab2:
    with st.expander("👨‍🔬 Programar Mezcla Multiproducto", expanded=False):
        if not df_fefo.empty:
            with st.form("nueva_ot_pro"):
                ca, cb, cc = st.columns(3)
                f_ot = ca.date_input("Fecha Programada")
                sec_ot = cb.text_input("Sector")
                obj_ot = cc.selectbox("Objetivo General", OBJETIVOS_COMUNES)
                
                # Datos de aplicación general
                h2o_ot = ca.number_input("Agua Total (L)", value=2000)
                labor_ot = cb.selectbox("Actividad", LABORES_COMUNES)
                
                st.write("**Composición del Tanque:**")
                editor = st.data_editor(
                    pd.DataFrame([{"Insumo": list(opciones_lotes.keys())[0], "Cantidad": 0.0}]),
                    num_rows="dynamic",
                    column_config={
                        "Insumo": st.column_config.SelectboxColumn("Lote", options=list(opciones_lotes.keys()), required=True),
                        "Cantidad": st.column_config.NumberColumn("Cantidad (Kg/L)", min_value=0.0)
                    }
                )

                if st.form_submit_button("📡 Enviar a Preparación"):
                    receta = []
                    for _, row in editor.iterrows():
                        info = opciones_lotes[row['Insumo']]
                        receta.append({"id": int(info['id']), "p": info['Producto'], "l": info['Codigo_Lote'], "c": row['Cantidad']})
                    
                    ot_data = {
                        "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                        "Status": "En Preparación",
                        "Fecha_Programada": str(f_ot),
                        "Sector_Aplicacion": sec_ot,
                        "Objetivo": obj_ot,
                        "Receta_Mezcla_Lotes": receta,
                        "Datos_Tecnicos": {"H2O": h2o_ot, "Labor": labor_ot}
                    }
                    supabase.table('Ordenes_de_Trabajo').insert(ot_data).execute()
                    st.success("📡 Orden enviada a Almacén.")
                    st.cache_data.clear()
                    st.rerun()

    # VISOR DE PENDIENTES
    st.divider()
    df_pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()
    
    if df_pendientes.empty:
        st.info("No hay mezclas pendientes.")
    else:
        for _, ot in df_pendientes.iterrows():
            with st.container(border=True):
                col_i, col_a = st.columns([7, 3])
                with col_i:
                    st.subheader(f"🆔 {ot['ID_Orden_Personalizado']}")
                    st.write(f"📍 **Sector:** {ot['Sector_Aplicacion']} | 🎯 **Objetivo:** {ot['Objetivo']}")
                    st.dataframe(pd.DataFrame(ot['Receta_Mezcla_Lotes']), hide_index=True)
                
                with col_a:
                    resp = st.text_input("Firma Responsable", key=f"r_{ot['id']}")
                    if st.button("✅ Confirmar Mezcla y Despacho", key=f"b_{ot['id']}"):
                        if resp:
                            try:
                                # Descontar cada item de la receta de la tabla Salidas
                                batch = []
                                for item in ot['Receta_Mezcla_Lotes']:
                                    batch.append({
                                        "Fecha_Aplicacion": ot['Fecha_Programada'],
                                        "Ingreso_ID": item['id'],
                                        "Cantidad_Usada": item['c'],
                                        "Sector_Destino": ot['Sector_Aplicacion'],
                                        "Objetivo_Tratamiento": ot['Objetivo']
                                        
                                        # ⚠️ COMENTADOS: Para que Supabase no rechace la inserción.
                                        # Si en el futuro creas estas columnas en tu SQL, solo quítales el "#"
                                        # "Responsable": resp,
                                        # "H2O": ot.get('Datos_Tecnicos', {}).get('H2O', 0),
                                        # "Labor": ot.get('Datos_Tecnicos', {}).get('Labor', '')
                                    })
                                
                                # Ejecutamos la subida a Supabase
                                supabase.table('Salidas').insert(batch).execute()
                                supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                                
                                st.success("¡Inventario descontado exitosamente!")
                                st.cache_data.clear()
                                st.rerun()
                                
                            except Exception as e:
                                # Escudo anti-caídas: Te mostrará el error en la app sin detener el programa
                                st.error(f"Error al guardar en Base de Datos: {e}")