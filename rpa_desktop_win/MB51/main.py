"""Entry point for MB51 bot (invocable from workflow).

Reads environment variables for parameters and executes `ejecutar_mb51`.
"""
import os
import sys
import time
from pathlib import Path
from datetime import datetime, date, timedelta

# Añadir path para importar core_shared y MB51 como paquete
pkg_root = Path(__file__).resolve().parents[1]
if str(pkg_root) not in sys.path:
    sys.path.insert(0, str(pkg_root))
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from MB51.logic.mb51_stock import ejecutar_mb51
from MB51.services.launcher import launch_sap
from MB51.services.sap_controller import SapController


def _to_date(s: str):
    # Expecting DDMMYYYY or ISO
    try:
        if '-' in s:
            return date.fromisoformat(s)
        return date(int(s[4:8]), int(s[2:4]), int(s[0:2]))
    except Exception:
        raise ValueError(f"Formato de fecha invalido: {s}. Use DDMMYYYY o YYYY-MM-DD")


def get_env_variable(name: str, required: bool = True) -> str:
    value = os.getenv(name)
    if required and not value:
        raise ValueError(f"Variable de entorno requerida no encontrada: {name}")
    return value


if __name__ == '__main__':
    print('[MB51 MAIN] Iniciando MB51 Bot...')
    try:
        sap_system = get_env_variable('SYSTEM')
        sap_client = get_env_variable('CLIENT')
        sap_user = get_env_variable('USER')
        sap_password = get_env_variable('PW')
        sap_lang = get_env_variable('LANG', required=False) or 'ES'

        centro = os.getenv('CENTRO', '4100')
        lgort_low = os.getenv('LGORT_LOW', '4147')
        lgort_high = os.getenv('LGORT_HIGH', '4195')
        variante = os.getenv('VARIANTE', 'BOTMB51')
        desde_raw = os.getenv('MB51_DESDE', '01012025')
        hasta_raw = os.getenv('MB51_HASTA')
        desde = _to_date(desde_raw)
        hasta = _to_date(hasta_raw) if hasta_raw else None

        print(f"[CONFIG] Sistema: {sap_system} Cliente: {sap_client} Usuario: {sap_user} Transaccion: MB51")
    except ValueError as e:
        print(f"[ERROR] {e}")
        sys.exit(1)

    # 1. Lanzar SAP
    try:
        print('[INFO] Lanzando SAP GUI...')
        launch_sap(system=sap_system, client=sap_client, user=sap_user, pw=sap_password, lang=sap_lang)
    except Exception as e:
        print(f"[ERROR] No se pudo lanzar SAP: {e}")
        sys.exit(1)

    # 2. Esperar y conectar
    controller = SapController()
    print('[INFO] Esperando que SAP inicie sesion...')

    max_wait = 90
    wait_interval = 5
    login_detectado = False

    for i in range(0, max_wait, wait_interval):
        if controller.wait_for_main_window(timeout=wait_interval):
            print(f"[SUCCESS] Sesion SAP detectada (despues de {i + wait_interval}s)")
            login_detectado = True
            break
        else:
            print(f"[WAIT] Esperando login SAP... ({i + wait_interval}s / {max_wait}s)")

    if not login_detectado:
        print('[ERROR] Timeout esperando sesion SAP')
        sys.exit(1)

    time.sleep(5)

    # Intentar conectar con reintentos
    max_retries = 5
    retry_delay = 5
    connected = False
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[INFO] Intento de conexion {attempt}/{max_retries}...")
            controller.connect()
            print('[SUCCESS] Conectado a SAP GUI Scripting')
            connected = True
            break
        except Exception as e:
            print(f"[WARN] Intento {attempt} fallido: {e}")
            if attempt < max_retries:
                time.sleep(retry_delay)

    if not connected:
        print('[ERROR] No se pudo conectar a SAP Scripting')
        sys.exit(1)

    # Ejecutar MB51
    try:
        filas = ejecutar_mb51(session=controller.session, centro=centro, lgort_low=lgort_low, lgort_high=lgort_high, variante=variante, desde=desde, hasta=hasta)
        print(f"[SUCCESS] MB51 completado. Filas: {filas}")
    except Exception as e:
        print(f"[ERROR] Error en proceso MB51: {e}")
        sys.exit(1)

    sys.exit(0)
