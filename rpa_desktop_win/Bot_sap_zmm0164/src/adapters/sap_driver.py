"""
adapters/sap_driver.py

Adaptador técnico para SAP GUI.
Encapsula toda la lógica de pywin32 y comunicación con SAP.
Es el único módulo que conoce detalles técnicos de SAP.
"""

import win32com.client
import subprocess
import time
import sys
import os
from typing import Optional


class SAPDriver:
    """Driver para conectar y manipular SAP GUI."""
    
    def __init__(self, sap_logon_path: str, connection_name: str):
        """
        Inicializa el driver SAP.
        
        Args:
            sap_logon_path: Ruta a saplogon.exe
            connection_name: Nombre de la conexión SAP (ej: "1.02 - PRD")
        """
        self.sap_logon_path = sap_logon_path
        self.connection_name = connection_name
        self.session = None
    
    def connect(self) -> None:
        """Conexión robusta a SAP. Lanza saplogon si es necesario."""
        try:
            SapGuiAuto = win32com.client.GetObject("SAPGUI")
            if not type(SapGuiAuto) == win32com.client.CDispatch:
                raise Exception("Objeto SAP no válido")
        except:
            print("[SAP] Lanzando SAP Logon...")
            subprocess.Popen(self.sap_logon_path)
            time.sleep(5)
            
            # Reintentar conexión
            for attempt in range(30):
                try:
                    SapGuiAuto = win32com.client.GetObject("SAPGUI")
                    break
                except:
                    time.sleep(1)
            else:
                raise Exception("No se pudo inicializar SAP GUI después de 30 intentos")
        
        # Obtener aplicación
        application = SapGuiAuto.GetScriptingEngine
        
        # Buscar conexión existente
        connection = None
        for i in range(application.Connections.Count):
            if self.connection_name in application.Children(int(i)).Description:
                connection = application.Children(int(i))
                break
        
        # Si no existe, intentar crear
        if connection is None:
            try:
                connection = application.OpenConnection(self.connection_name, True)
            except Exception as e:
                raise Exception(f"No se encontró conexión '{self.connection_name}': {e}")
        
        # Obtener sesión
        self.session = connection.Children(0)
        print(f"[SAP] Conectado a {self.connection_name}")
    
    def disconnect(self) -> None:
        """Cierra la sesión SAP y termina el proceso saplogon.exe."""
        if self.session is None:
            return
        
        try:
            # Logout
            self.send_command("/nex")
            time.sleep(2)
        except:
            pass
        finally:
            # Matar proceso
            print("[SAP] Cerrando SAP Logon...")
            os.system("taskkill /F /IM saplogon.exe")
            self.session = None
    
    def login(self, client: str, user: str, password: str, language: str = "ES") -> None:
        """Ingresa las credenciales en la pantalla de login."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        try:
            # Limpiar message bar si existe
            try:
                if self.session.findById("wnd[0]/sbar").text != "":
                    self.session.findById("wnd[0]").sendVKey(0)
            except:
                pass
            
            # Ingresarledenciales
            self.session.findById("wnd[0]/usr/txtRSYST-MANDT").text = client
            self.session.findById("wnd[0]/usr/txtRSYST-BNAME").text = user
            self.session.findById("wnd[0]/usr/pwdRSYST-BCODE").text = password
            self.session.findById("wnd[0]/usr/txtRSYST-LANGU").text = language
            
            # Enviar (Enter)
            self.session.findById("wnd[0]").sendVKey(0)
            print(f"[SAP] Login exitoso como {user}")
        except Exception as e:
            raise Exception(f"Error en login: {e}")
    
    def send_command(self, command: str) -> None:
        """Envía un comando a la barra de comandos de SAP."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById("wnd[0]/tbar[0]/okcd").text = command
        self.session.findById("wnd[0]").sendVKey(0)
        print(f"[SAP] Comando: {command}")
    
    def set_field_text(self, field_id: str, value: str) -> None:
        """Establece el texto de un campo."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById(field_id).text = value
    
    def get_field_text(self, field_id: str) -> str:
        """Obtiene el texto de un campo."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        return self.session.findById(field_id).text
    
    def press_button(self, button_id: str) -> None:
        """Presiona un botón por su ID."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById(button_id).press()
    
    def press_function_key(self, key_code: int) -> None:
        """Presiona una tecla de función (F1=1, F2=2, ..., F8=8, etc)."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById("wnd[0]").sendVKey(key_code)
        print(f"[SAP] F{key_code} presionado")
    
    def select_radio_button(self, radio_id: str) -> None:
        """Selecciona un botón de radio."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById(radio_id).select()
    
    def maximize_window(self) -> None:
        """Maximiza la ventana principal de SAP."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        self.session.findById("wnd[0]").maximize()
    
    def wait_for_field(self, field_id: str, timeout: int = 20) -> bool:
        """Espera a que un campo esté disponible (para diálogos de guardado)."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        for attempt in range(timeout):
            try:
                field_text = self.session.findById(field_id).text
                if field_text != "ERROR":
                    return True
            except:
                pass
            time.sleep(1)
        
        return False
    
    def confirm_overwrite(self, window_index: int = 2) -> None:
        """Confirma el reemplazo de archivo (botón Sí en diálogo de confirmación)."""
        if self.session is None:
            raise Exception("Sesión no inicializada")
        
        try:
            time.sleep(1)
            if self.session.Children.Count > window_index:
                # Botón 11 es típicamente "Sí" en SAP
                self.session.findById(f"wnd[{window_index}]/tbar[0]/btn[11]").press()
                print("[SAP] Confirmado: Sobrescribir archivo")
        except Exception as e:
            print(f"[SAP] Advertencia al confirmar sobrescritura: {e}")
