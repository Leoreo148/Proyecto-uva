import streamlit as st
import pandas as pd
from datetime import datetime
import json
from io import BytesIO
import plotly.express as px
import numpy as np

# --- LIBRERÍAS PARA LA CONEXIÓN A SUPABASE ---
from supabase import create_client, Client
from streamlit_local_storage import LocalStorage

# --- Configuración de la Página ---
st.set_page_config(page_title="Diámetro de Baya", page_icon="🍇", layout="wide")
st.title("🍇 Medición de Diámetro de Baya")
st.write("Registre el diámetro (mm) y visualice los promedios por racimo y planta en tiempo real.")

# --- Inicialización y Constantes ---
localS = LocalStorage()
LOCAL_STORAGE_KEY = 'diametro_baya_offline_v3'
columnas_racimo1 = ["Racimo 1 - Superior", "Racimo 1 - Medio", "Racimo 1 - Inferior"]
columnas_racimo2 = ["Racimo 2 - Superior", "Racimo 2 - Medio", "Racimo 2 - Inferior"]
columnas_medicion = columnas_racimo1 + columnas_racimo2
# --- CORRECCIÓN: Nombres de columna para la base de datos ---
columnas_db = [c.replace(' ', '_').replace(' - ', '_') for c in columnas_medicion]
mapeo_columnas = dict(zip(columnas_medicion, columnas_db))

# --- Conexión a Supabase ---
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

# --- Funciones de Datos ---
@st.cache_data(ttl=60)
def cargar_diametro_supabase():
    if supabase:
        try:
            response = supabase.table('Diametro_Baya').select("*").execute()
            df = pd.DataFrame(response.data)
            if not df.empty:
                df['Fecha'] = pd.to_datetime(df['Fecha'])
            return df
        except Exception as e:
            st.error(f"Error al cargar el historial de Supabase: {e}")
    return pd.DataFrame()

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Reporte_Diametro')
    return output.getvalue()

def calcular_tasa_crecimiento(df):
    if df.shape[0] < 2 or not all(c in df.columns for c in columnas_db):
        return pd.DataFrame()

    df['Diametro_Prom_Planta'] = df[columnas_db].mean(axis=1)
    tasas = []
    for sector in df['Sector'].unique():
        df_sector = df[df['Sector'] == sector].copy()
        promedio_por_fecha = df_sector.groupby('Fecha')['Diametro_Prom_Planta'].mean()
        if len(promedio_por_fecha) >= 2:
            ultimas_dos = promedio_por_fecha.sort_index().tail(2)
            (p_penultimo, p_ultimo), (f_penultima, f_ultima) = ultimas_dos.values, ultimas_dos.index
            dias = (f_ultima - f_penultima).days
            if dias > 0:
                tasa = (p_ultimo - p_penultimo) / dias
                tasas.append({
                    "Sector": sector, "Tasa (mm/día)": tasa, "Desde": f_penultima.strftime('%d/%m/%Y'),
                    "Hasta": f_ultima.strftime('%d/%m/%Y'), "Días Transcurridos": dias
                })
    return pd.DataFrame(tasas)

# --- Interfaz de Registro ---
with st.expander("➕ Registrar Nueva Medición", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        sectores_baya = ['J1', 'J2', 'R1', 'R2', 'W1', 'W2', 'W3', 'K1', 'K2','K3']
        sector_seleccionado = st.selectbox('Seleccione el Sector de Medición:', options=sectores_baya)
    with col2:
        fecha_medicion = st.date_input("Fecha de Medición", datetime.now())
    
    st.subheader("Tabla de Ingreso de Diámetros (mm)")
    
    # Creamos la plantilla editable en cada ejecución
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(None, index=plant_numbers, columns=columnas_medicion)
    
    df_editada = st.data_editor(df_plantilla, use_container_width=True, key="editor_baya")
    
    # --- LÓGICA DE PROMEDIOS (SIMPLIFICADA) ---
    st.subheader("Tabla de Ingreso de Diámetros (mm)")
    
    # 1. EL TRUCO DE LOS CEROS: Usamos None para no arruinar el promedio
    plant_numbers = [f"Planta {i+1}" for i in range(25)]
    df_plantilla = pd.DataFrame(None, index=plant_numbers, columns=columnas_medicion)
    
    # 2. EL CANDADO ANTI-ERRORES: Restringimos de 5mm a 40mm
    configuracion_columnas = {
        col: st.column_config.NumberColumn(
            col, 
            min_value=5.0,   
            max_value=40.0,  
            format="%.2f"
        )
        for col in columnas_medicion
    }

    # Creamos la tabla editable con los candados puestos
    df_editada = st.data_editor(
        df_plantilla, 
        use_container_width=True, 
        key="editor_baya",
        column_config=configuracion_columnas
    )
    
    # --- 3. LÓGICA DE PROMEDIOS Y UNIFORMIDAD (CV%) ---
    st.subheader("📊 Resultados Analíticos en Tiempo Real")
    df_promedios = df_editada.copy()
    df_promedios['Promedio Racimo 1'] = df_promedios[columnas_racimo1].mean(axis=1)
    df_promedios['Promedio Racimo 2'] = df_promedios[columnas_racimo2].mean(axis=1)
    df_promedios['Promedio Final Planta'] = df_promedios[columnas_medicion].mean(axis=1)
    
    # Cálculo estadístico global de la muestra actual (La magia de Numpy)
    valores_planos = df_editada.values.flatten()
    valores_validos = [v for v in valores_planos if pd.notnull(v) and v > 0]

    if valores_validos:
        promedio_global = np.mean(valores_validos)
        desviacion_estandar = np.std(valores_validos)
        cv_porcentaje = (desviacion_estandar / promedio_global) * 100

        c1, c2, c3 = st.columns(3)
        c1.metric("📏 Promedio del Lote", f"{promedio_global:.2f} mm")
        # Si el CV% es menor a 10, es excelente calidad de exportación
        c2.metric("🎯 Uniformidad (CV)", f"{cv_porcentaje:.1f} %", 
                  delta="Óptimo" if cv_porcentaje < 10 else "Desuniforme", 
                  delta_color="inverse")
        c3.metric("🍇 Total Bayas Medidas", f"{len(valores_validos)}")
    else:
        st.info("Ingresa medidas válidas en la tabla para ver el análisis de uniformidad.")

    # Mostramos la tabla de promedios individuales por planta
    st.dataframe(df_promedios[['Promedio Racimo 1', 'Promedio Racimo 2', 'Promedio Final Planta']].style.format("{:.2f}", na_rep="-"), use_container_width=True)

    if st.button("💾 Guardar Medición en Dispositivo"):
        df_para_guardar = df_editada.copy()
        df_para_guardar['Sector'] = sector_seleccionado
        df_para_guardar['Fecha'] = fecha_medicion.strftime("%Y-%m-%d")
        
        df_para_guardar = df_para_guardar.reset_index().rename(columns={'index': 'Planta'})
        df_para_guardar = df_para_guardar.rename(columns=mapeo_columnas)
        
        registros_json = df_para_guardar.to_dict('records')
        
        registros_locales_str = localS.getItem(LOCAL_STORAGE_KEY)
        registros_locales = json.loads(registros_locales_str) if registros_locales_str else []
        registros_locales.extend(registros_json)
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps(registros_locales))
        st.success(f"¡Medición guardada! Hay {len(registros_locales)} registros de plantas pendientes.")
        st.rerun()

# --- Sección de Sincronización ---
st.divider()
st.subheader("📡 Sincronización con la Base de Datos")
registros_pendientes_str = localS.getItem(LOCAL_STORAGE_KEY)
registros_pendientes = json.loads(registros_pendientes_str) if registros_pendientes_str else []

# --- NUEVO: Botón para limpiar datos locales corruptos ---
if registros_pendientes:
    st.error("Hay datos guardados en el dispositivo. Si la sincronización falla, límpielos con el siguiente botón.")
    if st.button("🧹 Limpiar Almacenamiento Local (Solucionar Errores)"):
        localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
        st.toast("Almacenamiento local limpiado. Recargando...")
        st.rerun()

if registros_pendientes:
    st.warning(f"Hay **{len(registros_pendientes)}** mediciones de plantas guardadas localmente pendientes de sincronizar.")
    if st.button("Sincronizar Ahora con Supabase"):
        if supabase:
            with st.spinner("Sincronizando..."):
                try:
                    supabase.table('Diametro_Baya').insert(registros_pendientes).execute()
                    localS.setItem(LOCAL_STORAGE_KEY, json.dumps([]))
                    st.success("¡Sincronización completada!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al guardar en Supabase: {e}. Sus datos locales están a salvo.")
        else:
            st.error("No se pudo sincronizar. La conexión con Supabase no está disponible.")
else:
    st.info("✅ Almacenamiento local limpio y listo para registrar nuevas mediciones.")

st.divider()

# --- HISTORIAL Y ANÁLISIS ---
st.header("📊 Historial y Análisis de Tendencia")
df_historial = cargar_diametro_supabase()

if df_historial is None or df_historial.empty:
    st.info("Aún no hay datos históricos para mostrar.")
else:
    st.subheader("🚀 Tasa de Crecimiento Actual (mm/día)")
    df_tasas = calcular_tasa_crecimiento(df_historial.copy())
    if not df_tasas.empty:
        st.write("Crecimiento promedio diario calculado entre las dos últimas mediciones de cada sector.")
        st.dataframe(
            df_tasas,
            column_config={"Tasa (mm/día)": st.column_config.NumberColumn(format="%.2f")},
            use_container_width=True, hide_index=True
        )
    else:
        st.info("Se necesitan al menos dos mediciones en un sector para calcular la tasa de crecimiento.")
    
    st.divider()

    st.subheader("📈 Curva y Tabla de Crecimiento")
    
    todos_los_sectores = sorted(df_historial['Sector'].astype(str).unique())
    sectores_a_graficar = st.multiselect("Sectores a comparar:", options=todos_los_sectores, default=todos_los_sectores)
    
    if sectores_a_graficar:
        df_filtrado = df_historial[df_historial['Sector'].isin(sectores_a_graficar)]
        df_melted = df_filtrado.melt(id_vars=['Fecha', 'Sector'], value_vars=columnas_db, var_name='Posicion', value_name='Diametro')
        df_melted = df_melted[df_melted['Diametro'] > 0]
        df_tendencia = df_melted.groupby(['Fecha', 'Sector'])['Diametro'].mean().reset_index()
        
        if not df_tendencia.empty:
            st.write("Tabla de Diámetro Promedio (mm):")
            df_pivot = df_tendencia.pivot_table(index='Fecha', columns='Sector', values='Diametro').sort_index(ascending=False)
            st.dataframe(df_pivot.style.format("{:.2f}", na_rep="-"), use_container_width=True)

            st.write("Gráfico de Tendencia:")
            fig = px.line(df_tendencia, x='Fecha', y='Diametro', color='Sector', title='Evolución del Diámetro Promedio', markers=True)
            st.plotly_chart(fig, use_container_width=True)
