import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Salidas y Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Centro de Mezclas y Salidas (Build 9.0)")
st.write("Control de descargas directas y formulación de recetas para campo.")

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE DATOS SEGURA ---
@st.cache_data(ttl=60)
def cargar_datos_operativos():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # 1. Productos e Ingresos
    p = supabase.table('Productos').select("Codigo, Producto, Unidad").execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Fecha_Vencimiento").execute()
    
    # 2. Salidas
    try:
        s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
        df_s = pd.DataFrame(s.data)
    except:
        df_s = pd.DataFrame() # Si no existe, devolvemos vacío sin romper la app
        
    # 3. Órdenes de Trabajo
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
        df_lotes = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna(0)
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada'] - df_lotes['Cantidad_Usada']
    else:
        df_lotes = df_i.copy()
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada']

    # Unir con nombres y unidades
    return pd.merge(df_lotes, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')

# --- PROCESAMIENTO ---
df_prod, df_ing, df_sal, df_ord = cargar_datos_operativos()
df_fefo = obtener_stock_por_lote(df_prod, df_ing, df_sal)

# Lista de Objetivos Agronómicos por defecto
OBJETIVOS_COMUNES = [
    "Fertilización", "Lavado de Campo", "Control de Plagas (Insecticida)", 
    "Control de Enfermedades (Fungicida)", "Control de Malezas (Herbicida)", 
    "Aplicación Foliar", "Inducción Floral", "Otro..."
]

# --- INTERFAZ DUAL ---
tab1, tab2 = st.tabs(["🚀 Salida Rápida (Directa)", "📋 Órdenes de Mezcla (Programación)"])

# ==========================================
# TAB 1: SALIDA DIRECTA RÁPIDA
# ==========================================
with tab1:
    st.subheader("Descargo Directo de Almacén")
    st.write("Útil para aplicaciones simples de un solo producto.")
    
    if df_fefo.empty or not (df_fefo['Stock_Actual'] > 0).any():
        st.error("❌ No hay stock disponible en el almacén.")
    else:
        df_disponible = df_fefo[df_fefo['Stock_Actual'] > 0].sort_values('Fecha_Vencimiento')
        opciones_lotes = {
            f"{r['Producto']} | Lote: {r['Codigo_Lote']} (Saldo: {r['Stock_Actual']:.2f} {r['Unidad']})": r 
            for _, r in df_disponible.iterrows()
        }

        with st.form("salida_rapida"):
            c1, c2 = st.columns([2, 1])
            lote_seleccionado = c1.selectbox("Seleccionar Producto y Lote a usar:", list(opciones_lotes.keys()))
            
            lote_info = opciones_lotes[lote_seleccionado]
            max_stock = float(lote_info['Stock_Actual'])
            
            cantidad_usar = c2.number_input(f"Cantidad a usar (Max: {max_stock:.2f})", min_value=0.01, max_value=max_stock, value=1.0)
            
            st.divider()
            col_a, col_b, col_c = st.columns(3)
            fecha_ap = col_a.date_input("Fecha de Aplicación", value=date.today())
            sector_ap = col_b.text_input("Sector / Lote Destino", placeholder="Ej. Lote 4 Uva")
            turno_ap = col_c.selectbox("Turno de Aplicación", ["Mañana", "Tarde", "Noche"])
            
            objetivo_ap = col_a.selectbox("Objetivo", OBJETIVOS_COMUNES)
            responsable = col_b.text_input("Responsable / Aplicador")

            if st.form_submit_button("⚡ Registrar Salida", type="primary"):
                if not sector_ap or not responsable:
                    st.warning("El Sector y el Responsable son obligatorios.")
                else:
                    nueva_salida = {
                        "Fecha_Aplicacion": str(fecha_ap),
                        "Ingreso_ID": int(lote_info['id']),
                        "Cantidad_Usada": cantidad_usar,
                        "Sector_Destino": sector_ap,
                        "Objetivo_Tratamiento": objetivo_ap,
                        "Turno": turno_ap,
                        "Responsable": responsable
                    }
                    try:
                        supabase.table('Salidas').insert(nueva_salida).execute()
                        st.success(f"✅ Se descontaron {cantidad_usar} {lote_info['Unidad']} de {lote_info['Producto']}.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error en base de datos: {e}")

# ==========================================
# TAB 2: ÓRDENES DE MEZCLA (RECETAS)
# ==========================================
with tab2:
    with st.expander("👨‍🔬 Programar Nueva Orden de Mezcla", expanded=False):
        if not df_fefo.empty and (df_fefo['Stock_Actual'] > 0).any():
            with st.form("nueva_ot"):
                c1, c2, c3 = st.columns(3)
                f_prog = c1.date_input("Fecha Programada")
                sector_ot = c2.text_input("Sector / Parcela", placeholder="Ej: Lote 05")
                turno_ot = c3.selectbox("Turno", ["Mañana", "Tarde", "Noche"])
                
                objetivo_ot = st.selectbox("Objetivo del Tratamiento", OBJETIVOS_COMUNES, key="obj_ot")

                st.write("**Composición de la Mezcla:**")
                editor_receta = st.data_editor(
                    pd.DataFrame([{"Insumo": list(opciones_lotes.keys())[0], "Dosis_Total": 0.0}]),
                    num_rows="dynamic",
                    column_config={
                        "Insumo": st.column_config.SelectboxColumn("Seleccionar Lote", options=list(opciones_lotes.keys()), required=True),
                        "Dosis_Total": st.column_config.NumberColumn("Cantidad a Extraer", min_value=0.0, format="%.2f")
                    }
                )

                if st.form_submit_button("📡 Enviar Orden a Almacén"):
                    receta_json = []
                    for _, row in editor_receta.iterrows():
                        info = opciones_lotes[row['Insumo']]
                        receta_json.append({
                            "ingreso_id": int(info['id']),
                            "producto": info['Producto'],
                            "lote_cod": info['Codigo_Lote'],
                            "cantidad": row['Dosis_Total']
                        })
                    
                    nueva_ot = {
                        "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                        "Status": "En Preparación",
                        "Fecha_Programada": str(f_prog),
                        "Sector_Aplicacion": sector_ot,
                        "Objetivo": objetivo_ot,
                        "Turno": turno_ot,
                        "Receta_Mezcla_Lotes": receta_json
                    }
                    try:
                        supabase.table('Ordenes_de_Trabajo').insert(nueva_ot).execute()
                        st.success("✅ Orden enviada exitosamente.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al crear Orden: {e}")

    st.divider()
    st.subheader("🧪 Órdenes Pendientes en Almacén")

    df_pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()

    if df_pendientes.empty:
        st.info("No hay mezclas pendientes. El almacén está al día.")
    else:
        for _, ot in df_pendientes.iterrows():
            with st.container(border=True):
                c_info, c_acc = st.columns([7, 3])
                
                with c_info:
                    st.markdown(f"### `{ot['ID_Orden_Personalizado']}`")
                    st.markdown(f"📍 **Sector:** {ot.get('Sector_Aplicacion', 'N/A')} | 🎯 **Objetivo:** {ot.get('Objetivo', 'N/A')} | 📅 **Fecha:** {ot.get('Fecha_Programada', '')}")
                    
                    df_det = pd.DataFrame(ot['Receta_Mezcla_Lotes'])
                    st.dataframe(df_det[['producto', 'lote_cod', 'cantidad']], hide_index=True)

                with c_acc:
                    st.write("---")
                    resp = st.text_input("Responsable de Mezcla", key=f"resp_{ot['id']}")
                    
                    if st.button("✅ Descontar del Inventario", key=f"btn_{ot['id']}", use_container_width=True):
                        if not resp:
                            st.warning("Indica quién preparó la mezcla.")
                        else:
                            try:
                                batch_salidas = []
                                for item in ot['Receta_Mezcla_Lotes']:
                                    batch_salidas.append({
                                        "Fecha_Aplicacion": ot['Fecha_Programada'],
                                        "Ingreso_ID": item['ingreso_id'],
                                        "Cantidad_Usada": item['cantidad'],
                                        "Sector_Destino": ot['Sector_Aplicacion'],
                                        "Objetivo_Tratamiento": ot['Objetivo'],
                                        "Turno": ot['Turno'],
                                        "Responsable": resp
                                    })
                                
                                supabase.table('Salidas').insert(batch_salidas).execute()
                                supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                                
                                st.success(f"¡Orden {ot['ID_Orden_Personalizado']} finalizada!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al procesar: {e}")