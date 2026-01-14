import os
import time
import glob
import concurrent.futures
import pandas as pd
from datetime import datetime
from src.adapters.state_manager import StateManager
from src.adapters.sql_repository import SqlRepository
from src.domain.file_parser import FileParser

class DataSource:
    """Configuración de una fuente de datos"""
    def __init__(self, name, file_client, staging_table, sp_name, parser_func, staging_table_items=None):
        self.name = name
        self.file_client = file_client  # LocalFileClient
        self.staging_table = staging_table
        self.staging_table_items = staging_table_items  # Para OutboundDelivery (2 tablas)
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
        
        # 1. Detectar archivos nuevos/modificados
        pending_files = self._detect_new_files(source)
        
        # 2. Procesamiento SQL directo
        if pending_files:
            self._process_files(source, pending_files)
            return True
        else:
            print(f"  Sin novedades en {source.name}")
            return False

    def _detect_new_files(self, source: DataSource):
        """Detecta archivos nuevos o modificados usando state.json"""
        print(f"  DETECTANDO archivos nuevos/modificados...")
        
        try:
            all_files = source.file_client.list_files()
            pending = []
            
            for file_info in all_files:
                state_key = f"{source.name}:{file_info.filename}"
                
                # Verificar si es nuevo o modificado
                if self.state.is_new_or_modified(state_key, file_info.mtime, file_info.size):
                    pending.append(file_info)
            
            if pending:
                print(f"  DETECTADOS: {len(pending)} archivos para procesar")
            
            return pending
            
        except Exception as e:
            print(f"  ERROR LISTANDO ARCHIVOS: {e}")
            return []
    
    def _process_files(self, source: DataSource, file_list):
        """Procesa archivos directamente desde origen hacia SQL"""
        total = len(file_list)
        print(f"  PROCESANDO: {total} archivos en lotes...")
        
        batch_size = 20
        processed_count = 0
        error_count = 0
        
        for i in range(0, len(file_list), batch_size):
            batch = file_list[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            print(f"    Lote {batch_num}/{total_batches}: {len(batch)} archivos...")
            success, errors = self._process_batch(source, batch)
            
            processed_count += success
            error_count += errors
            
            if success > 0:
                print(f"    Lote {batch_num}/{total_batches}: {success} OK, {errors} errores")
        
        self.stats[source.name]['processed'] += processed_count
        self.stats[source.name]['errors'] += error_count
        
        print(f"  COMPLETADO: {processed_count}/{total} procesados, {error_count} errores")

    def _process_batch(self, source: DataSource, file_list):
        """Procesa un lote de archivos hacia SQL (lectura directa desde origen)"""
        valid_files = []
        
        # OutboundDelivery retorna 2 DataFrames (headers, items)
        if source.staging_table_items:
            all_headers = []
            all_items = []
            
            for file_info in file_list:
                df_headers, df_items = source.parser_func(file_info.full_path)
                if df_headers is not None and not df_headers.empty:
                    all_headers.append(df_headers)
                    all_items.append(df_items)
                    valid_files.append(file_info)
            
            if not all_headers:
                return 0, len(file_list)
            
            full_headers = pd.concat(all_headers, ignore_index=True)
            full_items = pd.concat(all_items, ignore_index=True)
            
            if not self.sql.bulk_insert(full_headers, source.staging_table):
                print(f"      ERROR: Fallo bulk insert en headers")
                return 0, len(file_list)
            
            if not self.sql.bulk_insert(full_items, source.staging_table_items):
                print(f"      ERROR: Fallo bulk insert en items")
                return 0, len(file_list)
        
        # Cartoning / WaveConfirm retornan 1 DataFrame
        else:
            dfs = []
            
            for file_info in file_list:
                df = source.parser_func(file_info.full_path)
                if df is not None and not df.empty:
                    dfs.append(df)
                    valid_files.append(file_info)

            if not dfs:
                return 0, len(file_list)

            full_df = pd.concat(dfs, ignore_index=True)
            
            if not self.sql.bulk_insert(full_df, source.staging_table):
                print(f"      ERROR: Fallo bulk insert")
                return 0, len(file_list)
        
        # Procesar SPs SECUENCIALMENTE (CRITICO: Evita deadlocks SQL)
        success_count = 0
        error_count = 0
        
        for file_info in valid_files:
            state_key = f"{source.name}:{file_info.filename}"
            
            if self.sql.execute_sp(source.sp_name, {"ArchivoActual": file_info.filename}):
                # Registrar en state.json que fue procesado exitosamente
                self.state.register_download(state_key, file_info.mtime, file_info.size)
                self.state.mark_as_processed_in_sql(state_key)
                success_count += 1
            else:
                error_count += 1
        
        return success_count, error_count
