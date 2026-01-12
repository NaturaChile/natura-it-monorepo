import os
import re
import time
import urllib
from sqlalchemy import create_engine, text
import pandas as pd

class SqlRepository:
    def __init__(self, host, db, driver="ODBC Driver 17 for SQL Server"):
        params = urllib.parse.quote_plus(
            f"DRIVER={{{driver}}};SERVER={host};DATABASE={db};Trusted_Connection=yes;"
        )
        self.engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)

    def init_schema(self, script_path: str):
        if not os.path.exists(script_path): return
        print("  Inicializando esquema de BD...")
        try:
            with open(script_path, 'r', encoding='utf-8') as f: sql = f.read()
            # Split por GO
            commands = re.split(r'\bGO\b', sql, flags=re.IGNORECASE)
            with self.engine.connect() as conn:
                for cmd in commands:
                    if cmd.strip():
                        conn.execute(text(cmd))
                        conn.commit()
        except Exception as e:
            print(f" Error Schema Init (Puede que ya exista): {e}")

    def bulk_insert(self, df: pd.DataFrame, table_name: str) -> bool:
        try:
            t0 = time.time()
            df.to_sql(table_name, con=self.engine, if_exists='append', index=False, chunksize=20000)
            print(f"        Insert SQL: {len(df)} filas en {time.time()-t0:.2f}s")
            return True
        except Exception as e:
            print(f"       Error Bulk Insert: {e}")
            return False

    def execute_sp(self, sp_name: str, params: dict):
        try:
            with self.engine.begin() as conn:
                # Construcción dinámica simple de SP
                param_str = ", ".join([f"@{k}=:{k}" for k in params.keys()])
                query = text(f"EXEC {sp_name} {param_str}")
                conn.execute(query, params)
            return True
        except Exception as e:
            print(f"       Error SP {sp_name}: {e}")
            return False