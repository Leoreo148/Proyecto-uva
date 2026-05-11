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
    .card-auditoria { background-color: #ffffff; border-radius: 10px; padding: 15px; border-left: 5px solid #2ecc71; margin-bottom: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

st.title("⚗️ Centro de Mezclas y Salidas (Build 9.6)")
st.write("Control técnico y auditoría integral de aplicaciones.")

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS ---
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
        # Traemos TODO el historial de órdenes para la auditoría
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
tab1, tab2, tab3 = st.tabs(["🚀 Salida Rápida", "📋 Programar Mezcla", "📚 Historial y Auditoría"])

# ==========================================
# TAB 1: SALIDA DIRECTA RÁPIDA 
# ==========================================
with tab1:
    st.subheader("Descargo Directo de Almacén")
    if df_fefo.empty or not (df_fefo['Stock_Actual'] > 0).any():
        st.error("❌ No hay stock disponible.")
    else:
        df_disponible = df_fefo[df_fefo['Stock_Actual'] > 0].sort_values('Fecha_Vencimiento')
        opciones_lotes = { f"{r['Producto']} | Lote: {r['Codigo_Lote']} (Saldo: {r['Stock_Actual']:.2f} {r['Unidad']})": r for _, r in df_disponible.iterrows() }

        with st.form("salida_directa"):
            c1, c2 = st.columns([2, 1])
            lote_sel = c1.selectbox("Producto y Lote:", list(opciones_lotes.keys()))
            lote_info = opciones_lotes[lote_sel]
            cant_salida = c2.number_input(f"Cantidad ({lote_info['Unidad']}):", min_value=0.01, value=1.0)
            
            st.divider()
            c3, c4, c5 = st.columns(3)
            fecha = c3.date_input("Fecha", value=date.today())
            sector = c4.text_input("Sector Destino", placeholder="Ej: W3")
            objetivo = c5.selectbox("Objetivo", OBJETIVOS_COMUNES)
            
            if st.form_submit_button("⚡ Registrar Salida Directa", type="primary"):
                nueva_salida = { "Fecha_Aplicacion": str(fecha), "Ingreso_ID": int(lote_info['id']), "Cantidad_Usada": cant_salida, "Sector_Destino": sector, "Objetivo_Tratamiento": objetivo }
                supabase.table('Salidas').insert(nueva_salida).execute()
                st.success("✅ Salida registrada.")
                st.cache_data.clear()
                st.rerun()

# ==========================================
# TAB 2: ÓRDENES DE MEZCLA (EL INGENIERO MANDA)
# ==========================================
with tab2:
    with st.expander("👨‍🔬 Nueva Programación de Mezcla", expanded=True):
        if not df_fefo.empty:
            with st.form("nueva_ot_pro"):
                st.markdown('<div class="seccion-titulo">1. Datos Generales y Maquinaria</div>', unsafe_allow_html=True)
                ca1, ca2, ca3, ca4 = st.columns(4)
                f_ot = ca1.date_input("Fecha")
                sec_ot = ca2.text_input("Sector", placeholder="Ej: W3")
                ha_ot = ca3.number_input("Hectáreas", value=1.80)
                turno_ot = ca4.selectbox("Turno", ["Día", "Noche"])
                
                cm1, cm2, cm3 = st.columns(3)
                tract_ot = cm1.text_input("Tractor", placeholder="Ej: Antonio Carraro")
                imple_ot = cm2.text_input("Tanque", value="Full Maquinarias")
                oper_ot = cm3.text_input("Operario")

                st.markdown('<div class="seccion-titulo">2. Calibración y Agua</div>', unsafe_allow_html=True)
                cw1, cw2, cw3, cw4 = st.columns(4)
                vol_ha = cw1.number_input("Vol. Lts/Ha", value=1200)
                vol_tot = cw2.number_input("Vol. Total", value=2200)
                marcha = cw3.number_input("Marcha", value=1)
                presion = cw4.number_input("Presión (Bar)", value=9.0)

                st.markdown('<div class="seccion-titulo">3. Receta de Productos</div>', unsafe_allow_html=True)
                editor = st.data_editor(
                    pd.DataFrame([{"Insumo": list(opciones_lotes.keys())[0], "Cantidad": 0.0}]),
                    num_rows="dynamic",
                    column_config={
                        "Insumo": st.column_config.SelectboxColumn("Lote de Almacén", options=list(opciones_lotes.keys()), required=True),
                        "Cantidad": st.column_config.NumberColumn("Cantidad (Kg/L)", min_value=0.0)
                    }
                )

                if st.form_submit_button("📡 Enviar Orden Maestra", type="primary"):
                    receta = []
                    for _, row in editor.iterrows():
                        info = opciones_lotes[row['Insumo']]
                        receta.append({"id": int(info['id']), "p": info['Producto'], "l": info['Codigo_Lote'], "c": row['Cantidad']})
                    
                    reporte_tecnico = f"[ÁREA]: {ha_ot} Ha | [TURNO]: {turno_ot} | [AGUA]: {vol_tot}L ({vol_ha}L/Ha) | [CALIBRACIÓN]: M:{marcha} P:{presion} Bar | [EQUIPO]: {tract_ot} - {imple_ot}"
                    
                    ot_data = {
                        "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                        "Status": "En Preparación",
                        "Fecha_Programada": str(f_ot),
                        "Sector_Aplicacion": sec_ot,
                        "Objetivo": "Aplicación Mezcla",
                        "Receta_Mezcla_Lotes": receta,
                        "Observaciones_Aplicacion": reporte_tecnico 
                    }
                    supabase.table('Ordenes_de_Trabajo').insert(ot_data).execute()
                    st.success("📡 Orden enviada.")
                    st.cache_data.clear()
                    st.rerun()

    # VISOR DE PENDIENTES
    df_pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()
    if not df_pendientes.empty:
        st.subheader("⏳ Mezclas por Despachar (Almacén)")
        for _, ot in df_pendientes.iterrows():
            with st.container(border=True):
                c_ot1, c_ot2 = st.columns([3, 1])
                c_ot1.write(f"🆔 **{ot['ID_Orden_Personalizado']}** | 📍 {ot['Sector_Aplicacion']}")
                c_ot1.dataframe(pd.DataFrame(ot['Receta_Mezcla_Lotes']), hide_index=True)
                if c_ot2.button("✅ Despachar", key=f"d_{ot['id']}"):
                    batch = [{"Fecha_Aplicacion": ot['Fecha_Programada'], "Ingreso_ID": i['id'], "Cantidad_Usada": i['c'], "Sector_Destino": ot['Sector_Aplicacion'], "Objetivo_Tratamiento": ot['Objetivo']} for i in ot['Receta_Mezcla_Lotes']]
                    supabase.table('Salidas').insert(batch).execute()
                    supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                    st.rerun()

# ==========================================
# TAB 3: HISTORIAL Y AUDITORÍA (LO NUEVO)
# ==========================================
with tab3:
    st.subheader("📚 Registro Histórico de Mezclas")
    
    if df_ord.empty:
        st.info("No hay órdenes registradas.")
    else:
        # Filtramos órdenes que ya pasaron por almacén (Finalizada o Aplicada)
        df_audit = df_ord[df_ord['Status'].isin(['Finalizada', 'Aplicada en Campo'])].copy()
        
        # Botón de Descarga Excel
        csv = df_audit.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 Descargar Todo el Historial (Excel)", data=csv, file_name=f"auditoria_mezclas_{date.today()}.csv", mime="text/csv")
        
        st.write("---")
        
        # Mostramos las últimas 10 órdenes con detalle completo
        for _, ot in df_audit.head(10).iterrows():
            with st.container():
                st.markdown(f"""
                <div class="card-auditoria">
                    <b>🆔 {ot['ID_Orden_Personalizado']}</b> | 📅 {ot['Fecha_Programada']} | 📍 Sector: {ot['Sector_Aplicacion']} | 🚦 Estado: {ot['Status']}
                </div>
                """, unsafe_allow_html=True)
                
                col_aud1, col_aud2 = st.columns([1, 1])
                
                with col_aud2:
                    st.caption("⚙️ Parámetros Técnicos Programados:")
                    st.info(ot.get('Observaciones_Aplicacion', 'Sin datos técnicos.'))
                    
                    # 🛡️ FIX: Validamos que la fecha exista y sea texto antes de cortarla
                    fecha_fin = ot.get('Aplicacion_Completada_Fecha')
                    if pd.notna(fecha_fin) and str(fecha_fin).strip() not in ["", "NaT", "nan", "None"]:
                        # Reemplazamos la 'T' por un espacio para que se lea mejor (Ej: 2026-05-10 14:30)
                        st.success(f"🚜 Finalizado en campo: {str(fecha_fin)[:16].replace('T', ' ')}")
                    else:
                        st.warning("⏳ En espera de aplicación por el tractorista.")
                        
                with col_aud2:
                    st.caption("⚙️ Parámetros Técnicos Programados:")
                    st.info(ot.get('Observaciones_Aplicacion', 'Sin datos técnicos.'))
                    if ot.get('Aplicacion_Completada_Fecha'):
                        st.success(f"Finalizado en campo: {ot['Aplicacion_Completada_Fecha'][:16]}")
                st.write("---")