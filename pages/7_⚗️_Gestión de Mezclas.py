import streamlit as st
import pandas as pd
import json
from datetime import datetime

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Mezclas", page_icon="⚗️", layout="wide")
st.title("⚗️ Gestión de Mezclas y Pre-Mezclas por Lote")
st.write("El ingeniero programa la receta y los cálculos de pre-mezcla. El encargado confirma la preparación.")

# --- FUNCIÓN DE CONEXIÓN SEGURA A SUPABASE ---
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

# --- NUEVAS FUNCIONES ADAPTADAS PARA SUPABASE ---
@st.cache_data(ttl=60)
def cargar_datos_para_mezclas():
    """Carga todos los datos necesarios para la gestión de mezclas desde Supabase."""
    if supabase:
        try:
            res_ingresos = supabase.table('Ingresos').select("*").execute()
            df_ingresos = pd.DataFrame(res_ingresos.data)
            
            res_salidas = supabase.table('Salidas').select("*").execute()
            df_salidas = pd.DataFrame(res_salidas.data)
            
            res_ordenes = supabase.table('Ordenes_de_Trabajo').select("*").execute()
            df_ordenes = pd.DataFrame(res_ordenes.data)
            
            return df_ingresos, df_salidas, df_ordenes
        except Exception as e:
            st.error(f"Error al cargar datos de Supabase: {e}")
    return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def calcular_stock_por_lote(df_ingresos, df_salidas):
    """Calcula el stock actual por cada lote. Reutilizada del módulo de Kardex."""
    if df_ingresos.empty:
        return pd.DataFrame()
    
    df_ingresos['Cantidad'] = pd.to_numeric(df_ingresos['Cantidad'], errors='coerce').fillna(0)
    if not df_salidas.empty:
        df_salidas['Cantidad'] = pd.to_numeric(df_salidas['Cantidad'], errors='coerce').fillna(0)

    ingresos_por_lote = df_ingresos.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Ingresada'})
    
    if not df_salidas.empty and 'Codigo_Lote' in df_salidas.columns:
        salidas_por_lote = df_salidas.groupby('Codigo_Lote')['Cantidad'].sum().reset_index().rename(columns={'Cantidad': 'Cantidad_Consumida'})
        stock_lotes = pd.merge(ingresos_por_lote, salidas_por_lote, on='Codigo_Lote', how='left').fillna(0)
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada'] - stock_lotes['Cantidad_Consumida']
    else:
        stock_lotes = ingresos_por_lote
        stock_lotes['Stock_Restante'] = stock_lotes['Cantidad_Ingresada']
        
    lote_info = df_ingresos.drop_duplicates(subset=['Codigo_Lote'])[['Codigo_Lote', 'Codigo_Producto', 'Producto', 'Fecha_Vencimiento']]
    stock_lotes_detallado = pd.merge(stock_lotes, lote_info, on='Codigo_Lote', how='left')
    return stock_lotes_detallado

# --- CARGA DE DATOS ---
df_ingresos, df_salidas, df_ordenes = cargar_datos_para_mezclas()
df_stock_lotes = calcular_stock_por_lote(df_ingresos, df_salidas)

# --- SECCIÓN 1 (INGENIERO): PROGRAMAR NUEVA RECETA ---
with st.expander("👨‍🔬 Programar Nueva Receta de Mezcla (Ingeniero)", expanded=True):
    lotes_activos = df_stock_lotes[df_stock_lotes['Stock_Restante'] > 0].copy() if not df_stock_lotes.empty else pd.DataFrame()
    opciones_lotes = []
    if not lotes_activos.empty:
        lotes_activos['Fecha_Vencimiento'] = pd.to_datetime(lotes_activos['Fecha_Vencimiento'], errors='coerce').dt.strftime('%Y-%m-%d')
        lotes_activos = lotes_activos.sort_values(by='Fecha_Vencimiento', ascending=True)
        for _, row in lotes_activos.iterrows():
            label = f"{row['Producto']} ({row['Codigo_Lote']}) | Stock: {row['Stock_Restante']:.5f} | Vence: {row.get('Fecha_Vencimiento', 'N/A')}"
            opciones_lotes.append(label)

    with st.form("programar_form"):
        st.subheader("Datos Generales de la Orden")
        col1, col2, col3 = st.columns(3)
        with col1: fecha_aplicacion = st.date_input("Fecha Programada")
        with col2: sector_aplicacion = st.text_input("Lote / Sector de Aplicación")
        with col3: turno = st.selectbox("Turno", ["Día", "Noche"])
        objetivo_tratamiento = st.text_input("Objetivo del Tratamiento", placeholder="Ej: Control de Oídio y Trips")
        
        st.subheader("Receta y Pre-Mezcla")
        if not opciones_lotes:
            st.warning("No hay lotes con stock disponible para crear una receta.")
            productos_para_mezcla = None
        else:
            productos_para_mezcla = st.data_editor(
                pd.DataFrame([{"Lote_Seleccionado": opciones_lotes[0], "Total_Producto": 1.0, "Total_Pre_Mezcla": 10.0}]),
                num_rows="dynamic",
                column_config={
                    "Lote_Seleccionado": st.column_config.SelectboxColumn("Seleccione el Lote a Usar", options=opciones_lotes, required=True, width="large"),
                    "Total_Producto": st.column_config.NumberColumn("Total Producto (kg/L)", help="Cantidad de producto a usar.", min_value=0.00001, format="%.5f"),
                    "Total_Pre_Mezcla": st.column_config.NumberColumn("Total Pre-Mezcla (L)", help="Volumen final de la pre-mezcla con agua.", min_value=0.1, format="%.2f")
                }, key="editor_mezcla_premezcla"
            )

        submitted_programar = st.form_submit_button("✅ Programar Orden de Mezcla")

        if submitted_programar and productos_para_mezcla is not None and supabase:
            receta_final = []
            error_validacion = False
            for _, row in productos_para_mezcla.iterrows():
                codigo_lote = row['Lote_Seleccionado'].split('(')[1].split(')')[0].strip()
                stock_disponible = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote]['Stock_Restante'].iloc[0]
                
                if row['Total_Producto'] > stock_disponible:
                    st.error(f"Stock insuficiente para el lote {codigo_lote}. Solicitado: {row['Total_Producto']}, Disponible: {stock_disponible}")
                    error_validacion = True
                    break
                
                info_lote = lotes_activos[lotes_activos['Codigo_Lote'] == codigo_lote].iloc[0]
                
                receta_final.append({
                    'Codigo_Lote': codigo_lote, 'Producto': info_lote['Producto'],
                    'Codigo_Producto': info_lote['Codigo_Producto'],
                    'Total_Producto': row['Total_Producto'],
                    'Volumen_Pre_Mezcla_L': row['Total_Pre_Mezcla']
                })
            
            if not error_validacion:
                try:
                    id_orden = datetime.now().strftime("OT-%Y%m%d%H%M%S")
                    nueva_orden_data = {
                        "ID_Orden_Personalizado": id_orden, 
                        "Status": "Pendiente de Mezcla", 
                        "Fecha_Programada": fecha_aplicacion.strftime("%Y-%m-%d"), 
                        "Sector_Aplicacion": sector_aplicacion, 
                        "Objetivo": objetivo_tratamiento, 
                        "Turno": turno, 
                        "Receta_Mezcla_Lotes": receta_final # Se guarda como JSONB
                    }
                    supabase.table('Ordenes_de_Trabajo').insert(nueva_orden_data).execute()
                    st.success(f"¡Orden de mezcla '{id_orden}' programada exitosamente!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar la orden en Supabase: {e}")

st.divider()

# --- SECCIÓN 2 (ENCARGADO): TAREAS PENDIENTES ---
st.subheader("📋 Recetas Pendientes de Preparar (Encargado de Mezcla)")
tareas_pendientes = df_ordenes[df_ordenes['Status'] == 'Pendiente de Mezcla'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_pendientes.empty:
    for index, tarea in tareas_pendientes.iterrows():
        with st.container(border=True):
            st.markdown(f"**Orden ID:** `{tarea['ID_Orden_Personalizado']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Fecha:** {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}")
            
            # La receta ya viene como una lista de diccionarios desde Supabase
            receta = tarea['Receta_Mezcla_Lotes']
            df_receta = pd.DataFrame(receta)
            
            st.dataframe(
                df_receta[['Producto', 'Total_Producto', 'Volumen_Pre_Mezcla_L']],
                use_container_width=True,
                column_config={
                    "Total_Producto": st.column_config.NumberColumn("Total Producto", format="%.5f"),
                    "Volumen_Pre_Mezcla_L": st.column_config.NumberColumn("Total Pre-Mezcla (L)", format="%.2f")
                }
            )
            
            if st.button("✅ Confirmar Preparación y Registrar Salida", key=f"confirm_{tarea['id']}"):
                try:
                    nuevas_salidas = []
                    for item in receta:
                        nuevas_salidas.append({
                            'Fecha': datetime.now().strftime("%Y-%m-%d"), 
                            'Lote_Sector': tarea['Sector_Aplicacion'], 
                            'Turno': tarea['Turno'], 
                            'Producto': item['Producto'], 
                            'Cantidad': item['Total_Producto'], 
                            'Codigo_Producto': item['Codigo_Producto'], 
                            'Objetivo_Tratamiento': tarea['Objetivo'], 
                            'Codigo_Lote': item['Codigo_Lote']
                        })
                    
                    # Insertar todas las salidas en la tabla 'Salidas'
                    supabase.table('Salidas').insert(nuevas_salidas).execute()
                    
                    # Actualizar el estado de la orden a 'Lista para Aplicar'
                    supabase.table('Ordenes_de_Trabajo').update({'Status': 'Lista para Aplicar'}).eq('id', tarea['id']).execute()
                    
                    st.success(f"Salida para la orden '{tarea['ID_Orden_Personalizado']}' registrada. Stock actualizado.")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al confirmar la preparación: {e}")
else:
    st.info("No hay recetas pendientes de preparar.")
