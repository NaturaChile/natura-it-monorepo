"""
examples/test_example.py

Ejemplos de cómo testear la aplicación sin necesidad de SAP real.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock

# Importar los módulos a testear
import sys
sys.path.insert(0, r"..\src")

from domain.export_data import (
    ExportConfig,
    SAPCredentials,
    SAPConnection,
)


class TestExportDataModels(unittest.TestCase):
    """Tests para modelos de dominio."""
    
    def test_export_config_filename_generation(self):
        """Verifica que el nombre de archivo incluya la fecha."""
        config = ExportConfig(
            material_code="4100",
            output_folder=r"Z:\Publico",
            file_format="XLS",
        )
        
        # El nombre debe contener la fecha
        self.assertIn("zmm0164-", config.filename)
        self.assertTrue(config.filename.endswith(".xls"))
    
    def test_export_config_full_path(self):
        """Verifica que la ruta completa se construya correctamente."""
        config = ExportConfig(
            material_code="4100",
            output_folder=r"Z:\Publico",
            file_format="XLS",
        )
        
        full_path = config.full_path
        self.assertIn(r"Z:\Publico", full_path)
        self.assertIn("zmm0164-", full_path)
    
    def test_sap_credentials_creation(self):
        """Verifica que las credenciales se creen correctamente."""
        creds = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="test123",
            language="ES",
        )
        
        self.assertEqual(creds.client, "210")
        self.assertEqual(creds.user, "BOTSCL")
        self.assertEqual(creds.language, "ES")
    
    def test_sap_connection_creation(self):
        """Verifica parámetros de conexión."""
        conn = SAPConnection(
            sap_logon_path=r"C:\SAP\saplogon.exe",
            connection_name="1.02 - PRD",
            transaction="zmm0164",
        )
        
        self.assertEqual(conn.transaction, "zmm0164")


class MockSAPDriver:
    """Mock del driver SAP para testing sin necesidad de SAP real."""
    
    def __init__(self, sap_logon_path: str, connection_name: str):
        self.sap_logon_path = sap_logon_path
        self.connection_name = connection_name
        self.session = None
        self.connected = False
        self.logged_in = False
        self.commands = []  # Historial de comandos
    
    def connect(self):
        """Simula conexión."""
        print(f"[MOCK] Conectando a {self.connection_name}")
        self.session = MagicMock()
        self.connected = True
    
    def disconnect(self):
        """Simula desconexión."""
        print("[MOCK] Desconectando")
        self.connected = False
    
    def login(self, client: str, user: str, password: str, language: str = "ES"):
        """Simula login."""
        if not self.connected:
            raise Exception("No conectado")
        
        print(f"[MOCK] Login como {user}")
        self.logged_in = True
    
    def send_command(self, command: str):
        """Simula comando SAP."""
        if not self.connected:
            raise Exception("No conectado")
        
        self.commands.append(command)
        print(f"[MOCK] Comando: {command}")
    
    def set_field_text(self, field_id: str, value: str):
        """Simula escritura en campo."""
        if not self.connected:
            raise Exception("No conectado")
        
        print(f"[MOCK] Campo {field_id} = {value}")
    
    def press_function_key(self, key_code: int):
        """Simula presionar tecla."""
        if not self.connected:
            raise Exception("No conectado")
        
        print(f"[MOCK] F{key_code}")
    
    def press_button(self, button_id: str):
        """Simula presionar botón."""
        if not self.connected:
            raise Exception("No conectado")
    
    def maximize_window(self):
        """Simula maximizar."""
        pass
    
    def wait_for_field(self, field_id: str, timeout: int = 20):
        """Simula espera."""
        return True


class TestExportZMM0164UseCase(unittest.TestCase):
    """Tests para el caso de uso de exportación."""
    
    def setUp(self):
        """Configuración antes de cada test."""
        self.sap_connection = SAPConnection(
            sap_logon_path=r"C:\SAP\saplogon.exe",
            connection_name="1.02 - PRD",
            transaction="zmm0164",
        )
        
        self.credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="test123",
        )
        
        self.export_config = ExportConfig(
            material_code="4100",
            output_folder=r"Z:\Test",
            file_format="XLS",
        )
    
    def test_use_case_initialization(self):
        """Verifica que el caso de uso se inicialice correctamente."""
        # Importar aquí para evitar errores si SAPDriver no está disponible
        from adapters.sap_driver import SAPDriver
        
        # Para este test, solo verificamos que la estructura esté bien
        self.assertEqual(self.sap_connection.transaction, "zmm0164")
        self.assertEqual(self.credentials.user, "BOTSCL")
        self.assertEqual(self.export_config.material_code, "4100")
    
    @patch('adapters.sap_driver.SAPDriver')
    def test_use_case_flow_with_mock(self, mock_driver_class):
        """Prueba el flujo completo con un mock del driver."""
        # Configurar el mock
        mock_driver = MagicMock()
        mock_driver_class.return_value = mock_driver
        
        # Importar aquí el caso de uso
        from use_cases.release_process import ExportZMM0164UseCase
        
        use_case = ExportZMM0164UseCase(
            sap_connection=self.sap_connection,
            credentials=self.credentials,
            export_config=self.export_config,
        )
        
        # Verificar que se inicializó correctamente
        self.assertIsNotNone(use_case)
        self.assertEqual(use_case.export_config.material_code, "4100")


class TestSAPDriverMock(unittest.TestCase):
    """Tests para el mock del driver."""
    
    def setUp(self):
        """Configuración antes de cada test."""
        self.driver = MockSAPDriver(
            sap_logon_path=r"C:\SAP\saplogon.exe",
            connection_name="1.02 - PRD",
        )
    
    def test_driver_connect(self):
        """Verifica conexión del driver."""
        self.assertFalse(self.driver.connected)
        
        self.driver.connect()
        
        self.assertTrue(self.driver.connected)
    
    def test_driver_login_requires_connection(self):
        """Verifica que login requiere estar conectado."""
        with self.assertRaises(Exception):
            self.driver.login("210", "BOTSCL", "test123")
    
    def test_driver_login_success(self):
        """Verifica login exitoso después de conectar."""
        self.driver.connect()
        
        self.driver.login("210", "BOTSCL", "test123")
        
        self.assertTrue(self.driver.logged_in)
    
    def test_driver_commands_history(self):
        """Verifica historial de comandos."""
        self.driver.connect()
        
        self.driver.send_command("/nzmm0164")
        self.driver.send_command("/nex")
        
        self.assertEqual(len(self.driver.commands), 2)
        self.assertEqual(self.driver.commands[0], "/nzmm0164")
        self.assertEqual(self.driver.commands[1], "/nex")
    
    def test_driver_disconnect(self):
        """Verifica desconexión."""
        self.driver.connect()
        self.assertTrue(self.driver.connected)
        
        self.driver.disconnect()
        
        self.assertFalse(self.driver.connected)


class TestIntegrationScenario(unittest.TestCase):
    """Test de integración con mock del driver."""
    
    def test_complete_export_flow(self):
        """Simula el flujo completo de exportación."""
        # Crear driver mock
        driver = MockSAPDriver(
            sap_logon_path=r"C:\SAP\saplogon.exe",
            connection_name="1.02 - PRD",
        )
        
        # Simular flujo
        try:
            driver.connect()
            driver.login("210", "BOTSCL", "test123")
            driver.send_command("/nzmm0164")
            driver.set_field_text("wnd[0]/usr/ctxtSP$00006-LOW", "4100")
            driver.press_function_key(8)
            
            # Verificaciones
            self.assertTrue(driver.connected)
            self.assertTrue(driver.logged_in)
            self.assertEqual(driver.commands[0], "/nzmm0164")
            
        finally:
            driver.disconnect()


# ============================================
# Ejecutar tests
# ============================================

if __name__ == "__main__":
    # Verbose output
    unittest.main(verbosity=2)

"""
Ejecutar tests:
    python -m pytest examples/test_example.py -v
    
O con unittest:
    python examples/test_example.py

Cobertura:
    pytest examples/test_example.py --cov=src --cov-report=html
"""
