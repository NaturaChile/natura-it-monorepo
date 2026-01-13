import os
import time
import glob
import concurrent.futures
import pandas as pd
from datetime import datetime
# --- CAMBIO IMPORTANTE: RUTAS ABSOLUTAS ---
# En lugar de '..adapters', usamos 'src.adapters'
from src.adapters.sftp_client import SftpClient
from src.adapters.state_manager import StateManager
from src.adapters.sql_repository import SqlRepository
from src.domain.file_parser import FileParser
# ------------------------------------------

class IngestPipeline:
    def __init__(self, sftp: SftpClient, state: StateManager, sql: SqlRepository, config: dict):
        self.sftp = sftp
        self.state = state
        self.sql = sql
        self.cfg = config
        self.is_running = True # Bandera de control

    def run_streaming(self):
        """Modo Servicio Continuo: Nunca termina"""
        print(f" [STREAMING STARTED] Iniciando vigilancia continua SFTP...")
        print(f"⏱  Intervalo de polling: {self.cfg['poll_interval']} segundos")

        # 1. SETUP INICIAL (Solo una vez al inicio)
        self.sql.init_schema(self.cfg['sql_script_path'])

        try:
            while self.is_running:
                # Marcamos hora para logs
                now = datetime.now().strftime("%H:%M:%S")
                
                # --- CICLO DE TRABAJO ---
                hay_nuevos = self._step_download_deltas()
                
                # Solo intentamos procesar si bajamos algo o si quedaron pendientes de antes
                if hay_nuevos or self._check_pending_local():
                    self._step_process_pending()
                else:
                    # Mensaje heartbeat opcional para saber que sigue vivo (comentar para menos ruido)
                    # print(f"💤 [{now}] Sin novedades. Esperando...")
                    pass

                # --- DORMIR ---
                time.sleep(self.cfg['poll_interval'])

        except KeyboardInterrupt:
            print("\n [STOP] Deteniendo servicio ordenadamente...")

    def _check_pending_local(self):
        """Verifica rápido si hay algo pendiente en disco"""
        all_files = glob.glob(os.path.join(self.cfg['landing_path'], "*"))
        for f in all_files:
            if self.state.is_pending_sql(os.path.basename(f)):
                return True
        return False

    def _step_download_deltas(self):
        # ... (Mantener lógica de descarga igual, solo quitar prints excesivos si deseas) ...
        # Retorna True si descargó algo, False si no.
        downloaded_count = 0
        try:
            files = self.sftp.list_files()
            to_download = []
            for f in files:
                if self.state.is_new_or_modified(f.filename, f.st_mtime, f.st_size):
                    to_download.append(f)

            if to_download:
                print(f"Bajando {len(to_download)} archivos nuevos...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.cfg['threads']) as ex:
                    futures = {ex.submit(self.sftp.download_file, f.filename, self.cfg['landing_path']): f for f in to_download}
                    for fut in concurrent.futures.as_completed(futures):
                        f_attr = futures[fut]
                        if fut.result():
                            self.state.register_download(f_attr.filename, f_attr.st_mtime, f_attr.st_size)
                            downloaded_count += 1
        except Exception as e:
            print(f" Error conexión SFTP (Reintentando en {self.cfg['poll_interval']}s): {e}")
        
        return downloaded_count > 0

    def _step_process_pending(self):
        # ... (Mantener lógica de procesamiento igual) ...
        all_files = glob.glob(os.path.join(self.cfg['landing_path'], "*"))
        pending = [f for f in all_files if self.state.is_pending_sql(os.path.basename(f))]

        if not pending: return

        print(f" Procesando {len(pending)} archivos hacia SQL...")
        batch_size = 20
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            self._process_batch(batch)

    def _process_batch(self, file_paths):
        # ... (Mantener igual) ...
        dfs = []
        valid_files = []
        for fp in file_paths:
            df = FileParser.parse_to_dataframe(fp)
            if df is not None:
                dfs.append(df)
                valid_files.append(fp)

        if not dfs: return

        full_df = pd.concat(dfs, ignore_index=True)
        if self.sql.bulk_insert(full_df, "Staging_EWM_Cartoning"):
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                fs = {ex.submit(self.sql.execute_sp, "sp_Procesar_Cartoning_EWM", {"ArchivoActual": os.path.basename(f)}): f for f in valid_files}
                concurrent.futures.wait(fs)

            for f in valid_files:
                self.state.mark_as_processed_in_sql(os.path.basename(f))
            print(f"       Lote guardado.")