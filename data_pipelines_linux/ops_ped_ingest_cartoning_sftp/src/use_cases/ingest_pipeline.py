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
        self.cycle_count = 0  # Contador de ciclos
        self.total_downloaded = 0  # Total descargados en sesión
        self.total_errors = 0  # Total errores en sesión

    def run_streaming(self):
        """Modo Servicio Continuo: Nunca termina"""
        print(f"\n{'='*70}")
        print(f" STREAMING SERVICE INICIADO")
        print(f" Intervalo de polling: {self.cfg['poll_interval']} segundos")
        print(f"{'='*70}\n")

        # 1. SETUP INICIAL (Solo una vez al inicio)
        self.sql.init_schema(self.cfg['sql_script_path'])

        try:
            while self.is_running:
                self.cycle_count += 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"\n{'-'*70}")
                print(f"CICLO #{self.cycle_count} | {now}")
                print(f"Sesion: {self.total_downloaded} descargados, {self.total_errors} errores acumulados")
                print(f"{'-'*70}")
                
                # --- CICLO DE TRABAJO ---
                hay_nuevos = self._step_download_deltas()
                
                # Solo intentamos procesar si bajamos algo o si quedaron pendientes de antes
                if hay_nuevos or self._check_pending_local():
                    self._step_process_pending()
                else:
                    print(f"Sin archivos nuevos ni pendientes. Esperando {self.cfg['poll_interval']}s...")

                # --- DORMIR ---
                time.sleep(self.cfg['poll_interval'])

        except KeyboardInterrupt:
            print("\n  Deteniendo servicio ordenadamente...")
            print(f"  Resumen final: {self.total_downloaded} archivos descargados, {self.total_errors} errores")

    def _check_pending_local(self):
        """Verifica rápido si hay algo pendiente en disco"""
        all_files = glob.glob(os.path.join(self.cfg['landing_path'], "*"))
        for f in all_files:
            if self.state.is_pending_sql(os.path.basename(f)):
                return True
        return False

    def _step_download_deltas(self):
        """Descarga archivos nuevos/modificados con logging detallado"""
        downloaded_count = 0
        error_count = 0
        try:
            files = self.sftp.list_files()
            to_download = []
            for f in files:
                if self.state.is_new_or_modified(f.filename, f.st_mtime, f.st_size):
                    to_download.append(f)

            if to_download:
                total = len(to_download)
                print(f"\n=== DESCARGA INICIADA: {total} archivos detectados ===")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.cfg['threads']) as ex:
                    futures = {ex.submit(self.sftp.download_file, f.filename, self.cfg['landing_path']): f for f in to_download}
                    
                    for fut in concurrent.futures.as_completed(futures):
                        f_attr = futures[fut]
                        try:
                            if fut.result():
                                self.state.register_download(f_attr.filename, f_attr.st_mtime, f_attr.st_size)
                                downloaded_count += 1
                                print(f"  Progreso: {downloaded_count}/{total} OK | Errores: {error_count} | Archivo: {f_attr.filename[:50]}")
                            else:
                                error_count += 1
                                print(f"  Progreso: {downloaded_count}/{total} OK | Errores: {error_count} | FALLO: {f_attr.filename[:50]}")
                        except Exception as e:
                            error_count += 1
                            print(f"  Progreso: {downloaded_count}/{total} OK | Errores: {error_count} | ERROR: {str(e)[:50]}")
                
                print(f"=== DESCARGA COMPLETADA: {downloaded_count} exitosos, {error_count} fallidos de {total} ===\n")
                
                # Actualizar contadores globales
                self.total_downloaded += downloaded_count
                self.total_errors += error_count
                
                if error_count > 0:
                    print(f"NOTA: Los {error_count} archivos fallidos NO se marcaron como descargados.")
                    print(f"      Se reintentarán automáticamente en el próximo ciclo.\n")
                    
        except Exception as e:
            print(f"ERROR conexión SFTP (Reintentando en {self.cfg['poll_interval']}s): {e}")
        
        return downloaded_count > 0

    def _step_process_pending(self):
        """Procesa archivos descargados hacia SQL con logging detallado"""
        all_files = glob.glob(os.path.join(self.cfg['landing_path'], "*"))
        pending = [f for f in all_files if self.state.is_pending_sql(os.path.basename(f))]

        if not pending: return

        total_pending = len(pending)
        print(f"\n=== PROCESANDO A SQL: {total_pending} archivos pendientes ===")
        
        batch_size = 20
        processed_count = 0
        
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_pending + batch_size - 1) // batch_size
            
            print(f"  Lote {batch_num}/{total_batches}: Procesando {len(batch)} archivos...")
            success = self._process_batch(batch)
            
            if success:
                processed_count += len(batch)
                print(f"  Lote {batch_num}/{total_batches}: COMPLETADO ({processed_count}/{total_pending} procesados)")
            else:
                print(f"  Lote {batch_num}/{total_batches}: ERROR - Se reintentará después")
        
        print(f"=== PROCESAMIENTO SQL COMPLETADO: {processed_count}/{total_pending} archivos ===\n")

    def _process_batch(self, file_paths):
        """Procesa un lote de archivos hacia SQL"""
        dfs = []
        valid_files = []
        for fp in file_paths:
            df = FileParser.parse_to_dataframe(fp)
            if df is not None:
                dfs.append(df)
                valid_files.append(fp)

        if not dfs: 
            print(f"    AVISO: No hay datos válidos para procesar en este lote")
            return False

        full_df = pd.concat(dfs, ignore_index=True)
        if self.sql.bulk_insert(full_df, "Staging_EWM_Cartoning"):
            # Procesar SPs SECUENCIALMENTE para evitar deadlocks
            success_count = 0
            error_count = 0
            
            for f in valid_files:
                archivo = os.path.basename(f)
                if self.sql.execute_sp("sp_Procesar_Cartoning_EWM", {"ArchivoActual": archivo}):
                    self.state.mark_as_processed_in_sql(archivo)
                    success_count += 1
                else:
                    error_count += 1
                    print(f"    PENDIENTE: {archivo} (se reintentara en proximo ciclo)")
            
            if error_count > 0:
                print(f"    RESUMEN: {success_count} OK, {error_count} fallidos (se reintentaran)")
            
            return success_count > 0
        else:
            print(f"    ERROR: Fallo al insertar lote en SQL")
            return False