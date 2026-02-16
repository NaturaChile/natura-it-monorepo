"""
MultiSourcePipeline — Orquestador ETL con micro-lotes y DuckDB.

Flujo por fuente:
  1. batch_move_to_processing() → mover archivos a _processing/
  2. DuckDBBatchProcessor.batch_*() → leer + limpiar → PyArrow Tables
  3. SqlRepository.truncate_tables() + bulk_insert_arrow() → cargar staging
  4. SqlRepository.execute_sp() → migrar staging → tablas finales
  5. StateManager.mark_batch_processed() + archive_processed() → cerrar lote
"""

import os
import time
import traceback
from datetime import datetime
from src.adapters.state_manager import StateManager
from src.adapters.sql_repository import SqlRepository
from src.domain.duckdb_batch_processor import DuckDBBatchProcessor


def _log(tag: str, msg: str):
    """Log centralizado con timestamp y etapa."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")


class DataSource:
    """Configuración de una fuente de datos.
    
    Atributos clave:
        name: Identificador de fuente (Cartoning, WaveConfirm, etc.)
        file_client: LocalFileClient con path a la carpeta fuente
        staging_tables: lista de nombres de tablas staging en SQL Server
        sp_name: Stored Procedure que mueve staging → final
        batch_method: nombre del método en DuckDBBatchProcessor
    """
    def __init__(self, name, file_client, staging_tables: list,
                 sp_name: str, batch_method: str):
        self.name = name
        self.file_client = file_client
        self.staging_tables = staging_tables  # Lista uniforme de tablas staging
        self.sp_name = sp_name
        self.batch_method = batch_method  # e.g. 'batch_cartoning'


class MultiSourcePipeline:
    """Pipeline unificado que maneja múltiples fuentes de datos."""

    def __init__(self, sources: list, state: StateManager,
                 sql: SqlRepository, config: dict):
        self.sources = sources
        self.state = state
        self.sql = sql
        self.cfg = config
        self.is_running = True
        self.cycle_count = 0
        self.processor = DuckDBBatchProcessor()
        self.stats = {src.name: {'batches': 0, 'files': 0, 'rows': 0, 'errors': 0}
                      for src in sources}

    def run_streaming(self):
        """Modo Servicio Continuo para múltiples fuentes."""
        print(f"\n{'='*70}")
        print(f" MULTI-SOURCE STREAMING SERVICE v2 (DuckDB)")
        print(f" Fuentes: {', '.join([s.name for s in self.sources])}")
        print(f" Intervalo de polling: {self.cfg['poll_interval']} segundos")
        print(f"{'='*70}\n")

        # Setup inicial SQL
        _log('INIT', 'Etapa 1/2: Inicializando esquema de BD...')
        self.sql.init_schema(self.cfg['sql_script_path'])
        _log('INIT', 'Etapa 2/2: Esquema OK. Entrando en modo streaming...')

        try:
            while self.is_running:
                self.cycle_count += 1
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
                    _log('CICLO', f'Sin archivos nuevos. Ciclo duró {cycle_elapsed:.1f}s. '
                         f'Esperando {self.cfg["poll_interval"]}s...')
                else:
                    _log('CICLO', f'Ciclo completado en {cycle_elapsed:.1f}s. '
                         f'Esperando {self.cfg["poll_interval"]}s...')

                time.sleep(self.cfg['poll_interval'])

        except KeyboardInterrupt:
            _log('SHUTDOWN', 'Deteniendo servicio ordenadamente...')
            self.processor.close()
            self._print_stats()

    def _print_stats(self):
        """Imprime estadísticas de todas las fuentes."""
        _log('STATS', '--- Acumulado global ---')
        total_files = 0
        total_err = 0
        for name, stats in self.stats.items():
            _log('STATS', f'  {name}: {stats["batches"]} lotes, {stats["files"]} archivos, '
                 f'{stats["rows"]} filas, {stats["errors"]} errores')
            total_files += stats['files']
            total_err += stats['errors']
        _log('STATS', f'  TOTAL: {total_files} archivos, {total_err} errores')

    # ─────────────────────────────────────────────────────────────
    #  FLUJO PRINCIPAL POR FUENTE (5 pasos)
    # ─────────────────────────────────────────────────────────────

    def _process_source(self, source: DataSource) -> bool:
        """Procesa una fuente con el flujo micro-lote completo."""
        tag = f'SRC-{source.name[:4].upper()}'

        # PASO 1: Mover archivos nuevos a _processing/
        _log(tag, 'Paso 1/5: batch_move_to_processing...')
        moved_files = source.file_client.batch_move_to_processing()
        if not moved_files:
            _log(tag, 'Sin archivos nuevos.')
            return False

        file_count = len(moved_files)
        _log(tag, f'  → {file_count} archivos movidos a _processing/')

        processing_dir = source.file_client.get_processing_path()

        try:
            # PASO 2: DuckDB batch processing
            _log(tag, f'Paso 2/5: DuckDB {source.batch_method}...')
            t0 = time.time()
            batch_fn = getattr(self.processor, source.batch_method)
            tables = batch_fn(processing_dir)

            if not tables:
                _log(tag, 'WARN: DuckDB retornó sin datos. Limpiando _processing/...')
                source.file_client.cleanup_processing()
                return False

            total_rows = sum(t.num_rows for t in tables.values())
            _log(tag, f'  → {len(tables)} tablas, {total_rows} filas en {time.time()-t0:.2f}s')

            # PASO 3: Truncate staging + Bulk Insert
            _log(tag, 'Paso 3/5: Truncate staging + Bulk Insert Arrow...')
            t0 = time.time()

            if not self.sql.truncate_tables(source.staging_tables):
                _log(tag, 'ERROR CRITICO: No se pudo limpiar staging')
                source.file_client.cleanup_processing()
                self.stats[source.name]['errors'] += 1
                return False

            insert_ok = True
            for tbl_name, arrow_table in tables.items():
                _log(tag, f'  → {tbl_name}: {arrow_table.num_rows} filas')
                if not self.sql.bulk_insert_arrow(arrow_table, tbl_name):
                    _log(tag, f'  ERROR CRITICO: Fallo bulk insert en {tbl_name}')
                    insert_ok = False
                    break

            if not insert_ok:
                source.file_client.cleanup_processing()
                self.stats[source.name]['errors'] += 1
                return False

            _log(tag, f'  Insert OK en {time.time()-t0:.2f}s')

            # PASO 4: Ejecutar SP para cada archivo (secuencial para evitar deadlocks)
            _log(tag, f'Paso 4/5: Ejecutando {source.sp_name} para {file_count} archivos...')
            t0 = time.time()
            sp_ok = 0
            sp_err = 0

            for idx, fname in enumerate(moved_files, 1):
                _log(tag, f'  SP [{idx}/{file_count}]: {fname}')
                t0_sp = time.time()
                if self.sql.execute_sp(source.sp_name, {"ArchivoActual": fname}):
                    sp_ok += 1
                    _log(tag, f'  SP [{idx}/{file_count}]: OK ({time.time()-t0_sp:.2f}s)')
                else:
                    sp_err += 1
                    _log(tag, f'  SP [{idx}/{file_count}]: ERROR ({time.time()-t0_sp:.2f}s)')

            _log(tag, f'  SP Resumen: {sp_ok} OK, {sp_err} errores en {time.time()-t0:.2f}s')

            # PASO 5: Registrar en state + archivar
            _log(tag, 'Paso 5/5: Registrar estado + archivar...')
            self.state.mark_batch_processed(source.name, moved_files)
            source.file_client.archive_processed(moved_files)

            # Actualizar stats
            self.stats[source.name]['batches'] += 1
            self.stats[source.name]['files'] += file_count
            self.stats[source.name]['rows'] += total_rows
            self.stats[source.name]['errors'] += sp_err

            _log(tag, f'Lote completado: {file_count} archivos, {total_rows} filas')
            return True

        except Exception as e:
            _log(tag, f'ERROR NO CONTROLADO: {e}')
            _log(tag, f'  Traceback: {traceback.format_exc()}')
            # Devolver archivos a origen
            source.file_client.cleanup_processing()
            self.stats[source.name]['errors'] += 1
            return False
