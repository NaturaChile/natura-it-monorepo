"""
use_cases/release_process.py

Lógica de negocio para el proceso de exportación ZMM0164.
Orquesta el flujo: Conexión > Login > Transacción > Exportación > Guardado.

No contiene detalles técnicos de SAP ni Windows.
Solo sabe QUÉ hacer, no CÓMO hacerlo (eso lo delega al driver).
"""

from src.adapters.sap_driver import SAPDriver
from src.domain.export_data import (
    ExportConfig,
    SAPCredentials,
    SAPConnection,
)


class ExportZMM0164UseCase:
    """Caso de uso: Exportar datos de la transacción ZMM0164 de SAP."""
    
    def __init__(
        self,
        sap_connection: SAPConnection,
        credentials: SAPCredentials,
        export_config: ExportConfig,
    ):
        """
        Inicializa el caso de uso.
        
        Args:
            sap_connection: Parámetros de conexión a SAP
            credentials: Credenciales SAP
            export_config: Configuración de exportación
        """
        self.sap_connection = sap_connection
        self.credentials = credentials
        self.export_config = export_config
        self.driver = None
    
    def execute(self) -> None:
        """
        Ejecuta el proceso completo de exportación.
        
        Flujo:
        1. Conectar a SAP
        2. Login
        3. Navegar a transacción ZMM0164
        4. Ingresar parámetros de búsqueda
        5. Ejecutar búsqueda (F8)
        6. Exportar a archivo
        7. Guardar con nombre y ruta
        8. Desconectar
        """
        try:
            # Paso 1: Conectar
            print("=" * 60)
            print("[BOT] INICIANDO PROCESO DE EXPORTACIÓN ZMM0164")
            print("=" * 60)
            
            self.driver = SAPDriver(
                sap_logon_path=self.sap_connection.sap_logon_path,
                connection_name=self.sap_connection.connection_name,
            )
            self.driver.connect()
            
            # Paso 2: Login
            print("\n[INFO] Realizando login...")
            self.driver.login(
                client=self.credentials.client,
                user=self.credentials.user,
                password=self.credentials.password,
                language=self.credentials.language,
            )
            
            # Paso 3: Ir a transacción
            print("\n[NAV] Navegando a transacción ZMM0164...")
            self.driver.send_command(f"/n{self.sap_connection.transaction}")
            
            # Paso 4: Maximizar y establecer parámetros
            print("\n[CONFIG] Configurando búsqueda...")
            self.driver.maximize_window()
            
            # Buscar por código de material
            self.driver.set_field_text(
                "wnd[0]/usr/ctxtSP$00006-LOW",
                self.export_config.material_code,
            )
            
            # Paso 5: Ejecutar búsqueda (F8)
            print(f"[SEARCH] Ejecutando búsqueda para material: {self.export_config.material_code}")
            self.driver.press_function_key(8)  # F8
            
            # Esperar resultado
            print("[WAIT] Esperando resultados...")
            import time
            time.sleep(2)
            
            # Paso 6: Exportar (Botones 30 y 45)
            print("\n[EXPORT] Exportando datos...")
            self.driver.press_button("wnd[0]/tbar[1]/btn[30]")
            self.driver.press_button("wnd[0]/tbar[1]/btn[45]")
            
            # Paso 7: Configurar formato
            print("[CONFIG] Configurando formato XLS...")
            self.driver.select_radio_button(
                "wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]"
            )
            self.driver.press_button("wnd[1]/tbar[0]/btn[0]")
            
            # Paso 8: Esperar y configurar guardado
            print("\n[WAIT] Esperando diálogo de guardado...")
            self.driver.wait_for_field("wnd[1]/usr/ctxtDY_PATH")
            
            # Ingresar ruta
            print(f"[PATH] Ruta de destino: {self.export_config.output_folder}")
            self.driver.set_field_text(
                "wnd[1]/usr/ctxtDY_PATH",
                self.export_config.output_folder,
            )
            
            # Ingresar nombre de archivo
            print(f"[FILENAME] Nombre de archivo: {self.export_config.filename}")
            self.driver.set_field_text(
                "wnd[1]/usr/ctxtDY_FILENAME",
                self.export_config.filename,
            )
            
            import time
            time.sleep(0.5)
            
            # Generar archivo
            print("\n[CLICK] Generando archivo...")
            try:
                self.driver.press_button("wnd[1]/tbar[0]/btn[0]")
            except:
                pass
            
            # Confirmar sobrescritura si es necesario
            self.driver.confirm_overwrite()
            
            print(f"[OK] Archivo guardado exitosamente en: {self.export_config.full_path}")
            
        except Exception as e:
            print(f"\n[ERROR] Error en proceso de exportación: {e}")
            raise
        finally:
            # Paso 9: Desconectar
            if self.driver is not None:
                print("\n[DISCONNECT] Desconectando...")
                self.driver.disconnect()
            
            print("[DONE] Fin del proceso.\n")
