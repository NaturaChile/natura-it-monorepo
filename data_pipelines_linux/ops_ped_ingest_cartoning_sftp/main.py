import os
import sys

# 1. Setup de rutas para Monorepo (para encontrar core_shared)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../..")))

from core_shared.security.vault import Vault
from src.adapters.sftp_client import SftpClient, SftpConfig
from src.adapters.sql_repository import SqlRepository
from src.adapters.state_manager import StateManager
from src.use_cases.multi_source_pipeline import MultiSourcePipeline, DataSource
from src.domain.file_parser import FileParser

def main():
    # Verificar si se debe ejecutar el explorador de Wave Confirm
    if os.getenv("EXPLORE_WAVECONFIRM", "false").lower() == "true":
        print("\n>>> MODO EXPLORACION: Wave Confirm <<<\n")
        from explore_waveconfirm import explore_waveconfirm_folder
        explore_waveconfirm_folder()
        return
    
    print("Inicializando Bot Multi-Fuente EWM (Streaming Mode)...")

    # 2. Configuracion Global
    config = {
        'threads': 1,  # REDUCIDO: Threads compartidos (evita saturar servidor SFTP)
        'poll_interval': 30,
        'sql_script_path': os.path.join(current_dir, "sql/setup_database.sql")
    }

    # 3. SQL Repository compartido
    sql_adapter = SqlRepository(
        host=Vault.get_secret("SQL_HOST"),
        db=Vault.get_secret("SQL_DB_NAME"),
        user=Vault.get_secret("SQL_USER"),     
        password=Vault.get_secret("SQL_PASS")
    )
    
    # 4. State Manager compartido (diferenciara por prefijo de fuente)
    state_adapter = StateManager(os.path.join(current_dir, "state_store.json"))
    
    # 5. Configurar fuentes de datos
    sources = []
    
    # FUENTE 1: CARTONING
    cartoning_landing = os.path.join(current_dir, "data_lake/bronze/cartoning")
    if not os.path.exists(cartoning_landing):
        os.makedirs(cartoning_landing)
    
    cartoning_sftp = SftpClient(SftpConfig(
        host=Vault.get_secret("EWM_SFTP_HOST"),
        user=Vault.get_secret("EWM_SFTP_USER"),
        password=Vault.get_secret("EWM_SFTP_PASS"),
        remote_path="/EWM/ewm_to_gera/cartoning/02_Old"
    ))
    
    sources.append(DataSource(
        name="Cartoning",
        sftp_client=cartoning_sftp,
        landing_path=cartoning_landing,
        staging_table="Staging_EWM_Cartoning",
        sp_name="sp_Procesar_Cartoning_EWM",
        parser_func=FileParser.parse_cartoning_to_dataframe
    ))
    
    # FUENTE 2: WAVECONFIRM
    waveconfirm_landing = os.path.join(current_dir, "data_lake/bronze/waveconfirm")
    if not os.path.exists(waveconfirm_landing):
        os.makedirs(waveconfirm_landing)
    
    waveconfirm_sftp = SftpClient(SftpConfig(
        host=Vault.get_secret("EWM_SFTP_HOST"),
        user=Vault.get_secret("EWM_SFTP_USER"),
        password=Vault.get_secret("EWM_SFTP_PASS"),
        remote_path="/EWM/ewm_to_gera/waveconfirm/02_old"
    ))
    
    sources.append(DataSource(
        name="WaveConfirm",
        sftp_client=waveconfirm_sftp,
        landing_path=waveconfirm_landing,
        staging_table="Staging_EWM_WaveConfirm",
        sp_name="sp_Procesar_WaveConfirm_EWM",
        parser_func=FileParser.parse_waveconfirm_to_dataframe
    ))
    
    # 6. Crear e iniciar pipeline multi-fuente
    pipeline = MultiSourcePipeline(sources, state_adapter, sql_adapter, config)
    pipeline.run_streaming()

if __name__ == "__main__":
    main()