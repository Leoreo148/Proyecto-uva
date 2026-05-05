import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas y Pre-Mezclas (Build 8.0)")

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE DATOS (Optimizada) ---
@st.cache_data(ttl=60)
def cargar_datos_mezclas():
    # Traemos los ingresos con su ID para la trazabilidad real
    res_i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Fecha_Vencimiento, Productos(Producto)").execute()
    # Traemos las salidas para calcular el stock real disponible
    res_s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    # Órdenes y Objetivos
    res_o = supabase.table('Ordenes_de_Trabajo').select("*").order('created_at', desc=True).execute()
    res_obj = supabase.table('Maestro_Objetivos').select("*").execute()
    
    return pd.DataFrame(res_i.data), pd.DataFrame(res_s.data), pd.DataFrame(res_o.data), pd.DataFrame(res_obj.data)

def calcular_disponibilidad(df_i, df_s):
    if df_i.empty: return pd.DataFrame()
    
    # Normalizar datos de la relación con Productos
    df_i['Producto_Nombre'] = df_i['Productos'].apply(lambda x: x['Producto'] if x else "N/A")
    
    # Calcular saldos por Ingreso_ID
    if not df_s.empty:
        usado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_final = pd.merge(df_i, usado, left_on='id', right_on='Ingreso_ID', how='left').fillna(0)
        df_final['Stock_Real'] = df_final['Cantidad_Ingresada'] - df_final['Cantidad_Usada']
    else:
        df_final = df_i.copy()
        df_final['Stock_Real'] = df_final['Cantidad_Ingresada']
    
    return df_final[df_final['Stock_Real'] > 0]

# --- PROCESAMIENTO ---
df_i, df_s, df_ord, df_maestro_obj = cargar_datos_mezclas()
df_disponible = calcular_disponibilidad(df_i, df_s)

# --- SECCIÓN 1: INGENIERO (PROGRAMACIÓN) ---
st.subheader("👨‍🔬 Programación de Receta Técnica")
with st.expander("Crear nueva Orden de Trabajo", expanded=df_ord.empty):
    if df_maestro_obj.empty:
        st.warning("Debe configurar el Maestro de Objetivos en Supabase primero.")
    else:
        # Preparamos las opciones para el selector
        opciones_lotes = {
            f"{r['Producto_Nombre']} (Lote: {r['Codigo_Lote']}) | Saldo: {r['Stock_Real']}": r 
            for _, r in df_disponible.iterrows()
        }

        with st.form("form_ot", clear_on_submit=True):
            col1, col2, col3 = st.columns(3)
            f_prog = col1.date_input("Fecha de Aplicación")
            sector = col2.text_input("Sector / Lote de Campo")
            turno = col3.selectbox("Turno", ["Mañana", "Tarde", "Noche"])
            
            obj_nombres = df_maestro_obj['Nombre_Objetivo'].tolist()
            obj_sel = st.selectbox("Objetivo del Tratamiento", options=obj_nombres)
            obj_id = int(df_maestro_obj[df_maestro_obj['Nombre_Objetivo'] == obj_sel].iloc[0]['id'])

            # Editor de Receta
            st.write("**Composición de la Mezcla:**")
            receta_input = st.data_editor(
                pd.DataFrame([{"Lote": list(opciones_lotes.keys())[0] if opciones_lotes else "", "Cantidad": 0.0}]),
                num_rows="dynamic",
                column_config={
                    "Lote": st.column_config.SelectboxColumn("Lote en Almacén", options=list(opciones_lotes.keys()), required=True),
                    "Cantidad": st.column_config.NumberColumn("Dosis Total (L/Kg)", format="%.3f")
                },
                key="editor_mezcla"
            )

            if st.form_submit_button("🚀 Generar Orden de Trabajo"):
                receta_final = []
                for _, row in receta_input.iterrows():
                    lote_info = opciones_lotes[row['Lote']]
                    receta_final.append({
                        "ingreso_id": int(lote_info['id']),
                        "producto": lote_info['Producto_Nombre'],
                        "lote": lote_info['Codigo_Lote'],
                        "cantidad": row['Cantidad']
                    })
                
                nueva_ot = {
                    "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d%H%M')}",
                    "Status": "Pendiente de Mezcla",
                    "Fecha_Programada": str(f_prog),
                    "Sector_Aplicacion": sector,
                    "Objetivo": obj_id,
                    "Turno": turno,
                    "Receta_Mezcla_Lotes": receta_final
                }
                supabase.table('Ordenes_de_Trabajo').insert(nueva_ot).execute()
                st.success("Orden enviada a Almacén/Mezcla.")
                st.cache_data.clear()
                st.rerun()

# --- SECCIÓN 2: MEZCLA Y SALIDA AUTOMÁTICA ---
st.divider()
st.subheader("🧪 Preparación y Despacho de Mezclas")

pendientes = df_ord[df_ord['Status'] == 'Pendiente de Mezcla'] if not df_ord.empty else pd.DataFrame()

if pendientes.empty:
    st.info("No hay mezclas pendientes de preparación.")
else:
    for _, ot in pendientes.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([7, 3])
            with c1:
                st.write(f"### 📄 {ot['ID_Orden_Personalizado']}")
                st.caption(f"Sector: {ot['Sector_Aplicacion']} | Turno: {ot['Turno']}")
                # Mostrar tabla detallada de la receta
                df_det = pd.DataFrame(ot['Receta_Mezcla_Lotes'])
                st.dataframe(df_det[['producto', 'lote', 'cantidad']], use_container_width=True)
            
            with c2:
                st.write("###")
                responsable = st.text_input("Quién prepara?", key=f"resp_{ot['id']}")
                
                if st.button("✅ Confirmar Mezcla y Salida", key=f"btn_{ot['id']}", type="primary"):
                    if not responsable:
                        st.warning("Debe asignar un responsable.")
                    else:
                        try:
                            # 1. GENERAR SALIDAS AUTOMÁTICAS (HISTORIAL)
                            batch_salidas = []
                            for item in ot['Receta_Mezcla_Lotes']:
                                batch_salidas.append({
                                    "Fecha_Aplicacion": ot['Fecha_Programada'],
                                    "Ingreso_ID": item['ingreso_id'],
                                    "Cantidad_Usada": item['cantidad'],
                                    "Sector_Destino": ot['Sector_Aplicacion'],
                                    "Objetivo_Tratamiento": ot['Objetivo'],
                                    "Turno": ot['Turno'],
                                    "Responsable": responsable
                                })
                            
                            # Insertar todas las salidas de un solo golpe
                            supabase.table('Salidas').insert(batch_salidas).execute()
                            
                            # 2. ACTUALIZAR ESTADO DE LA OT
                            supabase.table('Ordenes_de_Trabajo').update({"Status": "Lista para Aplicar"}).eq('id', ot['id']).execute()
                            
                            st.toast(f"Inventario actualizado para la {ot['ID_Orden_Personalizado']}")
                            st.cache_data.clear()
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error al procesar: {e}")