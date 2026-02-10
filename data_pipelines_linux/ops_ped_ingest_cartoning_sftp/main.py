import os
import sys
from datetime import datetime

def _log(tag: str, msg: str):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")

# 1. Setup de rutas para Monorepo (para encontrar core_shared)
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../..")))

from core_shared.security.vault import Vault
from src.adapters.local_file_client import LocalFileClient
from src.adapters.sql_repository import SqlRepository
from src.adapters.state_manager import StateManager
from src.use_cases.multi_source_pipeline import MultiSourcePipeline, DataSource
from src.domain.file_parser import FileParser

def main():
    _log('MAIN', '========== INICIO Pipeline Multi-Fuente EWM ==========')
    _log('MAIN', f'Directorio de trabajo: {current_dir}')
    _log('MAIN', f'Python: {sys.version}')

    # 2. Configuracion Global
    _log('MAIN', 'Cargando configuración...')
    config = {
        'threads': 3,
        'poll_interval': 300,
        'sql_script_path': os.path.join(current_dir, "sql/setup_database.sql")
    }
    _log('MAIN', f'  poll_interval={config["poll_interval"]}s, threads={config["threads"]}')

    # 3. SQL Repository compartido
    _log('MAIN', 'Creando conexión SQL...')
    sql_adapter = SqlRepository(
        host=Vault.get_secret("SQL_HOST"),
        db=Vault.get_secret("SQL_DB_NAME"),
        user=Vault.get_secret("SQL_USER"),     
        password=Vault.get_secret("SQL_PASS")
    )
    
    # 4. State Manager compartido
    state_path = os.path.join(current_dir, "state_store.json")
    state_adapter = StateManager(state_path)
    state_count = len(state_adapter.state)
    _log('MAIN', f'State Manager: {state_count} archivos registrados en {state_path}')
    
    # 5. Configurar fuentes de datos
    _log('MAIN', 'Configurando fuentes de datos...')
    sources = []
    
    # FUENTE 1: CARTONING
    cart_path = r"E:\Datalake\Archivos\EWM\ewm_to_gera\cartoning\02_Old"
    _log('MAIN', f'  [1] Cartoning: {cart_path}')
    cartoning_client = LocalFileClient(cart_path)
    
    sources.append(DataSource(
        name="Cartoning",
        file_client=cartoning_client,
        staging_table="Staging_EWM_Cartoning",
        sp_name="sp_Procesar_Cartoning_EWM",
        parser_func=FileParser.parse_cartoning_to_dataframe
    ))
    
    # FUENTE 2: WAVECONFIRM
    wave_path = r"E:\Datalake\Archivos\EWM\ewm_to_gera\waveconfirm\02_Old"
    _log('MAIN', f'  [2] WaveConfirm: {wave_path}')
    waveconfirm_client = LocalFileClient(wave_path)
    
    sources.append(DataSource(
        name="WaveConfirm",
        file_client=waveconfirm_client,
        staging_table="Staging_EWM_WaveConfirm",
        sp_name="sp_Procesar_WaveConfirm_EWM",
        parser_func=FileParser.parse_waveconfirm_to_dataframe
    ))
    
    # FUENTE 3: OUTBOUND DELIVERY
    obd_path = r"E:\Datalake\Archivos\EWM\gera_to_ewm\outbounddelivery\02_Old"
    _log('MAIN', f'  [3] OutboundDelivery: {obd_path}')
    outbound_client = LocalFileClient(obd_path)
    
    sources.append(DataSource(
        name="OutboundDelivery",
        file_client=outbound_client,
        staging_table="Staging_EWM_OutboundDelivery_Header",
        staging_table_items="Staging_EWM_OutboundDelivery_Items",
        sp_name="sp_Procesar_OutboundDelivery_EWM",
        parser_func=FileParser.parse_outbound_delivery_to_dataframes
    ))
    
    # FUENTE 4: OUTBOUND DELIVERY CONFIRM
    obdc_path = r"E:\Datalake\Archivos\EWM\ewm_to_gera\outbounddeliveryconfirm\02_Old"
    _log('MAIN', f'  [4] OutboundDeliveryConfirm: {obdc_path}')
    outbound_confirm_client = LocalFileClient(obdc_path)
    
    sources.append(DataSource(
        name="OutboundDeliveryConfirm",
        file_client=outbound_confirm_client,
        staging_table="Staging_EWM_OBDConfirm_Cabecera",
        staging_table_items="Staging_EWM_OBDConfirm_Posiciones",
        staging_table_control="Staging_EWM_OBDConfirm_Control_Posiciones",
        staging_table_unidades="Staging_EWM_OBDConfirm_Unidades_HDR",
        staging_table_contenido="Staging_EWM_OBDConfirm_Contenido_Embalaje",
        staging_table_extensiones="Staging_EWM_OBDConfirm_Extensiones",
        sp_name="sp_Procesar_OutboundDeliveryConfirm_EWM",
        parser_func=FileParser.parse_outbound_delivery_confirm_to_dataframes
    ))
    
    _log('MAIN', f'{len(sources)} fuentes configuradas. Iniciando pipeline...')
    
    # 6. Crear e iniciar pipeline multi-fuente
    pipeline = MultiSourcePipeline(sources, state_adapter, sql_adapter, config)
    pipeline.run_streaming()

if __name__ == "__main__":
    main()