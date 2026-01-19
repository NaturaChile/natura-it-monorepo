"""SAP Bot - Automatizacion profesional con manejo de errores."""
import os
import sys
import time
from pathlib import Path

# Agregar el directorio padre al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sap_bot.services.launcher import launch_sap
from sap_bot.services.sap_controller import SapController


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
    
    # 2. Lanzar SAP
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
    
    # 3. Esperar y conectar
    controller = SapController()
    print("[INFO] Esperando ventana principal de SAP...")
    
    if not controller.wait_for_main_window(timeout=30):
        print("[WARN] No se detecto ventana SAP Easy Access, intentando conectar...")
        time.sleep(5)
    else:
        print("[SUCCESS] Ventana SAP Easy Access detectada")
    
    try:
        controller.connect()
        print("[SUCCESS] Conectado a SAP GUI Scripting")
    except Exception as e:
        print(f"[ERROR] No se pudo conectar a SAP Scripting: {str(e)}")
        sys.exit(1)
    
    # 4. Escribir transaccion
    try:
        print(f"[INFO] Ejecutando transaccion: {transaction}")
        controller.write_transaction(transaction)
        time.sleep(2)  # Esperar a que cargue la transaccion
        
    except Exception as e:
        print(f"[ERROR] No se pudo ejecutar transaccion: {str(e)}")
        sys.exit(1)
    
    # 5. Revisar barra de estado
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
