import time
try:
    import win32com.client
except Exception:  # pragma: no cover - environment specific
    win32com = None


class SapController:
    """Controller para SAP GUI Scripting (duplicado desde sap_bot/services)."""

    def __init__(self):
        self.session = None

    def wait_for_main_window(self, title: str = "SAP", timeout: int = 10) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            try:
                test_gui = win32com.client.GetObject("SAPGUI")
                test_app = test_gui.GetScriptingEngine
                if test_app.Children.Count > 0:
                    conn = test_app.Children(0)
                    if conn.Children.Count > 0:
                        return True
            except Exception:
                pass
            time.sleep(0.5)
        return False

    def connect(self):
        if win32com is None:
            raise RuntimeError("pywin32 no disponible. Instala pywin32 para usar SapController.")

        SapGuiAuto = None
        try:
            SapGuiAuto = win32com.client.GetObject("SAPGUI")
        except Exception as e1:
            try:
                rot = win32com.client.Dispatch("SapROTWrapper.SapROTWrapper")
                SapGuiAuto = rot.GetROTEntry("SAPGUI")
            except Exception as e2:
                try:
                    SapGuiAuto = win32com.client.Dispatch("SAPGUI")
                except Exception as e3:
                    raise RuntimeError(
                        f"No se pudo conectar a SAPGUI. Intentos:\n"
                        f"  1. GetObject: {str(e1)}\n"
                        f"  2. ROT: {str(e2)}\n"
                        f"  3. Dispatch: {str(e3)}\n"
                        f"Asegurate de que SAP este abierto y Scripting activado."
                    )

        application = SapGuiAuto.GetScriptingEngine
        if application.Children.Count == 0:
            raise RuntimeError("SAP GUI esta abierto pero no hay conexiones activas. Verifica que el login haya completado.")

        connection = application.Children(0)
        if connection.Children.Count == 0:
            raise RuntimeError("SAP tiene conexion pero no hay sesiones activas.")

        session = connection.Children(0)
        self.session = session

    def write_transaction(self, text: str, press_enter: bool = True):
        if not self.session:
            self.connect()

        self.session.findById("wnd[0]").maximize()
        time.sleep(0.3)
        self.session.findById("wnd[0]/tbar[0]/okcd").text = text
        self.session.findById("wnd[0]").sendVKey(0)
