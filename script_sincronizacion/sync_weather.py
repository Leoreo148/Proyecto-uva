import os
import time
import requests
from datetime import datetime
import json

# =================================================================
# SCRIPT DE SINCRONIZACIÓN AUTOMÁTICA DE WEATHERLINK A SUPABASE
# =================================================================
# Este script está diseñado para ejecutarse automáticamente al 
# encender la laptop del ingeniero. Extrae los datos exportados
# por WeatherLink y los envía a la nube.
# =================================================================

SUPABASE_URL = "REEMPLAZA_CON_TU_URL_DE_SUPABASE"
SUPABASE_KEY = "REEMPLAZA_CON_TU_ANON_KEY_DE_SUPABASE"

# Ruta del archivo de texto que genera WeatherLink
# NOTA: En WeatherLink ir a File -> Export -> Configurar para exportar automático diario
RUTA_ARCHIVO_WEATHERLINK = r"C:\WeatherLink\Fundo Belessia\download.txt"

def procesar_archivo_weatherlink():
    if not os.path.exists(RUTA_ARCHIVO_WEATHERLINK):
        print(f"❌ No se encontró el archivo de WeatherLink en: {RUTA_ARCHIVO_WEATHERLINK}")
        print("Asegúrate de que WeatherLink esté configurado para exportar los datos automáticamente.")
        return []

    print(f"✅ Archivo encontrado: {RUTA_ARCHIVO_WEATHERLINK}")
    # NOTA: Aquí iría la lógica exacta de leer el TXT que genera WeatherLink 6.0.5.
    # Dado que el formato exacto varía por estación, este es un código demostrativo
    # que genera un dato simulado para que confirmes que la conexión sirve.
    # En producción leeríamos línea por línea: line.split() ...
    
    # Simulación de datos extraídos
    datos_extraidos = [
        {
            "fecha_hora": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "temp_out": 22.5,
            "hum_out": 55.0,
            "viento_vel": 10.0,
            "viento_dir": "NW",
            "lluvia_mm": 0.0,
            "radiacion_solar": 650.0
        }
    ]
    
    return datos_extraidos

def enviar_datos_a_supabase(datos):
    if not datos:
        return

    print("🚀 Enviando datos a Supabase...")
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        # "Prefer": "resolution=merge-duplicates" hace un UPSERT si el campo UNIQUE (fecha_hora) choca
        "Prefer": "resolution=merge-duplicates" 
    }
    
    url_tabla = f"{SUPABASE_URL}/rest/v1/Clima"
    
    for registro in datos:
        try:
            response = requests.post(url_tabla, headers=headers, json=registro)
            if response.status_code in [200, 201]:
                print(f"✅ Registro de {registro['fecha_hora']} guardado con éxito.")
            else:
                print(f"❌ Error al guardar registro: {response.text}")
        except Exception as e:
            print(f"⚠️ Error de conexión a internet: {e}")

if __name__ == "__main__":
    print("==================================================")
    print(" Sincronizador de WeatherLink - Fundo Belessia ")
    print("==================================================")
    print(f"Hora de ejecución: {datetime.now()}")
    
    # 1. Leer los datos locales de WeatherLink
    datos = procesar_archivo_weatherlink()
    
    # 2. Enviarlos a internet
    enviar_datos_a_supabase(datos)
    
    print("\nProceso terminado. La ventana se cerrará en 10 segundos...")
    time.sleep(10)
