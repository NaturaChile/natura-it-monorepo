import subprocess
import time
import sys
import psutil

def verificar_ventana_sap(timeout=60):
    """Verifica que SAP GUI este abierto y con ventana visible"""
    inicio = time.time()
    
    while time.time() - inicio < timeout:
        try:
            # 1. Buscar proceso saplogon.exe
            saplogon_process = None
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == 'saplogon.exe':
                    saplogon_process = proc
                    break
            
            if not saplogon_process:
                print("  [WAIT] Proceso saplogon.exe no encontrado aun...")
                time.sleep(2)
                continue
            
            # 2. Verificar que tiene ventana (no es background)
            try:
                # Usar tasklist para verificar que la ventana esta activa
                result = subprocess.run(
                    ['powershell', '-Command', 
                     '[System.Diagnostics.Process]::GetProcessesByName("saplogon") | measure | select -exp Count'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                count = int(result.stdout.strip())
                if count > 0:
                    print(f"  [OK] Proceso SAP encontrado: {count} instancia(s)")
                    return True
            except:
                pass
            
            print("  [WAIT] SAP abierto pero ventana no lista...")
            time.sleep(2)
            
        except Exception as e:
            print(f"  [WARN] Error durante verificacion: {str(e)}")
            time.sleep(2)
    
    return False

print("[INFO] Iniciando SAP GUI...")
try:
    proc = subprocess.Popen(r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe")
    print(f"[INFO] Proceso iniciado con PID: {proc.pid}")
except Exception as e:
    print(f"[ERROR] No se pudo iniciar SAP: {str(e)}")
    sys.exit(1)

print("[INFO] Esperando que SAP GUI se abra y este listo (maximo 60 segundos)...")
if verificar_ventana_sap(timeout=60):
    print("[SUCCESS] SAP GUI abierto correctamente y ventana verificada.")
    time.sleep(5)  # Mantener abierto 5 segundos adicionales
    sys.exit(0)
else:
    print("[ERROR] SAP GUI no se abrio correctamente en 60 segundos.")
    sys.exit(1)
