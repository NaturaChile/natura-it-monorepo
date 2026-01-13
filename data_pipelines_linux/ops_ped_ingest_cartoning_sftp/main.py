import os
import sys

# 1. Setup de rutas para Monorepo (para encontrar core_shared)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../..")))

from core_shared.security.vault import Vault
from src.adapters.sftp_client import SftpClient, SftpConfig
from src.adapters.sql_repository import SqlRepository
from src.adapters.state_manager import StateManager
from src.use_cases.ingest_pipeline import IngestPipeline

def main():
    # Verificar si se debe ejecutar el explorador de Wave Confirm
    if os.getenv("EXPLORE_WAVECONFIRM", "false").lower() == "true":
        print("\n>>> MODO EXPLORACION: Wave Confirm <<<\n")
        from explore_waveconfirm import explore_waveconfirm_folder
        explore_waveconfirm_folder()
        return
    
    print("Inicializando Bot de Ingesta EWM (Streaming Mode)...")

    # 2. Configuración (Infrastructure Layer)
    config = {
        'landing_path': os.path.join(current_dir, "data_lake/bronze"),
        'sql_script_path': os.path.join(current_dir, "sql/setup_database.sql"),
        'threads': 5,
        'poll_interval': 30  # <--- CRÍTICO: Segundos de espera entre cada ciclo de vigilancia
    }

    # Asegurar que existe directorio de descarga
    if not os.path.exists(config['landing_path']):
        os.makedirs(config['landing_path'])

    # 3. Instanciar Adapters
    # A. SFTP
    sftp_cfg = SftpConfig(
        host=Vault.get_secret("EWM_SFTP_HOST"),
        user=Vault.get_secret("EWM_SFTP_USER"),
        password=Vault.get_secret("EWM_SFTP_PASS"),
        remote_path=Vault.get_secret("EWM_REMOTE_PATH")
    )
    sftp_adapter = SftpClient(sftp_cfg)
    
    # B. State Manager (JSON local para control de deltas)
    state_adapter = StateManager(os.path.join(current_dir, "state_store.json"))
    
    # C. SQL Repository
    sql_adapter = SqlRepository(
        host=Vault.get_secret("SQL_HOST"),
        db=Vault.get_secret("SQL_DB_NAME"),
        # Pasamos las credenciales nuevas
        user=Vault.get_secret("SQL_USER"),     
        password=Vault.get_secret("SQL_PASS")
    )

    # 4. Inyectar dependencias en el Caso de Uso
    bot = IngestPipeline(sftp_adapter, state_adapter, sql_adapter, config)

    # 5. Ejecutar en MODO STREAMING (Bucle Infinito)
    # Cambiamos run() por run_streaming() para que vigile 24/7
    bot.run_streaming()

if __name__ == "__main__":
    main()