"""
SqlRepository — Adaptador SQL Server con soporte PyArrow + pandas.

Mejoras FASE 3:
  - bulk_insert_arrow(): bulk insert directo desde PyArrow Table (zero-copy → pandas)
  - truncate_tables(): limpia staging antes de insertar nuevo lote
  - Mantiene bulk_insert() legacy para retrocompatibilidad
"""

import os
import re
import time
import traceback
import urllib
from datetime import datetime
from sqlalchemy import create_engine, text
import pandas as pd

try:
    import pyarrow as pa
    HAS_PYARROW = True
except ImportError:
    HAS_PYARROW = False


def _log(tag: str, msg: str):
    """Log centralizado con timestamp y etapa."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")


class SqlRepository:
    def __init__(self, host, db, user=None, password=None, driver="ODBC Driver 17 for SQL Server"):

        # Lógica inteligente: ¿SQL Auth o Windows Auth?
        if user and password:
            _log('SQL-CONN', f'Conectando a {host}/{db} con usuario: {user}')
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={host};"
                f"DATABASE={db};"
                f"UID={user};"
                f"PWD={password};"
                "Encrypt=no;TrustServerCertificate=yes;"
            )
        else:
            _log('SQL-CONN', f'Conectando a {host}/{db} vía Windows Auth...')
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={host};"
                f"DATABASE={db};"
                f"Trusted_Connection=yes;"
            )

        params = urllib.parse.quote_plus(connection_string)

        self.engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={params}",
            fast_executemany=True
        )

        # Verificar conectividad
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                result.fetchone()
            _log('SQL-CONN', 'Conexión verificada OK')
        except Exception as e:
            _log('SQL-CONN', f'ERROR verificando conexión: {e}')

    def init_schema(self, script_path: str):
        if not os.path.exists(script_path):
            _log('SQL-SCHEMA', f'WARN: Script no encontrado: {script_path}')
            return
        _log('SQL-SCHEMA', f'Ejecutando setup_database.sql...')
        t0 = time.time()
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            commands = re.split(r'\bGO\b', sql, flags=re.IGNORECASE)
            executed = 0
            with self.engine.connect() as conn:
                for cmd in commands:
                    if cmd.strip():
                        conn.execute(text(cmd))
                        conn.commit()
                        executed += 1
            _log('SQL-SCHEMA', f'Schema OK: {executed} bloques ejecutados en {time.time()-t0:.2f}s')
        except Exception as e:
            _log('SQL-SCHEMA', f'ERROR Schema Init: {e}')

    # ─────────────────────────────────────────────────────────────
    #  BULK INSERT: PyArrow (nuevo) y pandas (legacy)
    # ─────────────────────────────────────────────────────────────

    def bulk_insert_arrow(self, arrow_table: 'pa.Table', table_name: str) -> bool:
        """Inserta un PyArrow Table en SQL Server.

        Convierte Arrow → pandas (zero-copy cuando es posible) y usa
        fast_executemany para máximo throughput.
        """
        try:
            t0 = time.time()
            rows = arrow_table.num_rows
            cols = arrow_table.column_names
            _log('SQL-INSERT', f'[Arrow] Insertando {rows} filas en {table_name} (cols: {", ".join(cols)})')

            # Arrow → pandas con tipos nativos (zero-copy para strings)
            df = arrow_table.to_pandas(
                types_mapper=pd.ArrowDtype,
                self_destruct=True,      # Libera buffers Arrow conforme convierte
                split_blocks=True,        # Optimiza memoria
            )

            # Normalizar NaN/None a None para SQL
            df = df.where(df.notna(), None)

            df.to_sql(table_name, con=self.engine, if_exists='append',
                      index=False, chunksize=20000)
            elapsed = time.time() - t0
            rate = rows / elapsed if elapsed > 0 else 0
            _log('SQL-INSERT', f'[Arrow] OK: {rows} filas en {table_name} ({elapsed:.2f}s, {rate:.0f} filas/s)')
            return True

        except Exception as e:
            _log('SQL-INSERT', f'[Arrow] ERROR en {table_name}: {e}')
            _log('SQL-INSERT', f'  Schema Arrow: {arrow_table.schema}')
            _log('SQL-INSERT', f'  Traceback: {traceback.format_exc()}')
            return False

    def bulk_insert(self, df: pd.DataFrame, table_name: str) -> bool:
        """Inserta un pandas DataFrame en SQL Server (legacy)."""
        try:
            t0 = time.time()
            rows = len(df)
            cols = list(df.columns)
            _log('SQL-INSERT', f'Insertando {rows} filas en {table_name} (cols: {", ".join(cols)})')

            # Detectar posibles problemas antes del insert
            for col in cols:
                max_len = df[col].astype(str).str.len().max() if not df[col].isna().all() else 0
                null_count = df[col].isna().sum()
                if max_len > 400:
                    _log('SQL-INSERT', f'  WARN: {col} tiene valor máx de {max_len} chars')
                if null_count == rows:
                    _log('SQL-INSERT', f'  INFO: {col} es 100% NULL')

            df.to_sql(table_name, con=self.engine, if_exists='append', index=False, chunksize=20000)
            elapsed = time.time() - t0
            rate = rows / elapsed if elapsed > 0 else 0
            _log('SQL-INSERT', f'OK: {rows} filas en {table_name} ({elapsed:.2f}s, {rate:.0f} filas/s)')
            return True
        except Exception as e:
            _log('SQL-INSERT', f'ERROR bulk insert en {table_name}: {e}')
            _log('SQL-INSERT', f'  Columnas del DataFrame: {list(df.columns)}')
            _log('SQL-INSERT', f'  Dtypes: {df.dtypes.to_dict()}')
            _log('SQL-INSERT', f'  Primeras 2 filas: {df.head(2).to_dict()}')
            return False

    # ─────────────────────────────────────────────────────────────
    #  TRUNCATE STAGING (limpiar antes de cada lote)
    # ─────────────────────────────────────────────────────────────

    def truncate_tables(self, table_names: list) -> bool:
        """Limpia tablas staging antes de insertar nuevo lote.
        
        Usa TRUNCATE TABLE para velocidad; cae a DELETE si no tiene permisos.
        """
        try:
            with self.engine.begin() as conn:
                for tbl in table_names:
                    try:
                        conn.execute(text(f"TRUNCATE TABLE {tbl}"))
                    except Exception:
                        conn.execute(text(f"DELETE FROM {tbl}"))
                    _log('SQL-TRUNC', f'Limpiada: {tbl}')
            return True
        except Exception as e:
            _log('SQL-TRUNC', f'ERROR truncando staging: {e}')
            return False

    # ─────────────────────────────────────────────────────────────
    #  EXECUTE STORED PROCEDURE
    # ─────────────────────────────────────────────────────────────

    def execute_sp(self, sp_name: str, params: dict):
        try:
            t0 = time.time()
            _log('SQL-SP', f'Ejecutando {sp_name} con params: {params}')
            with self.engine.begin() as conn:
                param_str = ", ".join([f"@{k}=:{k}" for k in params.keys()])
                query = text(f"EXEC {sp_name} {param_str}")
                conn.execute(query, params)
            elapsed = time.time() - t0
            _log('SQL-SP', f'OK: {sp_name} completado en {elapsed:.2f}s')
            return True
        except Exception as e:
            elapsed = time.time() - t0
            _log('SQL-SP', f'ERROR en {sp_name} ({elapsed:.2f}s): {e}')
            _log('SQL-SP', f'  Traceback: {traceback.format_exc()}')
            return False