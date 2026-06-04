import os
import glob

def analyze_files():
    modules = glob.glob(r'c:\Users\lenovo\Proyecto-uva\modulos\*.py')
    modules.append(r'c:\Users\lenovo\Proyecto-uva\app.py')
    
    for file_path in modules:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            
        name = os.path.basename(file_path)
        print(f"\n--- Analizando: {name} ---")
        
        # 1. Seguridad: Candado de autenticación
        if '"autenticado" not in st.session_state' not in content and 'app.py' not in name:
            print("🚨 PELIGRO: Falta candado de autenticación (Cualquiera puede entrar)")
            
        # 2. Seguridad: Rol hardcodeado (KeyError risk)
        if 'st.session_state["rol"]' in content:
            print("⚠️ RIESGO: Usa st.session_state[\"rol\"] directamente en lugar de .get('rol'). Riesgo de KeyError.")
            
        # 3. Eficiencia: Global Cache Clear
        if 'st.cache_data.clear()' in content:
            print("⚠️ EFICIENCIA: Usa st.cache_data.clear() global. Borra toda la caché en lugar de una función específica.")
            
        # 4. Bugs: pd.to_datetime sin coerce
        if 'pd.to_datetime' in content and 'errors=' not in content:
            print("⚠️ BUGS: Usa pd.to_datetime sin errors='coerce'. Si hay fechas inválidas, la app explotará.")
            
        # 5. UX: Layout
        if 'st.columns(3)' in content or 'st.columns(4)' in content or 'st.columns(5)' in content:
            print("💡 UX: Tiene layouts de 3 a 5 columnas. En móviles se verá aplastado. Sugerencia: usar st.columns en pantallas grandes o métricas apiladas en móviles.")

if __name__ == '__main__':
    analyze_files()
