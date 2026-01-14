import os
import sys

# 1. Setup de rutas para Monorepo (para encontrar core_shared)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../..")))

from core_shared.security.vault import Vault
from src.adapters.local_file_client import LocalFileClient
from src.adapters.sql_repository import SqlRepository
from src.adapters.state_manager import StateManager
from src.use_cases.multi_source_local_pipeline import MultiSourceLocalPipeline, DataSource
from src.domain.file_parser import FileParser

def main():
    print("Inicializando Pipeline Multi-Fuente EWM (Local + Streaming)...")

    # 2. Configuracion Global
    config = {
        'threads': 3,  # Threads compartidos para procesamiento paralelo
        'sleep_seconds': 300  # 5 minutos entre ciclos
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
    
    # 5. Configurar fuentes de datos (LOCALES - Rclone)
    sources = []
    
    # FUENTE 1: CARTONING (Local)
    cartoning_landing = os.path.join(current_dir, "data_lake/bronze/cartoning")
    os.makedirs(cartoning_landing, exist_ok=True)
    
    cartoning_client = LocalFileClient(r"E:\Datalake\Archivos\EWM\ewm_to_gera\cartoning\02_Old")
    
    sources.append(DataSource(
        name="Cartoning",
        file_client=cartoning_client,
        landing_path=cartoning_landing,
        staging_table="Staging_EWM_Cartoning",
        sp_name="sp_Procesar_Cartoning_EWM",
        parser_func=FileParser.parse_cartoning_to_dataframe
    ))
    
    # FUENTE 2: WAVECONFIRM (Local)
    waveconfirm_landing = os.path.join(current_dir, "data_lake/bronze/waveconfirm")
    os.makedirs(waveconfirm_landing, exist_ok=True)
    
    waveconfirm_client = LocalFileClient(r"E:\Datalake\Archivos\EWM\ewm_to_gera\waveconfirm\02_Old")
    
    sources.append(DataSource(
        name="WaveConfirm",
        file_client=waveconfirm_client,
        landing_path=waveconfirm_landing,
        staging_table="Staging_EWM_WaveConfirm",
        sp_name="sp_Procesar_WaveConfirm_EWM",
        parser_func=FileParser.parse_waveconfirm_to_dataframe
    ))
    
    # FUENTE 3: OUTBOUND DELIVERY - SAP IDoc (Local)
    outbound_landing = os.path.join(current_dir, "data_lake/bronze/outbound_delivery")
    os.makedirs(outbound_landing, exist_ok=True)
    
    outbound_client = LocalFileClient(r"E:\Datalake\Archivos\EWM\gera_to_ewm_outbounddelivery")
    
    sources.append(DataSource(
        name="OutboundDelivery",
        file_client=outbound_client,
        landing_path=outbound_landing,
        staging_table="Staging_EWM_OutboundDelivery_Header",
        staging_table_items="Staging_EWM_OutboundDelivery_Items",  # Segunda tabla
        sp_name="sp_Procesar_OutboundDelivery_EWM",
        parser_func=FileParser.parse_outbound_delivery_to_dataframes
    ))
    
    # 6. Crear e iniciar pipeline multi-fuente (LOCAL)
    pipeline = MultiSourceLocalPipeline(sources, state_adapter, sql_adapter, config)
    pipeline.run_streaming()

if __name__ == "__main__":
    main()