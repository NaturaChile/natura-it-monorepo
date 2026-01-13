import sys
import os
from datetime import datetime

# Truco para que encuentre 'core_shared' aunque estemos en una subcarpeta
# Agregamos la raíz del proyecto al Path de Python
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, ".."))
sys.path.append(project_root)

try:
    print("--- INICIANDO DIAGNÓSTICO RPA NATURA ---")
    print(f"Fecha: {datetime.now()}")
    print(f"Directorio actual: {os.getcwd()}")
    print(f"Python: {sys.executable}")

    # 1. Probar Importación de Core Shared
    from core_shared.security.vault import Vault
    print("Core Shared importado correctamente.")

    # 2. Probar Acceso a Secretos 
    # Intenta leer una variable de entorno común, ej: PATH
    path_val = os.getenv("PATH")
    if path_val:
        print("Lectura de Variables de Entorno: OK")
    else:
        print("Advertencia: No se leyeron variables de entorno.")

    # 3. Probar Librería Externa (Pandas/Requests)
    import requests
    print(f"Librerías externas cargadas (Requests v{requests.__version__})")

    print("\n¡EL ENTORNO ESTÁ SANO Y LISTO PARA OPERAR!")

except Exception as e:
    print(f"\nERROR CRÍTICO: {e}")
    # En un bot real, aquí iría un log o alerta