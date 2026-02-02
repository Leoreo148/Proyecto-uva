import streamlit as st
import pandas as pd
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas y Pre-Mezclas (Build 7)")
st.write("Programación técnica de recetas y confirmación de salidas de almacén.")

# --- FUNCIÓN DE CONEXIÓN SEGURA ---
@st.cache_resource
def init_supabase_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Error al conectar con Supabase: {e}")
        return None

supabase = init_supabase_connection()

# --- CARGA DE DATOS NORMALIZADA ---
@st.cache_data(ttl=60)
def cargar_datos_mezclas():
    if supabase:
        try:
            # Traer tablas maestras y de movimiento
            res_p = supabase.table('Productos').select("Codigo, Producto").execute()
            res_i = supabase.table('Ingresos').select("*").execute()
            res_s = supabase.table('Salidas').select("*").execute()
            res_o = supabase.table('Ordenes_de_Trabajo').select("*").order('created_at', desc=True).execute()
            res_obj = supabase.table('Maestro_Objetivos').select("*").execute()
            
            return (pd.DataFrame(res_p.data), pd.DataFrame(res_i.data), 
                    pd.DataFrame(res_s.data), pd.DataFrame(res_o.data), 
                    pd.DataFrame(res_obj.data))
        except Exception as e:
            st.error(f"Error al cargar datos: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def calcular_stock_lotes(df_i, df_s, df_p):
    if df_i.empty: return pd.DataFrame()
    
    # Cálculos de stock (igual que en Kardex)
    df_i['Cantidad'] = pd.to_numeric(df_i['Cantidad'], errors='coerce').fillna(0)
    df_s['Cantidad'] = pd.to_numeric(df_s['Cantidad'], errors='coerce').fillna(0)
    
    ing = df_i.groupby(['Codigo_Producto', 'Codigo_Lote']).agg({'Cantidad': 'sum', 'Fecha_Vencimiento': 'first'}).reset_index()
    sal = df_s.groupby(['Codigo_Producto', 'Codigo_Lote'])['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cant_Sal'})
    
    df_stock = pd.merge(ing, sal, on=['Codigo_Producto', 'Codigo_Lote'], how='left').fillna(0)
    df_stock['Stock_Restante'] = df_stock['Cantidad'] - df_stock['Cant_Sal']
    
    # Unir con nombres de productos
    return pd.merge(df_stock, df_p, left_on='Codigo_Producto', right_on='Codigo', how='left')

# --- CARGA INICIAL ---
df_prod, df_ing, df_sal, df_ord, df_maestro_obj = cargar_datos_mezclas()
df_disponible = calcular_stock_lotes(df_ing, df_sal, df_prod)

# --- SECCIÓN 1: INGENIERO (PROGRAMACIÓN) ---
with st.expander("👨‍🔬 Programar Nueva Receta", expanded=True):
    if df_disponible.empty or df_maestro_obj.empty:
        st.warning("⚠️ Se requieren productos con stock y objetivos configurados.")
    else:
        # Preparar opciones de lotes (FEFO: Primero en vencer, primero en salir)
        df_fefo = df_disponible[df_disponible['Stock_Restante'] > 0].sort_values('Fecha_Vencimiento')
        opciones_lotes = {f"{r['Producto']} ({r['Codigo_Lote']}) | Stock: {r['Stock_Restante']:.2f}": r for _, r in df_fefo.iterrows()}
        
        # Diccionario de objetivos: Nombre -> ID
        dict_obj = {r['nombre']: r['id'] for _, r in df_maestro_obj.iterrows()}

        with st.form("form_receta"):
            c1, c2, c3 = st.columns(3)
            with c1: f_prog = st.date_input("Fecha Programada")
            with c2: sector = st.text_input("Sector de Aplicación (Ej: Lote 05)")
            with c3: turno = st.selectbox("Turno", ["Día", "Noche"])
            
            obj_seleccionado = st.selectbox("Objetivo del Tratamiento", options=list(dict_obj.keys()))
            
            st.markdown("---")
            # Editor de Receta
            receta_input = st.data_editor(
                pd.DataFrame([{"Lote": list(opciones_lotes.keys())[0], "Cantidad": 0.0}]),
                num_rows="dynamic",
                column_config={
                    "Lote": st.column_config.SelectboxColumn("Seleccione Lote", options=list(opciones_lotes.keys()), required=True, width="large"),
                    "Cantidad": st.column_config.NumberColumn("Cantidad (Kg/L)", min_value=0.0, format="%.4f")
                }, key="editor_mezcla"
            )

            if st.form_submit_button("✅ Guardar Orden de Mezcla"):
                receta_final = []
                for _, row in receta_input.iterrows():
                    lote_data = opciones_lotes[row['Lote']]
                    receta_final.append({
                        "Codigo_Lote": lote_data['Codigo_Lote'],
                        "Codigo_Producto": lote_data['Codigo_Producto'],
                        "Producto": lote_data['Producto'], # Guardamos el nombre para visualización rápida
                        "Cantidad": row['Cantidad']
                    })
                
                nueva_orden = {
                    "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d%H%M')}",
                    "Status": "Pendiente de Mezcla",
                    "Fecha_Programada": f_prog.strftime('%Y-%m-%d'),
                    "Sector_Aplicacion": sector,
                    "Objetivo": dict_obj[obj_seleccionado], # Guardamos el ID del maestro
                    "Turno": turno,
                    "Receta_Mezcla_Lotes": receta_final
                }
                
                try:
                    supabase.table('Ordenes_de_Trabajo').insert(nueva_orden).execute()
                    st.success("Orden programada correctamente.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")

# --- SECCIÓN 2: ENCARGADO (CONFIRMACIÓN) ---
st.divider()
st.subheader("📋 Recetas por Preparar")

ordenes_pendientes = df_ord[df_ord['Status'] == 'Pendiente de Mezcla'] if not df_ord.empty else pd.DataFrame()

if ordenes_pendientes.empty:
    st.info("No hay órdenes pendientes de preparación.")
else:
    # Unir con maestro objetivos para mostrar el nombre en lugar del ID
    df_pendientes_view = pd.merge(ordenes_pendientes, df_maestro_obj, left_on='Objetivo', right_on='id', how='left')
    
    for _, tarea in df_pendientes_view.iterrows():
        with st.container(border=True):
            col_info, col_btn = st.columns([8, 2])
            with col_info:
                st.markdown(f"**Orden:** `{tarea['ID_Orden_Personalizado']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Objetivo:** {tarea['nombre']}")
                df_det = pd.DataFrame(tarea['Receta_Mezcla_Lotes'])
                st.table(df_det[['Producto', 'Codigo_Lote', 'Cantidad']])
            
            with col_btn:
                st.write("")
                if st.button("✅ Confirmar Mezcla", key=f"conf_{tarea['id_x']}"):
                    try:
                        # 1. Registrar Salidas de Almacén
                        salidas_data = []
                        for item in tarea['Receta_Mezcla_Lotes']:
                            salidas_data.append({
                                "Fecha": datetime.now().strftime('%Y-%m-%d'),
                                "Lote_Sector": tarea['Sector_Aplicacion'],
                                "Turno": tarea['Turno'],
                                "Codigo_Producto": item['Codigo_Producto'],
                                "Codigo_Lote": item['Codigo_Lote'],
                                "Cantidad": item['Cantidad'],
                                "Objetivo_Tratamiento": tarea['Objetivo'] # ID del maestro
                            })
                        
                        supabase.table('Salidas').insert(salidas_data).execute()
                        
                        # 2. Actualizar estado de la Orden
                        supabase.table('Ordenes_de_Trabajo').update({"Status": "Lista para Aplicar"}).eq('id', tarea['id_x']).execute()
                        
                        st.toast("Mezcla confirmada e inventario actualizado.")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error en confirmación: {e}")