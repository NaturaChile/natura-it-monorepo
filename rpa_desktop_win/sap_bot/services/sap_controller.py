import time
try:
    import win32com.client
    import win32gui
except Exception:  # pragma: no cover - environment specific
    win32com = None
    win32gui = None


class SapController:
    """Simple controller to interact with SAP GUI via scripting."""

    def __init__(self):
        self.session = None

    def wait_for_main_window(self, title: str = "SAP Easy Access", timeout: int = 10) -> bool:
        """Espera a que SAP este listo verificando la conexion Scripting."""
        end = time.time() + timeout
        
        while time.time() < end:
            try:
                # Intentar conectar al scripting engine como test
                test_gui = win32com.client.GetObject("SAPGUI")
                test_app = test_gui.GetScriptingEngine
                
                # Si tiene al menos una conexion activa, SAP esta listo
                if test_app.Children.Count > 0:
                    return True
                    
            except Exception:
                # SAP aun no esta listo
                pass
            
            time.sleep(0.5)
        
        return False

    def connect(self):
        if win32com is None:
            raise RuntimeError("pywin32 no disponible. Instala pywin32 para usar SapController.")

        SapGuiAuto = None
        try:
            SapGuiAuto = win32com.client.GetObject("SAPGUI")
        except Exception:
            try:
                rot = win32com.client.Dispatch("SapROTWrapper.SapROTWrapper")
                SapGuiAuto = rot.GetROTEntry("SAPGUI")
            except Exception:
                raise RuntimeError("No se pudo conectar a SAPGUI. Asegúrate de que SAP esté abierto y Scripting activado.")

        application = SapGuiAuto.GetScriptingEngine
        connection = application.Children(0)
        session = connection.Children(0)
        self.session = session

    def write_transaction(self, text: str, press_enter: bool = True):
        if not self.session:
            self.connect()

        self.session.findById("wnd[0]").maximize()
        time.sleep(0.3)
        self.session.findById("wnd[0]/tbar[0]/okcd").text = text
        self.session.findById("wnd[0]").sendVKey(0)
        
