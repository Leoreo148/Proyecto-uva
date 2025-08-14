import streamlit as st
import pandas as pd
import joblib

pwa_code = """
    <link rel="manifest" href="/manifest.json">
    <script>
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/sw.js').then(function(registration) {
                console.log('ServiceWorker registration successful with scope: ', registration.scope);
            }).catch(function(err) {
                console.log('ServiceWorker registration failed: ', err);
            });
        }
    </script>
"""
st.html(pwa_code)

# --- FUNCIONES AUXILIARES ---
def cargar_modelo():
    try:
        return joblib.load('modelo_oidio.joblib')
    # ... (el resto de tu código continúa sin cambios) ...
