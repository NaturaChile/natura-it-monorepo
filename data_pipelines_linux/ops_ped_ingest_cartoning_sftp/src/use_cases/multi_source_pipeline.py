import os
import time
import glob
import concurrent.futures
import pandas as pd
from datetime import datetime
from src.adapters.sftp_client import SftpClient
from src.adapters.state_manager import StateManager
from src.adapters.sql_repository import SqlRepository
from src.domain.file_parser import FileParser

class DataSource:
    """Configuración de una fuente de datos"""
    def __init__(self, name, sftp_client, landing_path, staging_table, sp_name, parser_func):
        self.name = name
        self.sftp_client = sftp_client
        self.landing_path = landing_path
        self.staging_table = staging_table
        self.sp_name = sp_name
        self.parser_func = parser_func

class MultiSourcePipeline:
    """Pipeline unificado que maneja múltiples fuentes de datos con threads compartidos"""
    
    def __init__(self, sources: list, state: StateManager, sql: SqlRepository, config: dict):
        self.sources = sources
        self.state = state
        self.sql = sql
        self.cfg = config
        self.is_running = True
        self.cycle_count = 0
        self.stats = {src.name: {'downloaded': 0, 'errors': 0, 'processed': 0} for src in sources}

    def run_streaming(self):
        """Modo Servicio Continuo para múltiples fuentes"""
        print(f"\n{'='*70}")
        print(f" MULTI-SOURCE STREAMING SERVICE INICIADO")
        print(f" Fuentes: {', '.join([s.name for s in self.sources])}")
        print(f" Intervalo de polling: {self.cfg['poll_interval']} segundos")
        print(f" Threads compartidos: {self.cfg['threads']}")
        print(f"{'='*70}\n")

        # Setup inicial SQL
        self.sql.init_schema(self.cfg['sql_script_path'])

        try:
            while self.is_running:
                self.cycle_count += 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                print(f"\n{'-'*70}")
                print(f"CICLO #{self.cycle_count} | {now}")
                self._print_stats()
                print(f"{'-'*70}")
                
                # Procesar cada fuente
                any_work_done = False
                for source in self.sources:
                    work_done = self._process_source(source)
                    any_work_done = any_work_done or work_done
                
                if not any_work_done:
                    print(f"Sin archivos nuevos en ninguna fuente. Esperando {self.cfg['poll_interval']}s...")
                
                time.sleep(self.cfg['poll_interval'])

        except KeyboardInterrupt:
            print("\n  Deteniendo servicio ordenadamente...")
            self._print_stats()

    def _print_stats(self):
        """Imprime estadísticas de todas las fuentes"""
        for name, stats in self.stats.items():
            print(f"  {name}: {stats['downloaded']} descargados, "
                  f"{stats['processed']} procesados, {stats['errors']} errores")

    def _process_source(self, source: DataSource) -> bool:
        """Procesa una fuente de datos completa"""
        print(f"\n>>> FUENTE: {source.name} <<<")
        
        # 1. Descarga
        hay_nuevos = self._step_download(source)
        
        # 2. Procesamiento SQL
        if hay_nuevos or self._check_pending_local(source):
            self._step_process_pending(source)
            return True
        else:
            print(f"  Sin novedades en {source.name}")
            return False

    def _step_download(self, source: DataSource):
        """Descarga archivos de una fuente con logging detallado"""
        downloaded_count = 0
        error_count = 0
        
        try:
            files = source.sftp_client.list_files()
            to_download = []
            
            for f in files:
                state_key = f"{source.name}:{f.filename}"
                if self.state.is_new_or_modified(state_key, f.st_mtime, f.st_size):
                    to_download.append(f)

            if to_download:
                total = len(to_download)
                print(f"  DESCARGA: {total} archivos nuevos detectados")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.cfg['threads']) as ex:
                    futures = {
                        ex.submit(source.sftp_client.download_file, f.filename, source.landing_path): f 
                        for f in to_download
                    }
                    
                    for fut in concurrent.futures.as_completed(futures):
                        f_attr = futures[fut]
                        state_key = f"{source.name}:{f_attr.filename}"
                        
                        try:
                            if fut.result():
                                self.state.register_download(state_key, f_attr.st_mtime, f_attr.st_size)
                                downloaded_count += 1
                                if downloaded_count % 10 == 0 or downloaded_count == total:
                                    print(f"    Progreso: {downloaded_count}/{total} OK | Errores: {error_count}")
                            else:
                                error_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f"    ERROR: {str(e)[:80]}")
                
                print(f"  COMPLETADO: {downloaded_count} OK, {error_count} errores de {total}")
                
                self.stats[source.name]['downloaded'] += downloaded_count
                self.stats[source.name]['errors'] += error_count
                
                if error_count > 0:
                    print(f"  NOTA: Archivos fallidos se reintentaran en proximo ciclo")
                    
        except Exception as e:
            print(f"  ERROR CONEXION SFTP: {e}")
        
        return downloaded_count > 0

    def _check_pending_local(self, source: DataSource):
        """Verifica si hay archivos pendientes de procesar"""
        all_files = glob.glob(os.path.join(source.landing_path, "*"))
        for f in all_files:
            state_key = f"{source.name}:{os.path.basename(f)}"
            if self.state.is_pending_sql(state_key):
                return True
        return False

    def _step_process_pending(self, source: DataSource):
        """Procesa archivos pendientes hacia SQL"""
        all_files = glob.glob(os.path.join(source.landing_path, "*"))
        pending = []
        
        for f in all_files:
            state_key = f"{source.name}:{os.path.basename(f)}"
            if self.state.is_pending_sql(state_key):
                pending.append(f)

        if not pending:
            return

        total_pending = len(pending)
        print(f"  PROCESANDO SQL: {total_pending} archivos pendientes")
        
        batch_size = 20
        processed_count = 0
        
        for i in range(0, len(pending), batch_size):
            batch = pending[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total_pending + batch_size - 1) // batch_size
            
            print(f"    Lote {batch_num}/{total_batches}: {len(batch)} archivos...")
            success = self._process_batch(source, batch)
            
            if success:
                processed_count += len(batch)
                print(f"    Lote {batch_num}/{total_batches}: COMPLETADO")
        
        self.stats[source.name]['processed'] += processed_count
        print(f"  SQL COMPLETADO: {processed_count}/{total_pending}")

    def _process_batch(self, source: DataSource, file_paths):
        """Procesa un lote de archivos hacia SQL"""
        dfs = []
        valid_files = []
        
        for fp in file_paths:
            df = source.parser_func(fp)
            if df is not None and not df.empty:
                dfs.append(df)
                valid_files.append(fp)

        if not dfs:
            print(f"      AVISO: No hay datos validos en este lote")
            return False

        full_df = pd.concat(dfs, ignore_index=True)
        
        if self.sql.bulk_insert(full_df, source.staging_table):
            # Procesar SPs SECUENCIALMENTE para evitar deadlocks
            success_count = 0
            error_count = 0
            
            for f in valid_files:
                archivo = os.path.basename(f)
                state_key = f"{source.name}:{archivo}"
                
                if self.sql.execute_sp(source.sp_name, {"ArchivoActual": archivo}):
                    self.state.mark_as_processed_in_sql(state_key)
                    success_count += 1
                else:
                    error_count += 1
            
            if error_count > 0:
                print(f"      RESUMEN: {success_count} OK, {error_count} fallidos (se reintentaran)")
            
            return success_count > 0
        else:
            print(f"      ERROR: Fallo bulk insert")
            return False
