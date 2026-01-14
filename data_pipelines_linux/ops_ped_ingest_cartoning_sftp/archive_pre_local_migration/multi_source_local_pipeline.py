import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class DataSource:
    """Configuración de fuente de datos"""
    name: str
    file_client: Any  # LocalFileClient o SftpClient
    landing_path: str
    staging_table: str
    sp_name: str
    parser_func: Callable
    staging_table_items: str = None  # Para Outbound Delivery (segunda tabla)

class MultiSourceLocalPipeline:
    """Pipeline unificado que procesa múltiples fuentes desde carpetas locales"""
    
    def __init__(self, sources, state_adapter, sql_adapter, config):
        self.sources = sources
        self.state_manager = state_adapter
        self.sql_repo = sql_adapter
        self.max_workers = config.get('threads', 2)
        self.sleep_seconds = config.get('sleep_seconds', 300)
        
    def run_streaming(self):
        """Ejecutar pipeline en modo streaming (ciclo infinito)"""
        print(f"===== Iniciando Pipeline Multi-Fuente (LOCAL) =====")
        print(f"Fuentes: {[s.name for s in self.sources]}")
        print(f"Threads compartidos: {self.max_workers}")
        print(f"Intervalo: {self.sleep_seconds}s")
        print("=" * 60)
        
        while True:
            try:
                self._run_single_cycle()
                print(f"\n--- Esperando {self.sleep_seconds}s para el proximo ciclo ---\n")
                time.sleep(self.sleep_seconds)
                
            except KeyboardInterrupt:
                print("\n--- Pipeline detenido manualmente ---")
                break
            except Exception as e:
                print(f"ERROR CRITICO en ciclo: {e}")
                time.sleep(60)
    
    def _run_single_cycle(self):
        """Ejecutar un ciclo completo de procesamiento"""
        print(f"\n{'='*60}")
        print(f"INICIO DE CICLO - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
        
        # PASO 1: Descarga paralela (thread pool compartido)
        all_new_files = self._step_download()
        
        # PASO 2: Procesar cada fuente secuencialmente
        for source in self.sources:
            source_files = [f for f in all_new_files if f['source_name'] == source.name]
            if source_files:
                self._process_source(source, source_files)
        
        print(f"\n{'='*60}")
        print(f"FIN DE CICLO - {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")
    
    def _step_download(self):
        """Paso 1: Descarga concurrente de todas las fuentes"""
        print("\n--- PASO 1: DESCARGA DE ARCHIVOS ---")
        
        all_new_files = []
        download_tasks = []
        
        # Preparar tareas de descarga
        for source in self.sources:
            try:
                remote_files = source.file_client.list_files()
                print(f"[{source.name}] Archivos remotos: {len(remote_files)}")
                
                for file_info in remote_files:
                    state_key = f"{source.name}:{file_info.filename}"
                    
                    if self.state_manager.is_new_or_modified(state_key, file_info.mtime, file_info.size):
                        download_tasks.append({
                            'source': source,
                            'file_info': file_info,
                            'state_key': state_key
                        })
                        
            except Exception as e:
                print(f"[{source.name}] Error listando archivos: {e}")
        
        if not download_tasks:
            print("No hay archivos nuevos en ninguna fuente.")
            return []
        
        print(f"\nArchivos nuevos detectados: {len(download_tasks)}")
        print("Descargando en paralelo...")
        
        # Descargar en paralelo
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_task = {
                executor.submit(self._download_single_file, task): task 
                for task in download_tasks
            }
            
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    if result:
                        all_new_files.append(result)
                except Exception as e:
                    print(f"[{task['source'].name}] Error en descarga: {e}")
        
        print(f"\nDescargados exitosamente: {len(all_new_files)} archivos")
        return all_new_files
    
    def _download_single_file(self, task):
        """Descargar un archivo individual"""
        source = task['source']
        file_info = task['file_info']
        state_key = task['state_key']
        
        local_path = os.path.join(source.landing_path, file_info.filename)
        
        if source.file_client.download_file(file_info.filename, local_path):
            self.state_manager.register_download(state_key, file_info.mtime, file_info.size)
            print(f"[{source.name}] OK: {file_info.filename}")
            return {
                'source_name': source.name,
                'filename': file_info.filename,
                'local_path': local_path,
                'state_key': state_key
            }
        return None
    
    def _process_source(self, source, files):
        """Procesar archivos de una fuente específica"""
        print(f"\n--- PROCESANDO: {source.name} ({len(files)} archivos) ---")
        
        stats = {'ok': 0, 'err': 0}
        
        for file_data in files:
            try:
                # Parse
                if source.staging_table_items:  # Outbound Delivery (2 tablas)
                    df_headers, df_items = source.parser_func(file_data['local_path'])
                    
                    if df_headers is None or df_items is None:
                        print(f"[{source.name}] ERROR PARSE: {file_data['filename']}")
                        stats['err'] += 1
                        continue
                    
                    # Insert en staging (2 tablas)
                    self.sql_repo.bulk_insert(source.staging_table, df_headers)
                    self.sql_repo.bulk_insert(source.staging_table_items, df_items)
                    
                else:  # Cartoning / WaveConfirm (1 tabla)
                    df = source.parser_func(file_data['local_path'])
                    
                    if df is None or df.empty:
                        print(f"[{source.name}] ERROR PARSE: {file_data['filename']}")
                        stats['err'] += 1
                        continue
                    
                    # Insert en staging
                    self.sql_repo.bulk_insert(source.staging_table, df)
                
                # Ejecutar SP
                self.sql_repo.execute_sp(source.sp_name, file_data['filename'])
                
                # Marcar como procesado
                self.state_manager.mark_as_processed_in_sql(file_data['state_key'])
                stats['ok'] += 1
                
            except Exception as e:
                print(f"[{source.name}] ERROR SQL: {file_data['filename']} - {e}")
                stats['err'] += 1
        
        print(f"[{source.name}] Resultado: {stats['ok']} OK | {stats['err']} Errores")
