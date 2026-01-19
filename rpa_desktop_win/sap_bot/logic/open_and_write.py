import time

from sap_bot_simple.services.launcher import launch_sap
from sap_bot_simple.services.sap_controller import SapController


def open_and_write(system: str, client: str, user: str, pw: str, lang: str, text: str, exe_path: str = None, wait: int = 10):
    """Orquesta los pasos: abrir SAP, esperar ventana principal, conectar y escribir."""
    launch_sap(system=system, client=client, user=user, pw=pw, lang=lang, exe_path=exe_path)

    controller = SapController()

    if not controller.wait_for_main_window(timeout=wait):
        # fallback: esperar de forma pasiva
        time.sleep(wait)

    controller.connect()
    controller.write_transaction(text)
