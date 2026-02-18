import win32com.client
import subprocess
import time
import sys
import os
from datetime import datetime

# --- CONFIGURACIÓN ---
RUTA_SAP_LOGON = r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe"
SAP_CONEXION = "1.02 - PRD - Produção/Producción"
RUTA_CARPETA = r"Z:\Publico\RPA\Plan Chile\zmm0164"

# Credenciales BOTSCL
CLIENTE = "210"
USUARIO = "BOTSCL"
PASSWORD = "La.Nueva.Clave.2026"
IDIOMA = "ES"

def connect_to_sap():
    """Conexión robusta a 1.02"""
    try:
        SapGuiAuto = win32com.client.GetObject("SAPGUI")
        if not type(SapGuiAuto) == win32com.client.CDispatch:
            raise Exception("Objeto no válido")
    except:
        subprocess.Popen(RUTA_SAP_LOGON)
        time.sleep(5)
        for _ in range(30):
            try:
                SapGuiAuto = win32com.client.GetObject("SAPGUI")
                break
            except:
                time.sleep(1)
        else:
            sys.exit(1)

    application = SapGuiAuto.GetScriptingEngine
    
    connection = None
    for i in range(application.Connections.Count):
        if "1.02" in application.Children(int(i)).Description:
            connection = application.Children(int(i))
            break
            
    if connection is None:
        try:
            connection = application.OpenConnection(SAP_CONEXION, True)
        except:
            print(f"[ERROR] Error: No se encontró la conexión '{SAP_CONEXION}'.")
            sys.exit(1)
        
    session = connection.Children(0)
    return session

# --- INICIO ROBOT ---

try:
    print(f"[BOT] Conectando como {USUARIO}...")
    session = connect_to_sap()
    
    if session.findById("wnd[0]/sbar").text != "":
        session.findById("wnd[0]").sendVKey(0)

    # 1. LOGIN
    print("Verificando sesión...")
    try:
        session.findById("wnd[0]/usr/txtRSYST-MANDT").text = CLIENTE
        session.findById("wnd[0]/usr/txtRSYST-BNAME").text = USUARIO
        session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = PASSWORD
        session.findById("wnd[0]/usr/txtRSYST-LANGU").text = IDIOMA
        session.findById("wnd[0]").sendVKey(0)
    except:
        pass

    # 2. TRANSACCIÓN
    print("Entrando a ZMM0164...")
    session.findById("wnd[0]/tbar[0]/okcd").text = "/nzmm0164"
    session.findById("wnd[0]").sendVKey(0)
    
    # 3. DATOS
    session.findById("wnd[0]").maximize()
    session.findById("wnd[0]/usr/ctxtSP$00006-LOW").text = "4100"
    
    print("Ejecutando (F8)...")
    session.findById("wnd[0]/tbar[1]/btn[8]").press()
    
    print("Esperando datos...")
    time.sleep(2) 
    
    # 4. EXPORTACIÓN
    print("Botones 30 y 45...")
    session.findById("wnd[0]/tbar[1]/btn[30]").press()
    session.findById("wnd[0]/tbar[1]/btn[45]").press()
    
    # FORMATO
    session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]").select()
    session.findById("wnd[1]/tbar[0]/btn[0]").press()
    
    # 5. GUARDAR
    print("[WAIT] Esperando ventana de guardar...")
    for i in range(20):
        try:
            if session.findById("wnd[1]/usr/ctxtDY_PATH").text != "ERROR":
                break
        except:
            time.sleep(1)

    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    nombre_archivo = f"zmm0164-{fecha_hoy}.XLS"
    
    # Escribir RUTA
    print(f"[WRITE] Escribiendo Ruta: {RUTA_CARPETA}")
    session.findById("wnd[1]/usr/ctxtDY_PATH").text = RUTA_CARPETA
    session.findById("wnd[1]/usr/ctxtDY_PATH").setFocus()
    session.findById("wnd[1]/usr/ctxtDY_PATH").caretPosition = len(RUTA_CARPETA)
    
    # Escribir NOMBRE
    print(f"[WRITE] Escribiendo Nombre: {nombre_archivo}")
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = nombre_archivo
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").setFocus()
    session.findById("wnd[1]/usr/ctxtDY_FILENAME").caretPosition = len(nombre_archivo)
    
    time.sleep(0.5)
    
    # GENERAR
    print("[CLICK] Generando archivo...")
    try:
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
    except:
        pass

    # CONFIRMAR REEMPLAZO
    try:
        time.sleep(1)
        if session.Children.Count > 1:
            if session.findById("wnd[2]").text != "": 
                print("[WARN] Sobrescribiendo...")
                session.findById("wnd[2]/tbar[0]/btn[11]").press()
    except:
        pass

    print("[OK] Archivo guardado/actualizado.")

    # 6. CERRAR SESIÓN SAP (/nex)
    print("[DISCONNECT] Desconectando del servidor...")
    try:
        session.findById("wnd[0]/tbar[0]/okcd").text = "/nex"
        session.findById("wnd[0]").sendVKey(0)
    except:
        pass
    
    # 7. MATAR PROCESO SAP LOGON (Cierra la ventana 760)
    print("[STOP] Cerrando SAP Logon completamente...")
    time.sleep(2) # Esperamos a que el comando /nex termine
    
    # TASKKILL: Fuerza el cierre de saplogon.exe
    # /F = Forzar, /IM = Nombre de imagen
    os.system("taskkill /F /IM saplogon.exe")

    print("[DONE] Fin del proceso.")

except Exception as e:
    print(f"[ERROR] Error Crítico: {e}")
    # En caso de error, también intentamos cerrar SAP para no dejarlo colgado
    try:
        os.system("taskkill /F /IM saplogon.exe")
    except:
        pass