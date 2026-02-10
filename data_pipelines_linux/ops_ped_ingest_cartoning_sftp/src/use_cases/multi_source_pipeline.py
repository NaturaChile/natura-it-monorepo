import os
import time
import glob
import traceback
import concurrent.futures
import pandas as pd
from datetime import datetime
from src.adapters.state_manager import StateManager
from src.adapters.sql_repository import SqlRepository
from src.domain.file_parser import FileParser

def _log(tag: str, msg: str):
    """Log centralizado con timestamp y etapa."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")

class DataSource:
    """Configuración de una fuente de datos"""
    def __init__(self, name, file_client, staging_table, sp_name, parser_func, 
                 staging_table_items=None, staging_table_control=None, 
                 staging_table_unidades=None, staging_table_contenido=None, 
                 staging_table_extensiones=None):
        self.name = name
        self.file_client = file_client  # LocalFileClient
        self.staging_table = staging_table
        self.staging_table_items = staging_table_items  # Para OutboundDelivery (2 tablas)
        self.staging_table_control = staging_table_control  # Para OBDConfirm (6 tablas)
        self.staging_table_unidades = staging_table_unidades
        self.staging_table_contenido = staging_table_contenido
        self.staging_table_extensiones = staging_table_extensiones
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
        _log('INIT', 'Etapa 1/2: Inicializando esquema de BD...')
        self.sql.init_schema(self.cfg['sql_script_path'])
        _log('INIT', 'Etapa 2/2: Esquema OK. Entrando en modo streaming...')

        try:
            while self.is_running:
                self.cycle_count += 1
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cycle_start = time.time()
                
                print(f"\n{'='*70}")
                _log('CICLO', f'########## CICLO #{self.cycle_count} ##########')
                self._print_stats()
                print(f"{'='*70}")
                
                # Procesar cada fuente
                any_work_done = False
                for idx, source in enumerate(self.sources, 1):
                    _log('CICLO', f'--- Fuente {idx}/{len(self.sources)}: {source.name} ---')
                    work_done = self._process_source(source)
                    any_work_done = any_work_done or work_done
                
                cycle_elapsed = time.time() - cycle_start
                if not any_work_done:
                    _log('CICLO', f'Sin archivos nuevos. Ciclo duró {cycle_elapsed:.1f}s. Esperando {self.cfg["poll_interval"]}s...')
                else:
                    _log('CICLO', f'Ciclo completado en {cycle_elapsed:.1f}s. Esperando {self.cfg["poll_interval"]}s...')
                
                time.sleep(self.cfg['poll_interval'])

        except KeyboardInterrupt:
            _log('SHUTDOWN', 'Deteniendo servicio ordenadamente...')
            self._print_stats()

    def _print_stats(self):
        """Imprime estadísticas de todas las fuentes"""
        _log('STATS', '--- Acumulado global ---')
        total_proc = 0
        total_err = 0
        for name, stats in self.stats.items():
            _log('STATS', f'  {name}: {stats["processed"]} procesados, {stats["errors"]} errores')
            total_proc += stats['processed']
            total_err += stats['errors']
        _log('STATS', f'  TOTAL: {total_proc} procesados, {total_err} errores')

    def _process_source(self, source: DataSource) -> bool:
        """Procesa una fuente de datos completa"""
        
        # 1. Detectar archivos nuevos/modificados
        _log(f'DETECT-{source.name[:4].upper()}', f'Etapa DETECCION: Buscando archivos nuevos/modificados...')
        pending_files = self._detect_new_files(source)
        
        # 2. Procesamiento SQL directo
        if pending_files:
            _log(f'DETECT-{source.name[:4].upper()}', f'Encontrados {len(pending_files)} archivos pendientes')
            self._process_files(source, pending_files)
            return True
        else:
            _log(f'DETECT-{source.name[:4].upper()}', f'Sin novedades')
            return False

    def _detect_new_files(self, source: DataSource):
        """Detecta archivos nuevos o modificados usando state.json"""
        
        try:
            t0 = time.time()
            all_files = source.file_client.list_files()
            pending = []
            skipped = 0
            
            for file_info in all_files:
                state_key = f"{source.name}:{file_info.filename}"
                
                # Verificar si es nuevo o modificado
                if self.state.is_new_or_modified(state_key, file_info.mtime, file_info.size):
                    pending.append(file_info)
                else:
                    skipped += 1
            
            elapsed = time.time() - t0
            _log(f'DETECT-{source.name[:4].upper()}', 
                 f'  Escaneados: {len(all_files)} total | {len(pending)} nuevos | {skipped} ya procesados ({elapsed:.2f}s)')
            
            return pending
            
        except Exception as e:
            _log(f'DETECT-{source.name[:4].upper()}', f'  ERROR LISTANDO ARCHIVOS: {e}')
            return []
    
    def _process_files(self, source: DataSource, file_list):
        """Procesa archivos directamente desde origen hacia SQL"""
        total = len(file_list)
        tag = f'PROC-{source.name[:4].upper()}'
        _log(tag, f'Etapa PROCESAMIENTO: {total} archivos en lotes de 20')
        
        batch_size = 20
        processed_count = 0
        error_count = 0
        t0_global = time.time()
        
        for i in range(0, len(file_list), batch_size):
            batch = file_list[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size
            
            _log(tag, f'  Lote {batch_num}/{total_batches}: {len(batch)} archivos...')
            t0_batch = time.time()
            success, errors = self._process_batch(source, batch)
            batch_elapsed = time.time() - t0_batch
            
            processed_count += success
            error_count += errors
            
            _log(tag, f'  Lote {batch_num}/{total_batches}: {success} OK, {errors} errores ({batch_elapsed:.1f}s)')
        
        self.stats[source.name]['processed'] += processed_count
        self.stats[source.name]['errors'] += error_count
        
        global_elapsed = time.time() - t0_global
        _log(tag, f'  COMPLETADO: {processed_count}/{total} procesados, {error_count} errores en {global_elapsed:.1f}s')

    def _process_batch(self, source: DataSource, file_list):
        """Procesa un lote de archivos hacia SQL (lectura directa desde origen)"""
        valid_files = []
        tag = f'BATCH-{source.name[:4].upper()}'
        
        # OutboundDeliveryConfirm retorna 6 DataFrames
        if source.staging_table_extensiones:  # Detectar fuente con 6 tablas
            _log(tag, '    Etapa PARSEO: 6 tablas (OBDConfirm)...')
            all_cabecera = []
            all_posiciones = []
            all_control = []
            all_unidades = []
            all_contenido = []
            all_extensiones = []
            parse_errors = 0
            
            for file_info in file_list:
                result = source.parser_func(file_info.full_path)
                if result and result[0] is not None:
                    df_cab, df_pos, df_ctrl, df_uni, df_cont, df_ext = result
                    all_cabecera.append(df_cab)
                    all_posiciones.append(df_pos)
                    all_control.append(df_ctrl)
                    all_unidades.append(df_uni)
                    all_contenido.append(df_cont)
                    all_extensiones.append(df_ext)
                    valid_files.append(file_info)
                else:
                    parse_errors += 1
                    _log(tag, f'    WARN: Parser retornó None para {file_info.filename}')
            
            if parse_errors > 0:
                _log(tag, f'    {parse_errors} archivos con error de parseo')
            
            if not all_cabecera:
                _log(tag, '    SIN DATOS válidos para insertar')
                return 0, len(file_list)
            
            # Insertar las 6 tablas
            _log(tag, '    Etapa BULK INSERT: Insertando en 6 tablas staging...')
            tables = [
                (all_cabecera, source.staging_table),
                (all_posiciones, source.staging_table_items),
                (all_control, source.staging_table_control),
                (all_unidades, source.staging_table_unidades),
                (all_contenido, source.staging_table_contenido),
                (all_extensiones, source.staging_table_extensiones)
            ]
            
            for data_list, table_name in tables:
                full_df = pd.concat(data_list, ignore_index=True)
                _log(tag, f'      -> {table_name}: {len(full_df)} filas')
                if not self.sql.bulk_insert(full_df, table_name):
                    _log(tag, f'      ERROR CRITICO: Fallo bulk insert en {table_name}')
                    return 0, len(file_list)
        
        # OutboundDelivery retorna 2 DataFrames (headers, items)
        elif source.staging_table_items:
            _log(tag, '    Etapa PARSEO: 2 tablas (OutboundDelivery)...')
            all_headers = []
            all_items = []
            parse_errors = 0
            
            for file_info in file_list:
                df_headers, df_items = source.parser_func(file_info.full_path)
                if df_headers is not None and not df_headers.empty:
                    all_headers.append(df_headers)
                    all_items.append(df_items)
                    valid_files.append(file_info)
                else:
                    parse_errors += 1
                    _log(tag, f'    WARN: Parser retornó vacío para {file_info.filename}')
            
            if parse_errors > 0:
                _log(tag, f'    {parse_errors} archivos con error/vacíos')
            
            if not all_headers:
                _log(tag, '    SIN DATOS válidos para insertar')
                return 0, len(file_list)
            
            full_headers = pd.concat(all_headers, ignore_index=True)
            full_items = pd.concat(all_items, ignore_index=True)
            
            _log(tag, f'    Etapa BULK INSERT: Headers={len(full_headers)}, Items={len(full_items)}')
            
            if not self.sql.bulk_insert(full_headers, source.staging_table):
                _log(tag, f'      ERROR CRITICO: Fallo bulk insert en headers')
                return 0, len(file_list)
            
            if not self.sql.bulk_insert(full_items, source.staging_table_items):
                _log(tag, f'      ERROR CRITICO: Fallo bulk insert en items')
                return 0, len(file_list)
        
        # Cartoning / WaveConfirm retornan 1 DataFrame
        else:
            _log(tag, '    Etapa PARSEO: 1 tabla...')
            dfs = []
            parse_errors = 0
            
            for file_info in file_list:
                df = source.parser_func(file_info.full_path)
                if df is not None and not df.empty:
                    dfs.append(df)
                    valid_files.append(file_info)
                else:
                    parse_errors += 1
                    _log(tag, f'    WARN: Parser retornó None/vacío para {file_info.filename}')

            if parse_errors > 0:
                _log(tag, f'    {parse_errors} archivos con error/vacíos')

            if not dfs:
                _log(tag, '    SIN DATOS válidos para insertar')
                return 0, len(file_list)

            full_df = pd.concat(dfs, ignore_index=True)
            
            _log(tag, f'    Etapa BULK INSERT: {len(full_df)} filas -> {source.staging_table}')
            
            if not self.sql.bulk_insert(full_df, source.staging_table):
                _log(tag, f'      ERROR CRITICO: Fallo bulk insert')
                return 0, len(file_list)
        
        # Procesar SPs SECUENCIALMENTE (CRITICO: Evita deadlocks SQL)
        _log(tag, f'    Etapa SP: Ejecutando {source.sp_name} para {len(valid_files)} archivos...')
        success_count = 0
        error_count = 0
        
        for idx, file_info in enumerate(valid_files, 1):
            state_key = f"{source.name}:{file_info.filename}"
            
            _log(tag, f'      SP [{idx}/{len(valid_files)}]: {file_info.filename}')
            t0_sp = time.time()
            
            if self.sql.execute_sp(source.sp_name, {"ArchivoActual": file_info.filename}):
                sp_elapsed = time.time() - t0_sp
                # Registrar en state.json que fue procesado exitosamente
                self.state.register_download(state_key, file_info.mtime, file_info.size)
                self.state.mark_as_processed_in_sql(state_key)
                success_count += 1
                _log(tag, f'      SP [{idx}/{len(valid_files)}]: OK ({sp_elapsed:.2f}s)')
            else:
                sp_elapsed = time.time() - t0_sp
                error_count += 1
                _log(tag, f'      SP [{idx}/{len(valid_files)}]: ERROR ({sp_elapsed:.2f}s) - {file_info.filename}')
        
        _log(tag, f'    Resumen SP: {success_count} OK, {error_count} errores')
        return success_count, error_count
