import streamlit as st
import pandas as pd
from datetime import datetime
from supabase import create_client

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mezclas Pro", page_icon="⚗️", layout="wide")
st.title("⚗️ Centro de Mezclas y Órdenes de Trabajo (Build 8.3)")

# --- CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- CARGA DE DATOS ---
@st.cache_data(ttl=60)
def cargar_datos_operativos():
    if not supabase: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    
    # 1. Productos e Ingresos (para saber qué hay en stock)
    p = supabase.table('Productos').select("Codigo, Producto").execute()
    i = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Fecha_Vencimiento").execute()
    
    # 2. Salidas existentes (para calcular saldo real)
    s = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    
    # 3. Órdenes y Objetivos
    o = supabase.table('Ordenes_de_Trabajo').select("*").order('created_at', desc=True).execute()
    obj = supabase.table('Maestro_Objetivos').select("*").execute()
    
    return pd.DataFrame(p.data), pd.DataFrame(i.data), pd.DataFrame(s.data), pd.DataFrame(o.data), pd.DataFrame(obj.data)

def obtener_stock_por_lote(df_p, df_i, df_s):
    if df_i.empty: return pd.DataFrame()
    
    # Calcular cuánto se ha gastado de cada ID de ingreso
    if not df_s.empty:
        gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index()
        df_lotes = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna(0)
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada'] - df_lotes['Cantidad_Usada']
    else:
        df_lotes = df_i.copy()
        df_lotes['Stock_Actual'] = df_lotes['Cantidad_Ingresada']

    # Unir con nombres de productos
    return pd.merge(df_lotes, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')

# --- PROCESAMIENTO ---
df_prod, df_ing, df_sal, df_ord, df_maestro_obj = cargar_datos_operativos()
df_fefo = obtener_stock_por_lote(df_prod, df_ing, df_sal)

# --- SECCIÓN 1: INGENIERÍA (PROGRAMACIÓN) ---
with st.expander("👨‍🔬 Programar Orden de Mezcla", expanded=True):
    if df_maestro_obj.empty:
        st.warning("⚠️ No hay objetivos configurados. Configure 'Maestro_Objetivos' en Supabase.")
    elif df_fefo.empty or not (df_fefo['Stock_Actual'] > 0).any():
        st.error("❌ Alerta: No hay stock disponible en el almacén para programar mezclas.")
    else:
        # Filtrar solo lo que tiene stock y ordenar por vencimiento (FEFO)
        df_disponible = df_fefo[df_fefo['Stock_Actual'] > 0].sort_values('Fecha_Vencimiento')
        
        # Crear diccionario para el selectbox del data_editor
        opciones_lotes = {
            f"{r['Producto']} | Lote: {r['Codigo_Lote']} (Saldo: {r['Stock_Actual']:.2f})": r 
            for _, r in df_disponible.iterrows()
        }

        with st.form("nueva_ot"):
            c1, c2, c3 = st.columns(3)
            f_prog = c1.date_input("Fecha de Aplicación")
            sector = c2.text_input("Sector / Parcela", placeholder="Ej: Lote 05 - Uva Red Globe")
            turno = c3.selectbox("Turno", ["Mañana", "Tarde", "Noche"])
            
            objetivo_nombre = st.selectbox("Objetivo del Tratamiento", 
                                           options=df_maestro_obj['Nombre_Objetivo'].tolist())
            obj_id = int(df_maestro_obj[df_maestro_obj['Nombre_Objetivo'] == objetivo_nombre].iloc[0]['id'])

            st.write("**Composición de la Mezcla:**")
            editor_receta = st.data_editor(
                pd.DataFrame([{"Insumo": list(opciones_lotes.keys())[0], "Dosis_Total": 0.0}]),
                num_rows="dynamic",
                column_config={
                    "Insumo": st.column_config.SelectboxColumn("Seleccionar Lote", options=list(opciones_lotes.keys()), required=True),
                    "Dosis_Total": st.column_config.NumberColumn("Cantidad (Kg/L)", min_value=0.0, format="%.3f")
                }
            )

            if st.form_submit_button("📡 Enviar a Almacén"):
                receta_json = []
                for _, row in editor_receta.iterrows():
                    lote_info = opciones_lotes[row['Insumo']]
                    receta_json.append({
                        "ingreso_id": int(lote_info['id']),
                        "producto": lote_info['Producto'],
                        "lote_cod": lote_info['Codigo_Lote'],
                        "cantidad": row['Dosis_Total']
                    })
                
                nueva_ot = {
                    "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                    "Status": "En Preparación",
                    "Fecha_Programada": str(f_prog),
                    "Sector_Aplicacion": sector,
                    "Objetivo": obj_id,
                    "Turno": turno,
                    "Receta_Mezcla_Lotes": receta_json
                }
                supabase.table('Ordenes_de_Trabajo').insert(nueva_ot).execute()
                st.cache_data.clear()
                st.rerun()

# --- SECCIÓN 2: ALMACÉN / MEZCLA (EJECUCIÓN) ---
st.divider()
st.subheader("🧪 Órdenes Pendientes de Mezcla")

# Filtrar OT que no han sido aplicadas
df_pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()

if df_pendientes.empty:
    st.info("No hay mezclas pendientes. El tractorista está al día.")
else:
    for _, ot in df_pendientes.iterrows():
        with st.container(border=True):
            c_info, c_acc = st.columns([7, 3])
            
            with c_info:
                obj_txt = df_maestro_obj[df_maestro_obj['id'] == ot['Objetivo']].iloc[0]['Nombre_Objetivo']
                st.markdown(f"### `{ot['ID_Orden_Personalizado']}`")
                st.markdown(f"📍 **Sector:** {ot['Sector_Aplicacion']} | 🎯 **Objetivo:** {obj_txt}")
                
                # Mostrar detalle de la receta
                df_det = pd.DataFrame(ot['Receta_Mezcla_Lotes'])
                st.dataframe(df_det[['producto', 'lote_cod', 'cantidad']], hide_index=True)

            with c_acc:
                st.write("---")
                responsable = st.text_input("Responsable de Mezcla", key=f"resp_{ot['id']}")
                
                if st.button("✅ Confirmar Salida e Inventario", key=f"btn_{ot['id']}", use_container_width=True):
                    if not responsable:
                        st.warning("Escriba quién prepara la mezcla.")
                    else:
                        try:
                            # 1. GENERAR SALIDAS AUTOMÁTICAS
                            # Aquí es donde ocurre la magia: insertamos en 'Salidas' usando el Ingreso_ID guardado
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
                            
                            supabase.table('Salidas').insert(batch_salidas).execute()
                            
                            # 2. ACTUALIZAR STATUS DE LA ORDEN
                            supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                            
                            st.success(f"¡Inventario actualizado para la orden {ot['ID_Orden_Personalizado']}!")
                            st.cache_data.clear()
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"Error al procesar salida: {e}")