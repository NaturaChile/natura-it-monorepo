"""Logica de transaccion MB52 - Stock de almacen."""
import time
import os
import shutil
from datetime import datetime
import pandas as pd
import io

# Usar helper central para secretos/variables de entorno
from core_shared.security.vault import Vault

# --- CONFIGURACIÓN ---
# 1. DATOS DE CONEXIÓN (directos, sin importar variables externas)
SERVER_IP = "10.156.145.28"
RECURSO = "areas"
SUB_RUTA_DESTINO = r"Publico\RPA\Retail\Stock - Base Tiendas"

DOMAIN = "NATURA"
USER = "robotch_fin"
PASSWORD = "Natura@bot2025/"
USER_FULL = f"{DOMAIN}\\{USER}"


def ejecutar_mb52(session, centro: str = "4100", almacen: str = "4161", variante: str = "BOTMB52", ruta_destino: str = r"\\10.156.145.28\Publico\RPA\Retail\Stock - Base Tiendas"):
    """
    Ejecuta la transaccion MB52 y exporta el resultado a Excel via portapapeles.
    
    Args:
        session: Sesion SAP activa
        centro: Centro logistico (default: 4100)
        almacen: Almacen (default: 4161)
        variante: Variante de reporte (default: BOTMB52)
        ruta_destino: Ruta UNC donde guardar el archivo Excel (usar \\\\servidor\\... no letras de unidad)
    
    Returns:
        str: Ruta completa del archivo generado
    """
    # Generar nombre de archivo con fecha
    fecha_actual = datetime.now().strftime("%Y.%m.%d")
    nombre_archivo = f"Base Stock Tiendas {fecha_actual}.xlsx"
    
    print(f"[MB52] Centro: {centro}")

    print(f"[MB52] Almacen: {almacen}")
    print(f"[MB52] Variante: {variante}")
    print(f"[MB52] Archivo destino: {ruta_destino}\\{nombre_archivo}")
    
    try:
        # 1. Limpiar pantalla inicial
        print("[MB52] Paso 1: Preparando pantalla...")
        session.findById("wnd[0]/tbar[0]/okcd").text = "MB52"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)
        
        # 2. Llenar campos de seleccion
        print("[MB52] Paso 2: Llenando campos de seleccion...")
        session.findById("wnd[0]/usr/ctxtWERKS-LOW").text = centro
        session.findById("wnd[0]/usr/ctxtLGORT-HIGH").text = "4195"
        session.findById("wnd[0]/usr/ctxtLGORT-LOW").text = almacen
        session.findById("wnd[0]/usr/ctxtP_VARI").text = variante
        session.findById("wnd[0]/usr/ctxtP_VARI").setFocus()
        session.findById("wnd[0]/usr/ctxtP_VARI").caretPosition = len(variante)
        time.sleep(0.3)
        
        # 3. Ejecutar con Enter
        print("[MB52] Paso 3: Ejecutando variante...")
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(1)
        
        # 4. Ejecutar reporte (F8)
        print("[MB52] Paso 4: Ejecutando reporte (F8)...")
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        time.sleep(3)  # Esperar a que cargue el reporte
        
        # 5. Exportar menu
        print("[MB52] Paso 5: Iniciando exportacion...")
        session.findById("wnd[0]/tbar[1]/btn[45]").press()
        time.sleep(1)
        
        # 6. Seleccionar formato de exportacion (Portapapeles)
        print("[MB52] Paso 6: Seleccionando formato Portapapeles...")
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[4,0]").select()
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[4,0]").setFocus()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        time.sleep(2)
        
        # 7. Leer portapapeles y procesar datos
        print("[MB52] Paso 7: Leyendo datos del portapapeles...")
        import win32clipboard
        
        win32clipboard.OpenClipboard()
        try:
            clipboard_data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        
        print(f"[MB52] Datos recibidos del portapapeles: {len(clipboard_data)} caracteres")
        
        # 8. Procesar datos y crear DataFrame
        print("[MB52] Paso 8: Procesando y limpiando datos...")
        lines = clipboard_data.strip().split('\n')
        print(f"[MB52] Total lineas en portapapeles: {len(lines)}")
        
        # Estructura del portapapeles SAP:
        # Linea 0: ---- separador de guiones
        # Linea 1: | Col1 | Col2 | ... | (headers)
        # Linea 2: ---- separador de guiones
        # Linea 3+: | dato1 | dato2 | ... | (datos)
        
        # Separar lineas de datos de lineas de guiones
        header_line = None
        data_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Ignorar lineas vacias o que sean solo guiones
            if not stripped or stripped.replace('-', '').replace('|', '').strip() == '':
                continue
            # Si contiene | y no es solo guiones, es una linea de datos
            if '|' in stripped:
                if header_line is None:
                    header_line = stripped
                else:
                    data_lines.append(stripped)
        
        if header_line is None:
            raise ValueError("No se encontro linea de encabezados en el portapapeles")
        
        # Extraer headers (separar por | y limpiar)
        headers = [col.strip() for col in header_line.split('|')]
        # Eliminar elementos vacios al inicio y final
        headers = [h for h in headers if h]
        print(f"[MB52] Columnas detectadas ({len(headers)}): {headers[:5]}...")
        
        # Procesar filas de datos
        data_rows = []
        for line in data_lines:
            # Separar por | y limpiar espacios
            row = [col.strip() for col in line.split('|')]
            # Eliminar elementos vacios al inicio y final
            row = [r for r in row if r != '']
            
            if len(row) == len(headers):
                data_rows.append(row)
            elif len(row) > 0:
                print(f"[MB52] [WARN] Fila con {len(row)} cols (esperadas {len(headers)}), ajustando...")
                # Ajustar fila si es necesario
                if len(row) > len(headers):
                    data_rows.append(row[:len(headers)])
                else:
                    # Rellenar con vacios
                    row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row)
        
        print(f"[MB52] Filas de datos procesadas: {len(data_rows)}")
        
        # Crear DataFrame
        df = pd.DataFrame(data_rows, columns=headers)

        # DEBUG: mostrar columnas y primeras 3 filas ANTES de renombrar
        try:
            print(f"[MB52 DEBUG] Headers raw: {headers}")
            for r in data_rows[:3]:
                print("[MB52 DEBUG BEFORE] " + ";".join(r))
        except Exception as e:
            print(f"[MB52 DEBUG] Error mostrando muestras antes: {e}")

        # --- Limpiar y normalizar nombres de columna (trim) ---
        cleaned_cols = [str(c).strip() for c in df.columns]
        df.columns = cleaned_cols
        print(f"[MB52] Columnas limpias: {df.columns.tolist()[:20]}...")

        # Mapeo explícito de nombres originales a nombres objetivo (priority explicit matches)
        explicit_map = {
            'material': ['material'],
            'ce.': ['centro'],
            'ce': ['centro'],
            'alm.': ['almacen'],
            'alm': ['pb_a_nivel_almacen'],
            'lote': ['lote'],
            'um': ['unidad_medida_base'],
            'libre utiliz.': ['libre_utilizacion'],
            'libre utiliz': ['libre_utilizacion'],
            'mon.': ['moneda'],
            'mon': ['moneda'],
            'valor total': ['valor_libre_util', 'valor_stock_bloq'],  # may appear twice
            'transytras': ['trans_trasl'],
            'val.trans.c/cond.': ['val_trans_cond'],
            'val.trans.c/cond': ['val_trans_cond'],
            'en ctrlcal': ['en_control_calidad'],
            'valor en insp.cal.': ['valor_en_insp_cal'],
            'valor en insp.cal': ['valor_en_insp_cal'],
            'stock no libre': ['stock_no_libre'],
            'valor no libre': ['valor_no_libre'],
            'bloqueado': ['bloqueado'],
            'devol.': ['devoluciones'],
            'devol': ['devoluciones'],
            'val.stock bl.dev.': ['val_stock_bl_dev'],
            'val.stock bl.dev': ['val_stock_bl_dev'],
            'texto breve de material': ['texto_breve_material'],
            'denom-almacén': ['denominacion_almacen'],
            'denominacion almacen': ['denominacion_almacen'],
            'denominacion-almacen': ['denominacion_almacen']
        }

        def key_for_exact(s: str) -> str:
            return s.strip().lower()

        from collections import defaultdict
        count_by_key = defaultdict(int)
        occurrences = defaultdict(int)
        for col in df.columns:
            occurrences[key_for_exact(col)] += 1

        renames = {}
        # Map by position-aware strategy: if a key has multiple targets and multiple occurrences, distribute them in order; if single occurrence, prefer first target
        for col in df.columns.tolist():
            k = key_for_exact(col)
            mapped = None
            if k in explicit_map:
                targets = explicit_map[k]
                if occurrences[k] == 1 and len(targets) > 1:
                    mapped = targets[0]
                else:
                    mapped = targets[count_by_key[k]] if count_by_key[k] < len(targets) else targets[-1]
                count_by_key[k] += 1
            else:
                nk = normalize_col(col)
                if nk in [ 'material','centro','almacen','pb_a_nivel_almacen','lote','unidad_medida_base','libre_utilizacion','moneda','valor_libre_util','trans_trasl','val_trans_cond','en_control_calidad','valor_en_insp_cal','stock_no_libre','valor_no_libre','bloqueado','valor_stock_bloq','devoluciones','val_stock_bl_dev','texto_breve_material','denominacion_almacen' ]:
                    mapped = nk
            if mapped and col != mapped:
                renames[col] = mapped

        if renames:
            df = df.rename(columns=renames)
            for o, n in renames.items():
                print(f"[MB52] Renombrada columna: '{o}' -> '{n}'")

        # Detectar nombres duplicados y hacerlos unicos por posicion si existen (añadir sufijo __1, __2)
        cols = list(df.columns)
        seen = {}
        for i, c in enumerate(cols):
            if c in seen:
                seen[c] += 1
                newc = f"{c}__{seen[c]}"
                cols[i] = newc
                print(f"[MB52] [WARN] Nombre de columna duplicado detectado: '{c}' -> renombrado a '{newc}' para evitar ambiguedad")
            else:
                seen[c] = 0
        df.columns = cols

        # Reordenar/asegurar columnas objetivo
        required_cols = [
            'material','centro','almacen','pb_a_nivel_almacen','lote',
            'unidad_medida_base','libre_utilizacion','moneda','valor_libre_util',
            'trans_trasl','val_trans_cond','en_control_calidad','valor_en_insp_cal',
            'stock_no_libre','valor_no_libre','bloqueado','valor_stock_bloq',
            'devoluciones','val_stock_bl_dev','texto_breve_material','denominacion_almacen'
        ]
        for c in required_cols:
            if c not in df.columns:
                df[c] = None
        df = df[[c for c in required_cols]]

        # DEBUG: mostrar columnas y primeras 3 filas DESPUES de renombrar/reordenar
        try:
            print(f"[MB52 DEBUG] Columns after rename: {df.columns.tolist()}")
            print('[MB52 DEBUG AFTER] ')
            print(df.head(3).to_csv(sep=';', index=False, header=False))
        except Exception as e:
            print(f"[MB52 DEBUG] Error mostrando muestras despues: {e}")

        # 9. Procesar DataFrame y cargar en SQL
        print("[MB52] Paso 9: Procesando DataFrame para carga en SQL...")

        # Columnas objetivo (snake_case)
        COLUMNAS = [
            'material', 'centro', 'almacen', 'pb_a_nivel_almacen', 'lote', 
            'unidad_medida_base', 'libre_utilizacion', 'moneda', 'valor_libre_util', 
            'trans_trasl', 'val_trans_cond', 'en_control_calidad', 
            'valor_en_insp_cal', 'stock_no_libre', 'valor_no_libre', 
            'bloqueado', 'valor_stock_bloq', 'devoluciones', 'val_stock_bl_dev', 
            'texto_breve_material', 'denominacion_almacen'
        ]

        from sqlalchemy import BigInteger, Text, Numeric, text

        STOCK_DTYPE = {
            'material': BigInteger(),
            'centro': BigInteger(),
            'almacen': BigInteger(),
            'pb_a_nivel_almacen': Text(),
            'lote': Text(),
            'unidad_medida_base': Text(),
            'moneda': Text(),
            'texto_breve_material': Text(),
            'denominacion_almacen': Text(),
            'libre_utilizacion': Numeric(18, 2),
            'valor_libre_util': Numeric(18, 2),
            'trans_trasl': Numeric(18, 2),
            'val_trans_cond': Numeric(18, 2),
            'en_control_calidad': Numeric(18, 2),
            'valor_en_insp_cal': Numeric(18, 2),
            'stock_no_libre': Numeric(18, 2),
            'valor_no_libre': Numeric(18, 2),
            'bloqueado': Numeric(18, 2),
            'valor_stock_bloq': Numeric(18, 2),
            'devoluciones': Numeric(18, 2),
            'val_stock_bl_dev': Numeric(18, 2)
        }

        def normalize_col(c: str) -> str:
            c = str(c).strip().lower()
            c = c.replace('-', ' ').replace('/', ' ')
            c = ''.join(ch if ch.isalnum() or ch == ' ' else '_' for ch in c)
            c = '_'.join(c.split())
            return c

        # Intentar asignar nombres objetivo
        if len(df.columns) == len(COLUMNAS):
            df.columns = COLUMNAS
        else:
            cols_map = {}
            normalized = {normalize_col(c): c for c in df.columns}
            for target in COLUMNAS:
                if target in normalized:
                    cols_map[normalized[target]] = target
            df = df.rename(columns=cols_map)
            # Añadir columnas faltantes con nulls
            for c in COLUMNAS:
                if c not in df.columns:
                    df[c] = None
            # Reordenar
            df = df[[c for c in COLUMNAS]]

        # Convertir dtypes básicos
        for int_col in ['material', 'centro', 'almacen']:
            if int_col in df.columns:
                df[int_col] = pd.to_numeric(df[int_col], errors='coerce').astype('Int64')

        numeric_cols = [
            'libre_utilizacion','valor_libre_util','trans_trasl','val_trans_cond',
            'en_control_calidad','valor_en_insp_cal','stock_no_libre','valor_no_libre',
            'bloqueado','valor_stock_bloq','devoluciones','val_stock_bl_dev'
        ]
        for c in numeric_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).str.replace(',', '.'), errors='coerce')

        # Texto
        for t in ['pb_a_nivel_almacen','lote','unidad_medida_base','moneda','texto_breve_material','denominacion_almacen']:
            if t in df.columns:
                df[t] = df[t].astype(str).replace('nan', None)

        # Añadir timestamp de ingestion
        df['timestamp_ingestion'] = datetime.now()

        # Obtener credenciales **desde Vault** (Environment: SAP_Jorge) — fallback a env solo con advertencia
        print('[MB52] Intentando leer credenciales SQL2022_* desde Vault...')
        db_host = Vault.get_secret('SQL2022_HOST')
        db_user = Vault.get_secret('SQL2022_USER')
        db_pw = Vault.get_secret('SQL2022_PW')
        db_name = os.getenv('SQL2022_DB', 'Retail')

        # Si Vault no tiene los secretos, fallback a variables de entorno con WARNING
        if not (db_host and db_user and db_pw):
            env_host = os.getenv('SQL2022_HOST')
            env_user = os.getenv('SQL2022_USER')
            env_pw = os.getenv('SQL2022_PW')
            if env_host or env_user or env_pw:
                print('[MB52] [WARN] Secrets SQL2022_* no encontrados en Vault. Usando variables de entorno para esta ejecución. **Por favor cargue los secrets en Vault (Environment: SAP_Jorge)**')
                db_host = db_host or env_host
                db_user = db_user or env_user
                db_pw = db_pw or env_pw
            else:
                raise Exception('Secrets SQL2022_* no encontrados en Vault ni en variables de entorno. Agregue los secrets en Vault (Environment: SAP_Jorge)')

        print(f"[MB52] Conectando a SQL Server {db_host} DB {db_name} como {db_user}")

        # SqlRepository local (implementación propia dentro del bot)
        from sqlalchemy import create_engine
        import urllib

        class SqlRepository:
            def __init__(self, host, db, user=None, password=None, driver=None):
                # Detectar driver disponible si no se especifica
                preferred = [
                    'ODBC Driver 18 for SQL Server',
                    'ODBC Driver 17 for SQL Server',
                    'ODBC Driver 13 for SQL Server',
                    'SQL Server Native Client 11.0',
                    'SQL Server'
                ]
                selected_driver = driver
                try:
                    import pyodbc
                    available = pyodbc.drivers()
                    # Buscar el primer preferido que esté disponible
                    if not selected_driver:
                        for d in preferred:
                            if d in available:
                                selected_driver = d
                                break
                    if not selected_driver:
                        # No se encontró driver preferido
                        raise RuntimeError(f"No se encontró un driver ODBC compatible. Drivers instalados: {available}")
                except Exception as e:
                    # Si pyodbc no está disponible o no hay drivers, fallamos con mensaje claro
                    raise RuntimeError(f"Error detectando drivers ODBC: {e}")

                print(f"[MB52] [INFO] Usando driver ODBC: {selected_driver}")

                if user and password:
                    print(f"[MB52] [INFO] Conectando a SQL Server {host} con usuario {user}")
                    connection_string = (
                        f"DRIVER={{{selected_driver}}};"
                        f"SERVER={host};"
                        f"DATABASE={db};"
                        f"UID={user};"
                        f"PWD={password};"
                        "Encrypt=no;TrustServerCertificate=yes;"
                    )
                else:
                    print(f"[MB52] [INFO] Conectando a SQL Server {host} usando Windows Auth")
                    connection_string = (
                        f"DRIVER={{{selected_driver}}};"
                        f"SERVER={host};"
                        f"DATABASE={db};"
                        "Trusted_Connection=yes;"
                    )
                params = urllib.parse.quote_plus(connection_string)
                try:
                    self.engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)
                except Exception as e:
                    raise RuntimeError(f"Error creando engine SQLAlchemy/pyodbc: {e}\nAsegure que el driver ODBC '{selected_driver}' esté instalado en el runner y que 'pyodbc' esté disponible en el entorno Python.")

        repo = SqlRepository(host=db_host, db=db_name, user=db_user, password=db_pw)

        # Cargar en tabla temporal y luego reemplazar tabla destino en transaccion
        table_schema = 'Retail'
        table_name = 'stock_tienda'

        try:
            with repo.engine.begin() as conn:
                tmp_table = '#tmp_stock'
                # Cargar a tabla temporal (se creara en la misma conexion)
                print('[MB52] Creando tabla temporal y cargando datos...')
                df.to_sql(tmp_table, con=conn, if_exists='replace', index=False)

                # Verificar filas cargadas
                r = conn.execute(text("SELECT COUNT(1) FROM #tmp_stock")).fetchone()[0]
                print(f"[MB52] Filas en temp: {r}")

                # Reemplazar tabla destino (con historico)
                print('[MB52] Reemplazando tabla destino (con historico)...')

                # Nombre de la tabla historica
                history_table = 'stock_tienda_historica'

                # 1) Asegurar que exista la tabla historica (si no, la creamos como copia vacia + columna ingestion_date)
                ensure_sql = f"""
IF OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]','U') IS NULL
BEGIN
    -- Crear tabla historica como copia vacia de la actual y añadir columna ingestion_date
    SELECT TOP 0 *, CAST(NULL AS datetime2) AS ingestion_date
    INTO [{db_name}].[{table_schema}].[{history_table}]
    FROM [{db_name}].[{table_schema}].[{table_name}];

    -- Crear indice en ingestion_date para consultas eficientes si no existe
    IF NOT EXISTS (
        SELECT name FROM sys.indexes
        WHERE name = 'IX_{history_table}_ingestion_date' AND object_id = OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]')
    )
    BEGIN
        CREATE INDEX IX_{history_table}_ingestion_date ON [{db_name}].[{table_schema}].[{history_table}] (ingestion_date);
    END
END
"""
                conn.execute(text(ensure_sql))

                # Verificar que el índice de ingestion_date existe y loguear resultado
                idx_check = conn.execute(text(f"SELECT 1 FROM sys.indexes WHERE name = 'IX_{history_table}_ingestion_date' AND object_id = OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]')")).fetchone()
                if idx_check:
                    print(f"[MB52] [INFO] Índice IX_{history_table}_ingestion_date confirmado en DB.")
                else:
                    print(f"[MB52] [WARN] No se encontró el índice IX_{history_table}_ingestion_date tras creación (revisar permisos).")

                # 2) Insertar el contenido actual de la tabla destino en la tabla historica con la fecha de ingesta
                ingest_ts = datetime.now()
                cols = ', '.join([c for c in COLUMNAS] + ['timestamp_ingestion'])
                insert_hist_sql = f"INSERT INTO [{db_name}].[{table_schema}].[{history_table}] ({cols}, ingestion_date) SELECT {cols}, :ingest_ts FROM [{db_name}].[{table_schema}].[{table_name}];"
                conn.execute(text(insert_hist_sql), {'ingest_ts': ingest_ts})

                # 3) Reemplazar la tabla destino con los datos nuevos
                conn.execute(text(f"DELETE FROM [{db_name}].[{table_schema}].[{table_name}]") )
                conn.execute(text(f"INSERT INTO [{db_name}].[{table_schema}].[{table_name}] SELECT * FROM #tmp_stock"))

            print('[MB52] [SUCCESS] Ingesta completa y consistente. Tabla reemplazada.')
            rows_ingested = int(r)
            print(f"[MB52] [INFO] Filas ingestadas: {rows_ingested}")
            print(f"[MB52] [INFO] Total columnas: {len(df.columns)}")
            return rows_ingested
        except Exception as e:
            print(f"[MB52] [ERROR] Ingesta fallida, se realizó rollback automático: {e}")
            raise
        
    except Exception as e:
        print(f"[MB52] [ERROR] Error durante ejecucion: {str(e)}")
        raise
