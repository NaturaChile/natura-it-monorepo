import os
import re
import time
import urllib
from sqlalchemy import create_engine, text
import pandas as pd

class SqlRepository:
    def __init__(self, host, db, user=None, password=None, driver="ODBC Driver 17 for SQL Server"):
        
        # Lógica inteligente: ¿SQL Auth o Windows Auth?
        if user and password:
            # Opción A: Tenemos usuario y contraseña (SQL Authentication)
            print(f"Conectando a SQL Server ({host}) con usuario: {user}")
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={host};"
                f"DATABASE={db};"
                f"UID={user};"
                f"PWD={password};"
                "Encrypt=no;TrustServerCertificate=yes;"  # Útil para servidores locales/antiguos
            )
        else:
            # Opción B: No hay credenciales, usamos la cuenta de servicio de Windows
            print(f"Conectando a SQL Server ({host}) vía Windows Auth...")
            connection_string = (
                f"DRIVER={{{driver}}};"
                f"SERVER={host};"
                f"DATABASE={db};"
                f"Trusted_Connection=yes;"
            )

        # Codificamos la cadena para SQLAlchemy
        params = urllib.parse.quote_plus(connection_string)
        
        # Creamos el engine
        self.engine = create_engine(
            f"mssql+pyodbc:///?odbc_connect={params}", 
            fast_executemany=True
        )

    def init_schema(self, script_path: str):
        # ... (El resto del código sigue igual) ...
        if not os.path.exists(script_path): return
        print("Inicializando esquema de BD...")
        try:
            with open(script_path, 'r', encoding='utf-8') as f: sql = f.read()
            commands = re.split(r'\bGO\b', sql, flags=re.IGNORECASE)
            with self.engine.connect() as conn:
                for cmd in commands:
                    if cmd.strip():
                        conn.execute(text(cmd))
                        conn.commit()
        except Exception as e:
            print(f"Error Schema Init (Info): {e}")

    def bulk_insert(self, df: pd.DataFrame, table_name: str) -> bool:
        try:
            t0 = time.time()
            # method=None para usar fast_executemany por defecto de pandas/sqlalchemy modernos
            df.to_sql(table_name, con=self.engine, if_exists='append', index=False, chunksize=20000)
            print(f"      Insert SQL: {len(df)} filas en {time.time()-t0:.2f}s")
            return True
        except Exception as e:
            print(f"      Error Bulk Insert: {e}")
            return False

    def execute_sp(self, sp_name: str, params: dict):
        try:
            with self.engine.begin() as conn:
                param_str = ", ".join([f"@{k}=:{k}" for k in params.keys()])
                query = text(f"EXEC {sp_name} {param_str}")
                conn.execute(query, params)
            return True
        except Exception as e:
            print(f"      Error SP {sp_name}: {e}")
            return False