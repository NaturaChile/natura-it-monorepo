import subprocess
import time
import sys

def verificar_proceso_sap(timeout=60):
    """Verifica que SAP GUI esté corriendo"""
    inicio = time.time()
    while time.time() - inicio < timeout:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq saplogon.exe'],
            capture_output=True,
            text=True
        )
        if 'saplogon.exe' in result.stdout:
            return True
        time.sleep(2)
    return False

print("[INFO] Iniciando SAP GUI...")
subprocess.Popen(r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe")

print("[INFO] Esperando que SAP GUI se abra (máximo 60 segundos)...")
if verificar_proceso_sap(timeout=60):
    print("[SUCCESS] ✓ SAP GUI abierto correctamente y verificado en procesos.")
    time.sleep(5)  # Mantener abierto 5 segundos adicionales
    sys.exit(0)
else:
    print("[ERROR] ✗ SAP GUI no se abrió en 60 segundos.")
    sys.exit(1)
