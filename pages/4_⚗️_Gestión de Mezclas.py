import streamlit as st
import pandas as pd
from datetime import datetime, date
from supabase import create_client

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="Gestión de Salidas y Mezclas - Project Uva", page_icon="⚗️", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #f8f9fa; }
    .seccion-titulo { color: #1e3d33; font-weight: 600; margin-top: 15px; border-bottom: 2px solid #2ecc71; padding-bottom: 5px;}
    div[data-testid="stMetric"] { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIÓN ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

supabase = init_supabase()

# --- 3. CARGA DE DATOS RELACIONALES (Jalando de tus tablas SQL reales) ---
@st.cache_data(ttl=60)
def cargar_catalogos():
    pers = supabase.table('Personal').select("id, nombre_completo").eq('activo', True).execute()
    maq = supabase.table('Maquinaria').select("id, nombre").execute()
    prod = supabase.table('Productos').select("Codigo, Producto, Unidad").execute()
    ing = supabase.table('Ingresos').select("id, Codigo_Producto, Codigo_Lote, Cantidad_Ingresada, Precio_Unitario_PEN").execute()
    sal = supabase.table('Salidas').select("Ingreso_ID, Cantidad_Usada").execute()
    ord_ = supabase.table('Ordenes_de_Trabajo').select("*").order('created_at', desc=True).execute()

    return pd.DataFrame(pers.data), pd.DataFrame(maq.data), pd.DataFrame(prod.data), pd.DataFrame(ing.data), pd.DataFrame(sal.data), pd.DataFrame(ord_.data)

df_pers, df_maq, df_prod, df_ing, df_sal, df_ord = cargar_catalogos()

# Motor FEFO (First Expired, First Out)
def obtener_fefo(df_p, df_i, df_s):
    if df_i.empty: return pd.DataFrame()
    gastado = df_s.groupby('Ingreso_ID')['Cantidad_Usada'].sum().reset_index() if not df_s.empty else pd.DataFrame(columns=['Ingreso_ID', 'Cantidad_Usada'])
    df_res = pd.merge(df_i, gastado, left_on='id', right_on='Ingreso_ID', how='left').fillna(0)
    df_res['Stock_Actual'] = df_res['Cantidad_Ingresada'] - df_res['Cantidad_Usada']
    return pd.merge(df_res[df_res['Stock_Actual'] > 0], df_p, left_on='Codigo_Producto', right_on='Codigo')

df_stock = obtener_fefo(df_prod, df_ing, df_sal)

# --- 4. INTERFAZ PRINCIPAL ---
st.title("⚗️ Centro de Mezclas y Auditoría Técnica")
tab1, tab2, tab3 = st.tabs(["📋 Programar Mezcla (Ingeniero)", "🚚 Almacén y Despacho", "💰 Historial de Costos"])

# ==========================================
# TAB 1: PROGRAMAR MEZCLA (Foliar vs Fertirriego)
# ==========================================
with tab1:
    if df_stock.empty:
        st.warning("⚠️ No hay stock disponible en el Kardex para programar mezclas.")
    else:
        # 💡 EL INTERRUPTOR MÁGICO: Separa visualmente las labores
        tipo_labor = st.radio(
            "Seleccione el Tipo de Labor a Programar:", 
            ["🚜 Aplicación Foliar (Maquinaria/Mochila)", "💧 Fertirriego (Sistema de Riego)"],
            horizontal=True
        )
        st.write("---")

        with st.form("nueva_ot_belessia"):
            st.markdown('<div class="seccion-titulo">1. Ubicación General</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            f_prog = c1.date_input("Fecha Programada", value=date.today())
            SECTORES_UVA = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2', 'K3']
            sec_dest = c2.selectbox("Sector / Lote Destino", options=SECTORES_UVA)
            ha_dest = c3.number_input("Hectáreas a tratar", min_value=0.1, value=1.8)
            obj_app = c4.text_input("Objetivo (Ej: Nutrición, Trips)")

            st.markdown('<div class="seccion-titulo">2. Parámetros Técnicos</div>', unsafe_allow_html=True)
            
            # Listas de base de datos
            lista_opers = df_pers['nombre_completo'].tolist() if not df_pers.empty else ["Sin personal"]
            lista_maqs = df_maq['nombre'].tolist() if not df_maq.empty else ["Sin maquinaria"]

            # 🔀 LÓGICA CONDICIONAL: Cambia el formulario según el botón de arriba
            if "Foliar" in tipo_labor:
                cf1, cf2, cf3 = st.columns(3)
                oper_sel = cf1.selectbox("Operario / Tractorista", options=lista_opers)
                maq_sel = cf2.selectbox("Tractor Utilizado", options=lista_maqs)
                tipo_app = cf3.selectbox("Método", ["Nebulizado (Turbo)", "Pulverizado", "Barras", "Mochila"])
                
                cf4, cf5, cf6, cf7 = st.columns(4)
                vol_ha = cf4.number_input("Vol. Lts/Ha", value=1200)
                marcha = cf5.number_input("Marcha Tractor", value=1)
                presion = cf6.number_input("Presión (Bar/Lb)", value=9.0)
                config_barras = cf7.text_input("Distribución Boquillas", placeholder="Ej: Izq: 2N-2M")
                
                datos_extra_json = {"Metodo": "Foliar"} # Para guardar en JSONB
                caseta_sel, ph_agua, ce_agua, tiempo_riego = None, None, None, None # Nulos para foliar

            else: # Es Fertirriego
                cr1, cr2, cr3 = st.columns(3)
                oper_sel = cr1.selectbox("Casetero / Operador de Riego", options=lista_opers)
                caseta_sel = cr2.selectbox("Caseta / Cabezal de Riego", ["Caseta 1", "Caseta 2", "Válvula Directa"])
                tipo_app = "Fertirriego"
                
                cr4, cr5, cr6, cr7 = st.columns(4)
                vol_ha = cr4.number_input("Vol. Agua (m3/Ha)", value=15.0)
                ph_agua = cr5.number_input("pH Esperado", value=5.5, step=0.1)
                ce_agua = cr6.number_input("Conductividad (CE)", value=1.2, step=0.1)
                tiempo_riego = cr7.number_input("Tiempo Inyección (Min)", value=45)
                
                maq_sel, marcha, presion, config_barras = None, 0, 0.0, None # Nulos para riego
                datos_extra_json = {"Caseta": caseta_sel, "pH": ph_agua, "CE": ce_agua, "Tiempo_Min": tiempo_riego, "Metodo": "Fertirriego"}

            st.markdown('<div class="seccion-titulo">3. Receta de Insumos (Cálculo Automático)</div>', unsafe_allow_html=True)
            opciones_fefo = {f"{r['Producto']} - Lote: {r['Codigo_Lote']} (Sald: {r['Stock_Actual']} {r.get('Unidad','')} - S/{r['Precio_Unitario_PEN']:.2f})": r for _, r in df_stock.iterrows()}
            
            editor_receta = st.data_editor(
                pd.DataFrame([{"Insumo": list(opciones_fefo.keys())[0], "Cantidad_Total": 0.0}]),
                num_rows="dynamic",
                column_config={
                    "Insumo": st.column_config.SelectboxColumn("Lote en Almacén", options=list(opciones_fefo.keys()), required=True),
                    "Cantidad_Total": st.column_config.NumberColumn("Cantidad (L/Kg)", min_value=0.0)
                }
            )

            if st.form_submit_button("📡 Enviar Orden Maestra a Almacén", type="primary"):
                if ha_dest <= 0:
                    st.error("⚠️ Las hectáreas deben ser mayores a 0 para calcular costos.")
                else:
                    costo_total_mezcla = 0
                    receta_final = []
                    
                    for _, row in editor_receta.iterrows():
                        info = opciones_fefo[row['Insumo']]
                        precio_unitario = float(info.get('Precio_Unitario_PEN', 0))
                        costo_insumo = row['Cantidad_Total'] * precio_unitario
                        costo_total_mezcla += costo_insumo
                        
                        receta_final.append({
                            "id": int(info['id']), 
                            "p": info['Producto'], 
                            "l": info['Codigo_Lote'], 
                            "c": row['Cantidad_Total'],
                            "precio_u": precio_unitario,
                            "costo_total": costo_insumo
                        })

                    # Empaquetamos los costos dentro del diccionario de datos extra que ya definimos
                    datos_extra_json["Costo_Estimado_Total"] = costo_total_mezcla
                    datos_extra_json["Costo_Por_Ha"] = (costo_total_mezcla/ha_dest) if ha_dest>0 else 0

                    maq_id = df_maq[df_maq['nombre'] == maq_sel]['id'].values[0] if maq_sel and not df_maq.empty else None
                    oper_id = df_pers[df_pers['nombre_completo'] == oper_sel]['id'].values[0] if oper_sel and not df_pers.empty else None

                    ot_data = {
                        "ID_Orden_Personalizado": f"OT-{datetime.now().strftime('%y%m%d-%H%M')}",
                        "Status": "En Preparación",
                        "Fecha_Programada": str(f_prog),
                        "Sector_Aplicacion": sec_dest,
                        "Objetivo": obj_app,
                        "Receta_Mezcla_Lotes": receta_final,
                        "Volumen_Hectarea": ha_dest,
                        "Marcha": int(marcha),
                        "Presion_Bar": float(presion),
                        "Tipo_Aplicacion": tipo_app,
                        "Color_Boquilla": config_barras,
                        "maquinaria_id": int(maq_id) if maq_id else None,
                        "operador_id": int(oper_id) if oper_id else None,
                        "Datos_Tecnicos": datos_extra_json # Aquí viaja si es fertirriego o foliar limpiamente
                    }
                    
                    supabase.table('Ordenes_de_Trabajo').insert(ot_data).execute()
                    st.success(f"✅ Orden enviada a Almacén. Inversión calculada: S/ {costo_total_mezcla:,.2f}")
                    st.cache_data.clear()
                    st.rerun()

# ==========================================
# TAB 2: ALMACÉN Y DESPACHO (La Firma Digital)
# ==========================================
with tab2:
    st.subheader("Órdenes por Despachar al Tractor")
    pendientes = df_ord[df_ord['Status'] == 'En Preparación'] if not df_ord.empty else pd.DataFrame()
    
    if pendientes.empty:
        st.info("No hay mezclas pendientes. El ingeniero no ha programado nada nuevo.")
    else:
        for _, ot in pendientes.iterrows():
            with st.expander(f"📦 {ot['ID_Orden_Personalizado']} | Sector: {ot['Sector_Aplicacion']} | 🎯 {ot['Objetivo']}"):
                col_d1, col_d2 = st.columns([3, 1])
                
                # Formateamos el dataframe del JSON para que se vea limpio
                df_receta = pd.DataFrame(ot['Receta_Mezcla_Lotes'])
                col_d1.dataframe(df_receta[['p', 'l', 'c']].rename(columns={'p':'Producto', 'l':'Lote', 'c':'Cantidad(L/Kg)'}), hide_index=True)
                
                with col_d2:
                    st.markdown("**Firma de Salida Logística**")
                    # AUDITORÍA: Almacenero obligatorio
                    resp_alm = st.text_input("Nombre Responsable Almacén*", key=f"resp_{ot['id']}", placeholder="Ej: Carlos M.")
                    
                    if st.button("✅ Confirmar y Descargar Stock", key=f"btn_{ot['id']}", type="primary"):
                        if resp_alm.strip():
                            batch_salidas = []
                            for insumo in ot['Receta_Mezcla_Lotes']:
                                batch_salidas.append({
                                    "Fecha_Aplicacion": ot['Fecha_Programada'],
                                    "Ingreso_ID": insumo['id'],
                                    "Cantidad_Usada": insumo['c'],
                                    "Sector_Destino": ot['Sector_Aplicacion'],
                                    "Objetivo_Tratamiento": ot['Objetivo'],
                                    "Responsable": resp_alm,
                                    "Labor": "Aplicación OT"
                                })
                            
                            # Transacción doble: Quita stock y cambia estado
                            supabase.table('Salidas').insert(batch_salidas).execute()
                            supabase.table('Ordenes_de_Trabajo').update({"Status": "Finalizada"}).eq('id', ot['id']).execute()
                            
                            st.success("Despacho exitoso. Kardex actualizado.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("⚠️ La firma del responsable es obligatoria por auditoría.")

# ==========================================
# TAB 3: HISTORIAL Y KPIs DE COSTOS (Finanzas)
# ==========================================
with tab3:
    st.subheader("Auditoría Financiera de Aplicaciones en Campo")
    finalizadas = df_ord[df_ord['Status'] == 'Finalizada'] if not df_ord.empty else pd.DataFrame()
    
    if finalizadas.empty:
        st.info("Aún no hay órdenes finalizadas para mostrar estadísticas.")
    else:
        # Recuperamos los costos desde el JSONB 'Datos_Tecnicos'
        costos_totales = []
        hectareas_totales = 0
        
        for _, ot in finalizadas.iterrows():
            if ot.get('Datos_Tecnicos'):
                costos_totales.append(ot['Datos_Tecnicos'].get('Costo_Estimado_Total', 0))
            hectareas_totales += float(ot.get('Volumen_Hectarea', 0))
            
        inversion_global = sum(costos_totales)
        promedio_global_ha = inversion_global / hectareas_totales if hectareas_totales > 0 else 0

        # Tarjetas de KPI
        k1, k2, k3 = st.columns(3)
        k1.metric("💰 Inversión Total en Químicos", f"S/ {inversion_global:,.2f}")
        k2.metric("📉 Costo Promedio General / Ha", f"S/ {promedio_global_ha:,.2f}")
        k3.metric("🚜 Hectáreas Totales Tratadas", f"{hectareas_totales:,.1f} Ha")

        st.divider()
        st.write("### Desglose por Orden de Trabajo")
        
        for _, ot in finalizadas.iterrows():
            dt = ot.get('Datos_Tecnicos', {})
            c_ot = dt.get('Costo_Estimado_Total', 0)
            c_ha = dt.get('Costo_Por_Ha', 0)
            ha_uso = ot.get('Volumen_Hectarea', 0)
            
            st.markdown(f"""
            <div style='background-color:#ffffff; padding:15px; border-radius:8px; border-left:4px solid #2ecc71; margin-bottom:10px; box-shadow:0 1px 3px rgba(0,0,0,0.1);'>
                <b>OT: {ot['ID_Orden_Personalizado']}</b> | 📍 Sector: {ot['Sector_Aplicacion']} ({ha_uso} Ha) <br>
                💵 <b>Costo Total: S/ {c_ot:,.2f}</b>  👉 (<i>S/ {c_ha:,.2f} por Hectárea</i>)
            </div>
            """, unsafe_allow_html=True)