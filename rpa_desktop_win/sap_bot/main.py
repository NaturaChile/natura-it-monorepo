"""SAP Bot - Automatizacion profesional con manejo de errores."""
import os
import sys
import time
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sap_bot.services.launcher import launch_sap
from sap_bot.services.sap_controller import SapController
from sap_bot.logic.mb52_stock import ejecutar_mb52


def get_env_variable(name: str, required: bool = True) -> str:
    """Obtiene variable de entorno con validacion."""
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Variable de entorno requerida no encontrada: {name}")
    return value


def check_statusbar(controller: SapController) -> dict:
    """Revisa la barra de estado de SAP para detectar errores o mensajes."""
    try:
        statusbar_text = controller.session.findById("wnd[0]/sbar/pane[0]").text
        message_type = controller.session.findById("wnd[0]/sbar").MessageType
        
        return {
            "text": statusbar_text,
            "type": message_type,
            "is_error": message_type in ["E", "A"],  # E=Error, A=Abort
            "is_warning": message_type == "W",
            "is_success": message_type == "S"
        }
    except Exception as e:
        return {
            "text": "",
            "type": "unknown",
            "is_error": False,
            "is_warning": False,
            "is_success": False,
            "exception": str(e)
        }


def verificar_error_login() -> str:
    """Verifica si hay un error de login en SAP (contrasena incorrecta, usuario bloqueado, etc.)"""
    try:
        import win32com.client
        sap_gui = win32com.client.GetObject("SAPGUI")
        app = sap_gui.GetScriptingEngine
        
        # Verificar si hay conexiones
        if app.Children.Count == 0:
            return None  # No hay conexion aun, sigue esperando
        
        conn = app.Children(0)
        
        # Verificar si hay sesiones
        if conn.Children.Count == 0:
            return None  # No hay sesion aun
        
        session = conn.Children(0)
        
        # Intentar leer la barra de estado de la pantalla de login
        try:
            statusbar = session.findById("wnd[0]/sbar")
            mensaje = statusbar.Text
            tipo = statusbar.MessageType
            
            # Mensajes comunes de error de login
            errores_login = [
                "password",
                "contrasena",
                "clave",
                "incorrecta",
                "invalid",
                "bloqueado",
                "locked",
                "expired",
                "expirado",
                "caducado",
                "no autorizado",
                "unauthorized",
                "no existe",
                "does not exist"
            ]
            
            mensaje_lower = mensaje.lower()
            if tipo in ["E", "A"] and any(err in mensaje_lower for err in errores_login):
                return mensaje
                
        except Exception:
            pass
        
        return None
        
    except Exception:
        return None  # SAP no esta listo, sigue esperando


def main():
    """Punto de entrada principal del bot."""
    print("[INFO] Iniciando SAP Bot...")
    
    # 1. Cargar configuracion desde environment
    try:
        sap_system = get_env_variable("SYSTEM")
        sap_client = get_env_variable("CLIENT")
        sap_user = get_env_variable("USER")
        sap_password = get_env_variable("PW")
        sap_lang = get_env_variable("LANG", required=False) or "ES"
        transaction = get_env_variable("TRANSACTION", required=False) or "MB51"
        
        print(f"[CONFIG] Sistema: {sap_system}")
        print(f"[CONFIG] Cliente: {sap_client}")
        print(f"[CONFIG] Usuario: {sap_user}")
        print(f"[CONFIG] Idioma: {sap_lang}")
        print(f"[CONFIG] Transaccion: {transaction}")
        
    except ValueError as e:
        print(f"[ERROR] {str(e)}")
        sys.exit(1)
    
    # 2. Verificar que no haya otra sesion SAP activa
    print("[INFO] Verificando si hay otra sesion SAP activa...")
    try:
        import subprocess
        # Buscar ventana con titulo "SAP Easy Access" usando PowerShell
        result = subprocess.run(
            ['powershell', '-Command', 
             'Get-Process | Where-Object {$_.MainWindowTitle -like "*SAP Easy Access*"} | Select-Object -First 1 | Measure-Object | Select-Object -ExpandProperty Count'],
            capture_output=True,
            text=True,
            timeout=10
        )
        count = int(result.stdout.strip()) if result.stdout.strip() else 0
        
        if count > 0:
            print("[ERROR] Hay otro bot funcionando en SAP")
            print("[ERROR] Se detecto una ventana 'SAP Easy Access' abierta")
            print("[ERROR] Cierre la sesion SAP existente antes de ejecutar este proceso")
            sys.exit(1)
        else:
            print("[OK] No hay sesiones SAP activas")
    except Exception as e:
        print(f"[WARN] No se pudo verificar sesiones SAP: {str(e)}")
        print("[INFO] Continuando de todas formas...")
    
    # 3. Lanzar SAP
    try:
        print("[INFO] Lanzando SAP GUI...")
        launch_sap(
            system=sap_system,
            client=sap_client,
            user=sap_user,
            pw=sap_password,
            lang=sap_lang
        )
    except Exception as e:
        print(f"[ERROR] No se pudo lanzar SAP: {str(e)}")
        sys.exit(1)
    
    # 4. Esperar y conectar
    controller = SapController()
    print("[INFO] Esperando que SAP inicie sesion (ventana 'SAP')...")
    
    # Esperar mas tiempo para que SAP se abra completamente y haga login
    max_wait = 90  # 90 segundos (login puede tardar)
    wait_interval = 5
    login_detectado = False
    
    for i in range(0, max_wait, wait_interval):
        if controller.wait_for_main_window(timeout=wait_interval):
            print(f"[SUCCESS] Sesion SAP detectada (despues de {i + wait_interval}s)")
            login_detectado = True
            break
        else:
            # Verificar si hay error de login (contrasena incorrecta, usuario bloqueado, etc.)
            error_login = verificar_error_login()
            if error_login:
                print(f"[ERROR] Error de autenticacion SAP: {error_login}")
                print("[ERROR] Posibles causas:")
                print("  - Contrasena incorrecta o expirada")
                print("  - Usuario bloqueado")
                print("  - Usuario sin permisos en este sistema/cliente")
                sys.exit(1)
            print(f"[WAIT] Esperando login SAP... ({i + wait_interval}s / {max_wait}s)")
    
    if not login_detectado:
        print("[ERROR] Timeout esperando sesion SAP")
        print("[ERROR] El login no se completo en 90 segundos")
        print("[ERROR] Verifica credenciales y conectividad al servidor SAP")
        sys.exit(1)
    
    # Esperar adicional para que el login complete
    print("[INFO] Esperando que el login complete...")
    time.sleep(10)
    
    # Intentar conectar con reintentos
    max_retries = 5
    retry_delay = 5
    connected = False
    
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] Intento de conexion {attempt}/{max_retries}...")
            controller.connect()
            print("[SUCCESS] Conectado a SAP GUI Scripting")
            connected = True
            break
        except Exception as e:
            print(f"[WARN] Intento {attempt} fallido: {str(e)}")
            if attempt < max_retries:
                print(f"[INFO] Esperando {retry_delay}s antes del siguiente intento...")
                time.sleep(retry_delay)
    
    if not connected:
        print("[ERROR] No se pudo conectar a SAP Scripting despues de todos los intentos")
        print("[INFO] Verifica que:")
        print("  1. SAP GUI este instalado")
        print("  2. SAP Scripting este habilitado (RZ11 -> sapgui/user_scripting)")
        print("  3. La sesion tenga permisos de UI (no session 0)")
        print("  4. Las credenciales sean correctas")
        sys.exit(1)
    
    # 4. Escribir transaccion
    try:
        print(f"[INFO] Ejecutando transaccion: {transaction}")
        controller.write_transaction(transaction)
        time.sleep(2)  # Esperar a que cargue la transaccion
        
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar transaccion: {str(e)}")
        sys.exit(1)
    
    # 5. Revisar barra de estado despues de entrar a la transaccion
    print("[INFO] Revisando barra de estado...")
    status = check_statusbar(controller)
    
    if "exception" in status:
        print(f"[WARN] No se pudo leer barra de estado: {status['exception']}")
    else:
        print(f"[STATUS] Tipo: {status['type']}")
        print(f"[STATUS] Mensaje: {status['text']}")
        
        if status['is_error']:
            print("[ERROR] Se detecto un error en SAP")
            sys.exit(1)
    
    # 6. Ejecutar logica especifica de la transaccion
    if transaction.upper() == "MB52":
        try:
            # Obtener parametros opcionales desde environment
            centro = os.getenv("CENTRO", "4100")
            almacen = os.getenv("ALMACEN", "4161")
            variante = os.getenv("VARIANTE", "BOTMB52")
            ruta_destino = os.getenv("RUTA_DESTINO", r"Y:\Publico\RPA\Retail\Stock - Base Tiendas")
            
            archivo_generado = ejecutar_mb52(
                session=controller.session,
                centro=centro,
                almacen=almacen,
                variante=variante,
                ruta_destino=ruta_destino
            )
            
            print(f"[SUCCESS] Proceso MB52 completado. Archivo: {archivo_generado}")
            
        except Exception as e:
            print(f"[ERROR] Error en proceso MB52: {str(e)}")
            # Leer barra de estado para mostrar mensaje de error de SAP
            print("[INFO] Leyendo barra de estado de SAP...")
            status = check_statusbar(controller)
            if "exception" not in status:
                print(f"[SAP STATUS] Tipo: {status['type']}")
                print(f"[SAP STATUS] Mensaje: {status['text']}")
            sys.exit(1)
    else:
        print(f"[INFO] Transaccion {transaction} ejecutada (sin logica adicional)")
    
    # 7. Revisar barra de estado final
    print("[INFO] Revisando barra de estado final...")
    status = check_statusbar(controller)
    
    if "exception" in status:
        print(f"[WARN] No se pudo leer barra de estado: {status['exception']}")
    else:
        print(f"[STATUS] Tipo: {status['type']}")
        print(f"[STATUS] Mensaje: {status['text']}")
        
        if status['is_error']:
            print("[ERROR] Se detecto un error en SAP")
            sys.exit(1)
        elif status['is_warning']:
            print("[WARN] Se detecto una advertencia en SAP")
        elif status['is_success']:
            print("[SUCCESS] Operacion exitosa")
        else:
            print("[INFO] Sin mensajes especiales")
    
    print("[SUCCESS] Bot ejecutado correctamente")
    time.sleep(3)  # Mantener ventana abierta
    sys.exit(0)


if __name__ == "__main__":
    main()
