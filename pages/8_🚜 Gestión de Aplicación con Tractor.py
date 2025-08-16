import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, time
from io import BytesIO
import openpyxl

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Gestión de Aplicación", page_icon="🚜", layout="wide")
st.title("🚜 Cartilla de Aplicación con Tractor")
st.write("El operario completa la cartilla digital con los detalles de la aplicación para marcar la orden como finalizada.")

# --- NOMBRES DE ARCHIVOS ---
ORDENES_FILE = 'Ordenes_de_Trabajo.xlsx'

# --- FUNCIONES ---
def cargar_ordenes():
    if os.path.exists(ORDENES_FILE):
        return pd.read_excel(ORDENES_FILE)
    cols = ['ID_Orden', 'Status', 'Fecha_Programada', 'Sector_Aplicacion', 'Objetivo', 'Receta_Mezcla_Lotes']
    return pd.DataFrame(columns=cols)

def guardar_ordenes(df):
    df.to_excel(ORDENES_FILE, index=False, engine='openpyxl')
    return True

def to_excel_detailed(tarea_row):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Hoja 1: Resumen
        resumen_data = {k: [v] for k, v in tarea_row.items() if not isinstance(v, (list, dict, str)) or len(str(v)) < 200}
        pd.DataFrame(resumen_data).to_excel(writer, index=False, sheet_name='Resumen_Orden')
        
        # Hoja 2: Receta
        if 'Receta_Mezcla_Lotes' in tarea_row and pd.notna(tarea_row['Receta_Mezcla_Lotes']):
            receta = json.loads(tarea_row['Receta_Mezcla_Lotes'])
            pd.DataFrame(receta).to_excel(writer, index=False, sheet_name='Receta_Detallada')

        # Hoja 3: Cartilla de Aplicación
        if 'Detalle_Aplicacion' in tarea_row and pd.notna(tarea_row['Detalle_Aplicacion']):
            detalle = json.loads(tarea_row['Detalle_Aplicacion'])
            pd.DataFrame([detalle]).T.to_excel(writer, sheet_name='Cartilla_Aplicacion')
            
    return output.getvalue()

# --- CARGA DE DATOS ---
df_ordenes = cargar_ordenes()

# --- SECCIÓN 1: TAREAS LISTAS PARA APLICAR ---
st.subheader("✅ Tareas Listas para Aplicar")
st.write("Aquí aparecen las órdenes que ya tienen la mezcla preparada.")

tareas_para_aplicar = df_ordenes[df_ordenes['Status'] == 'Lista para Aplicar'] if 'Status' in df_ordenes.columns else pd.DataFrame()

if not tareas_para_aplicar.empty:
    for index, tarea in tareas_para_aplicar.iterrows():
        expander_title = f"**Orden ID:** `{tarea['ID_Orden']}` | **Sector:** {tarea['Sector_Aplicacion']} | **Fecha:** {pd.to_datetime(tarea['Fecha_Programada']).strftime('%d/%m/%Y')}"
        with st.expander(expander_title):
            
            st.write("**Receta de la Mezcla (Lotes a Usar):**")
            receta = json.loads(tarea['Receta_Mezcla_Lotes'])
            st.dataframe(pd.DataFrame(receta), use_container_width=True)
            
            with st.form(key=f"form_tractor_{tarea['ID_Orden']}"):
                st.subheader("Cartilla de Aplicación")
                
                # --- DATOS DE LA CARTILLA ---
                st.markdown("##### Método de Aplicación")
                col_tipo, col_vol = st.columns(2)
                with col_tipo:
                    tipo_aplicacion = st.radio("Tipo de Aplicación", ["Nebulizador (Turbo)", "Barras", "Pistolas/Drench"])
                with col_vol:
                    volumen_total = st.number_input("Volumen de Agua Total (L)", value=2200)
                    volumen_ha = st.number_input("Volumen por Hectárea", value=1200)

                st.markdown("##### Maquinaria")
                col_maq1, col_maq2, col_maq3 = st.columns(3)
