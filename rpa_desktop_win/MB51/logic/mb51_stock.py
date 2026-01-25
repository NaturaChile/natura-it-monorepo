"""Lógica MB51 — Descarga histórica por tramos y carga en SQL.

Comportamiento:
- Descarga datos MB51 desde SAP por tramos de 15 días desde 01-01-2025 hasta ayer.
- Para cada tramo: ejecuta la variante ALV, selecciona exportar por portapapeles, parsea y acumula filas.
- Al final hace un ingest transaccional en SQL Server en tabla `mb51` y guarda snapshot en `mb51_historica` con columna `ingestion_date`.

Notas:
- Reusa el helper central `core_shared.security.vault.Vault` para obtener credenciales SQL.
- Evita prints ruidosos por fila (solo info/resumen por tramo).
"""
from datetime import datetime, date, timedelta
import time
import os
import pandas as pd
import uuid

from core_shared.security.vault import Vault

# --- CONFIG DEFAULTS ---
DEFAULT_CENTRO = "4100"
DEFAULT_LGORT_LOW = "4147"
DEFAULT_LGORT_HIGH = "4195"
DEFAULT_VARIANTE = "BOTMB51"
CHUNK_DAYS = 15
HISTORIC_FROM = date(2025, 1, 15)


def _safe_str(s):
    import unicodedata
    if s is None:
        return s
    if isinstance(s, bytes):
        s = s.decode('utf-8', errors='replace')
    s = str(s)
    s = unicodedata.normalize('NFC', s)
    return s.strip()


def _parse_clipboard(clipboard_data: str) -> pd.DataFrame:
    """Parsea texto del portapapeles (formato ALV) y devuelve DataFrame.
    - Mantiene campos vacíos internos.
    - Ignora filas de totales/footers (ej. líneas que comienzan con '|*').
    - Normaliza números que usan punto como separador de miles y '-' al final como signo.
    """
    import re

    def _normalize_possible_number(s: str) -> str:
        if s is None:
            return s
        t = str(s).strip()
        # If it matches a DATE or TIME pattern, keep as-is (don't coerce to number)
        date_re = re.compile(r'^\d{2}[\./-]\d{2}[\./-]\d{4}$')
        time_re = re.compile(r'^\d{2}:\d{2}(:\d{2})?$')
        if date_re.match(t) or time_re.match(t):
            return t
        # Detect numeric patterns like '9.911.196-' or '1.732' or '1.234,56-'
        if re.fullmatch(r"[\d\.,]+-?", t):
            sign = -1 if t.endswith('-') else 1
            t_clean = t.rstrip('-')
            # Remove thousands dot, convert comma decimal to dot
            t_clean = t_clean.replace('.', '').replace(',', '.')
            if t_clean == '':
                return s
            return ("-" if sign == -1 else "") + t_clean
        return s

    lines = clipboard_data.strip().split('\n')
    header_line = None
    data_lines = []
    for line in lines:
        stripped = line.strip()
        # Ignorar separadores de linea (solo guiones u otros) y footers de totales que empiezan con '|*'
        if not stripped or stripped.replace('-', '').replace('|', '').strip() == '':
            continue
        if stripped.startswith('|*'):
            # Footer/linea de totales, ignorar
            continue
        if '|' in stripped:
            if header_line is None:
                header_line = stripped
            else:
                data_lines.append(stripped)

    if header_line is None:
        raise ValueError('No se encontro linea de encabezados en el portapapeles')

    headers = [_safe_str(col) for col in header_line.split('|')]
    # Mantener campos vacíos internos; solo eliminar placeholders vacíos al inicio/final
    if headers and headers[0] == '':
        headers = headers[1:]
    if headers and headers[-1] == '':
        headers = headers[:-1]

    rows = []
    for line in data_lines:
        row = [_safe_str(col) for col in line.split('|')]
        if row and row[0] == '':
            row = row[1:]
        if row and row[-1] == '':
            row = row[:-1]

        # Aplicar normalizacion de numeros a cada celda detectada como numero
        row = [ _normalize_possible_number(c) for c in row ]

        if len(row) == len(headers):
            rows.append(row)
        elif len(row) > 0:
            if len(row) > len(headers):
                rows.append(row[:len(headers)])
            else:
                row.extend([''] * (len(headers) - len(row)))
                rows.append(row)

    df = pd.DataFrame(rows, columns=headers)

    # Normalizar columnas numericas detectadas: si la mayoria de valores se parsean como numeros, convertir
    # Columns that must remain TEXT regardless of content
    non_numeric_force = {'Razión', 'Txt.cab.doc.', 'Pedido', 'Proveedor'}
    for col in df.columns:
        non_null = df[col].dropna().astype(str)
        if len(non_null) == 0:
            continue
        # If column is explicitly forced to non-numeric, skip numeric coercion
        if col in non_numeric_force:
            continue
        numeric_like = non_null.str.match(r"^-?[0-9]+([.,][0-9]+)?$")
        if numeric_like.sum() >= max(1, int(0.6 * len(non_null))):
            # Normalize common thousand/decimal formats before coercion
            s = df[col].astype(str).str.strip()
            s = s.str.rstrip('-')
            s = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df[col] = pd.to_numeric(s.replace('', None), errors='coerce')

    return df


def _generate_date_ranges(start: date, end: date, delta_days: int = CHUNK_DAYS):
    """Genera tuplas (start, end) inclusivas en tramos de delta_days.
    El último tramo llega hasta `end`.
    """
    cur = start
    while cur <= end:
        nxt = cur + timedelta(days=delta_days - 1)
        if nxt > end:
            nxt = end
        yield cur, nxt
        cur = nxt + timedelta(days=1)


def _clean_clipboard_df(df: pd.DataFrame) -> pd.DataFrame:
    """Limpia y castea el DataFrame bruto extraído del portapapeles.
    Basado en el ejemplo Polars del repo, adaptado a pandas.

    Reglas principales:
    - Quitar espacios y normalizar strings.
    - Parsear fechas 'Registrado' y 'Fecha doc.' con dayfirst True.
    - 'Cantidad' y 'Impte.ML' -> NUMERIC (float) limpiando miles (puntos) y coma decimal.
    - Mantener otras columnas como string.
    """
    import unicodedata

    # Normalizar columnas (quitar espacios sobrantes en nombres)
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # Strip en string columns
    for c in df.columns:
        df[c] = df[c].astype(str).str.strip()

    # Parsear fechas
    date_cols = ['Registrado', 'Fecha doc.']
    for c in date_cols:
        if c in df.columns:
            # convertimos formatos dd.mm.yyyy o dd/mm/yyyy y también yyyy-mm-dd (dos intentos explícitos para evitar warnings)
            tmp = df[c].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
            res = pd.to_datetime(tmp, format='%d-%m-%Y', errors='coerce')
            res2 = pd.to_datetime(tmp, format='%Y-%m-%d', errors='coerce')
            df[c] = res.fillna(res2).dt.date

    # Numericas: quitar separadores de miles y normalizar decimal
    num_cols = ['Cantidad', 'Impte.ML']
    for c in num_cols:
        if c in df.columns:
            s_raw = df[c].astype(str).str.strip()
            s = s_raw.str.rstrip('-')
            s = s.str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            num = pd.to_numeric(s.replace('', None), errors='coerce')
            # Fallback: if parsing failed but original contains digits, try extracting numeric fragments
            mask_na = num.isna() & s_raw.str.contains(r'\d', regex=True)
            if mask_na.any():
                import re as _re
                def _extract_numeric(x):
                    if not _re.search(r'\d', x):
                        return None
                    t = _re.sub(r'[^\d\-,\.]', '', x)
                    sign = -1 if t.endswith('-') else 1
                    t = t.rstrip('-')
                    t = t.replace('.', '')
                    t = t.replace(',', '.')
                    try:
                        return float(t) * sign
                    except Exception:
                        m = _re.search(r'[\d]+[,.]?\d*', t)
                        return float(m.group(0).replace(',', '.')) if m else None
                num_fallback = s_raw[mask_na].apply(lambda x: _extract_numeric(str(x)))
                num.loc[mask_na] = num_fallback
            df[c] = num

    # Forzar strings en el resto
    preserve = set(date_cols + num_cols + ['timestamp_ingestion'])
    for c in df.columns:
        if c not in preserve:
            df[c] = df[c].where(df[c].notna(), None)

    # 'Razión' debe ser siempre texto; conservar valores aunque parezcan numericos
    if 'Razión' in df.columns:
        df['Razión'] = df['Razión'].astype(str).str.strip().replace({'': None})

    # 'Txt.cab.doc.', 'Pedido', 'Proveedor' sin letras ni numeros -> null
    for tcol in ['Txt.cab.doc.', 'Pedido', 'Proveedor']:
        if tcol in df.columns:
            def _maybe_null_text(x):
                if x is None:
                    return None
                s = str(x).strip()
                if s == '':
                    return None
                if re.search(r'[A-Za-z0-9ÁÉÍÓÚáéíóúÑñ]', s) is None:
                    return None
                return s
            df[tcol] = df[tcol].apply(_maybe_null_text)

    return df


# --- Helpers para inferir esquema y DDL (deben estar definidos antes del bucle principal) ---
import re

def _infer_sql_type(series: pd.Series) -> str:
    samples = series.dropna().astype(str).map(lambda x: x.strip())
    if len(samples) == 0:
        return 'NVARCHAR(255)'

    date_re = re.compile(r'^\d{2}[\./-]\d{2}[\./-]\d{4}$')
    time_re = re.compile(r'^\d{2}:\d{2}(:\d{2})?$')

    # If any sample contains alphabetic characters (like 'YR1'), prefer string to avoid casting loss
    alpha_count = samples.str.contains(r'[A-Za-z]', regex=True).sum()
    max_len = 0
    for v in samples.head(200):
        vv = str(v)
        max_len = max(max_len, len(vv))

    if alpha_count > 0:
        if max_len <= 50:
            return f'NVARCHAR({max_len + 10})'
        if max_len <= 4000:
            return f'NVARCHAR({max_len + 100})'
        return 'NVARCHAR(MAX)'

    int_like = 0
    float_like = 0
    date_like = 0
    max_int = 0
    for v in samples.head(200):
        vv = str(v)
        if date_re.match(vv):
            date_like += 1
            continue
        if time_re.match(vv):
            # time only -> keep as NVARCHAR
            continue
        # normalize numeric-looking values: remove thousands '.' and convert comma to dot
        t = vv.rstrip('-')
        t = t.replace('.', '').replace(',', '.')
        if re.fullmatch(r'-?\d+', t):
            int_like += 1
            try:
                iv = abs(int(t))
                if iv > max_int:
                    max_int = iv
            except Exception:
                pass
        elif re.fullmatch(r'-?\d+\.\d+$', t):
            float_like += 1

    total = max(1, len(samples.head(200)))
    if date_like >= 0.6 * total:
        return 'DATE'
    if float_like >= 0.6 * total:
        return 'NUMERIC(18,4)'
    if int_like >= 0.6 * total:
        # choose size
        if max_int > 2_147_483_647:
            return 'BIGINT'
        return 'INT'
    # otherwise string with reasonable length
    if max_len <= 50:
        return f'NVARCHAR({max_len + 10})'
    if max_len <= 4000:
        return f'NVARCHAR({max_len + 100})'
    return 'NVARCHAR(MAX)'


def _generate_create_table_sql(db: str, schema: str, table: str, df: pd.DataFrame) -> str:
    cols_defs = []
    for c in df.columns:
        t = _infer_sql_type(df[c])
        cols_defs.append(f'[{c}] {t} NULL')
    cols_sql = ',\n    '.join(cols_defs)
    ddl = f"""
IF OBJECT_ID('[{db}].[{schema}].[{table}]','U') IS NULL
BEGIN
    CREATE TABLE [{db}].[{schema}].[{table}] (
    {cols_sql}
    );
END
"""
    return ddl


def _generate_generic_table_sql(db: str, schema: str, table: str, df: pd.DataFrame) -> str:
    # Fallback conservador: todas las columnas NVARCHAR(MAX)
    cols_defs = [f'[{c}] NVARCHAR(MAX) NULL' for c in df.columns]
    cols_sql = ',\n    '.join(cols_defs)
    ddl = f"""
IF OBJECT_ID('[{db}].[{schema}].[{table}]','U') IS NULL
BEGIN
    CREATE TABLE [{db}].[{schema}].[{table}] (
    {cols_sql}
    );
END
"""
    return ddl


def _generate_canonical_table_sql(db: str, schema: str, table: str) -> str:
    """Return DDL for canonical MB51 table with fixed schema (no inference)."""
    cols_defs = [
        '[Ce.] NVARCHAR(50) NULL',
        '[Alm.] NVARCHAR(50) NULL',
        '[CMv] NVARCHAR(50) NULL',
        '[Razión] NVARCHAR(100) NULL',
        '[Registrado] DATE NULL',
        '[Hora] NVARCHAR(16) NULL',
        '[Doc.mat.] NVARCHAR(50) NULL',
        '[Usuario] NVARCHAR(64) NULL',
        '[Fecha doc.] DATE NULL',
        '[Material] NVARCHAR(50) NULL',
        '[Texto breve de material] NVARCHAR(400) NULL',
        '[Lote] NVARCHAR(100) NULL',
        '[Cantidad] NUMERIC(18,4) NULL',
        '[Impte.ML] NUMERIC(18,4) NULL',
        '[Txt.cab.doc.] NVARCHAR(255) NULL',
        '[Pedido] NVARCHAR(100) NULL',
        '[Proveedor] NVARCHAR(100) NULL',
        '[Txt clase-mov.] NVARCHAR(200) NULL',
        '[timestamp_ingestion] DATETIME2 NULL'
    ]
    cols_sql = ',\n    '.join(cols_defs)
    ddl = f"""
IF OBJECT_ID('[{db}].[{schema}].[{table}]','U') IS NULL
BEGIN
    CREATE TABLE [{db}].[{schema}].[{table}] (
    {cols_sql}
    );
END
"""
    return ddl


def ejecutar_mb51(session,
                 centro: str = DEFAULT_CENTRO,
                 lgort_low: str = DEFAULT_LGORT_LOW,
                 lgort_high: str = DEFAULT_LGORT_HIGH,
                 variante: str = DEFAULT_VARIANTE,
                 desde: date = HISTORIC_FROM,
                 hasta: date = None):
    """Ejecuta MB51 por tramos historicos y carga en SQL.

    Args:
        session: sesion SAP (SAP GUI Scripting object)
        centro, lgort_low, lgort_high, variante: parametros de selection
        desde: fecha de inicio historic (date)
        hasta: fecha final (date). Si None => ayer.

    Returns:
        int: filas ingestadas totales
    """
    if hasta is None:
        hasta = date.today() - timedelta(days=1)

    print(f"[MB51] Rango historico: {desde.isoformat()} -> {hasta.isoformat()} (tramos de {CHUNK_DAYS} días)")

    frames = []
            # 1. Limpiar pantalla inicial
    print("[MB51] Paso 1: Preparando pantalla...")
    session.findById("wnd[0]/tbar[0]/okcd").text = "MB51"
    session.findById("wnd[0]").sendVKey(0)
    time.sleep(0.5)

    # --- Preparar conexion a DB y repo ANTES de procesar tramos ---
    print('[MB51] Intentando leer credenciales SQL2022_* desde Vault...')
    db_host = Vault.get_secret('SQL2022_HOST')
    db_user = Vault.get_secret('SQL2022_USER')
    db_pw = Vault.get_secret('SQL2022_PW')
    db_name = os.getenv('SQL2022_DB', 'Retail')

    if not (db_host and db_user and db_pw):
        env_host = os.getenv('SQL2022_HOST')
        env_user = os.getenv('SQL2022_USER')
        env_pw = os.getenv('SQL2022_PW')
        if env_host or env_user or env_pw:
            print('[MB51] [WARN] Secrets SQL2022_* no encontrados en Vault. Usando variables de entorno para esta ejecución.')
            db_host = db_host or env_host
            db_user = db_user or env_user
            db_pw = db_pw or env_pw
        else:
            raise Exception('Secrets SQL2022_* no encontrados en Vault ni en variables de entorno. Agregue los secrets en Vault (Environment: SAP_Jorge)')

    # Instanciar repo SQL (antes de iniciar tramos)
    from sqlalchemy import create_engine, text
    import urllib

    class SqlRepositoryLocal:
        def __init__(self, host, db, user=None, password=None, driver=None):
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
                if not selected_driver:
                    for d in preferred:
                        if d in available:
                            selected_driver = d
                            break
                if not selected_driver:
                    raise RuntimeError(f"No se encontró un driver ODBC compatible. Drivers instalados: {available}")
            except Exception as e:
                raise RuntimeError(f"Error detectando drivers ODBC: {e}")

            print(f"[MB51] [INFO] Usando driver ODBC: {selected_driver}")
            if user and password:
                connection_string = (
                    f"DRIVER={{{selected_driver}}};"
                    f"SERVER={host};"
                    f"DATABASE={db};"
                    f"UID={user};"
                    f"PWD={password};"
                    "Encrypt=no;TrustServerCertificate=yes;"
                )
            else:
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
                raise RuntimeError(f"Error creando engine SQLAlchemy/pyodbc: {e}\nAsegure que el driver ODBC '{selected_driver}' esté instalado y que 'pyodbc' esté disponible.")

    repo = SqlRepositoryLocal(host=db_host, db=db_name, user=db_user, password=db_pw)

    # Tabla destino (puede configurarse via env vars)
    table_schema = os.getenv('MB51_TABLE_SCHEMA', 'Retail')
    table_name = os.getenv('MB51_TABLE_NAME', 'mb51')

    for s, e in _generate_date_ranges(desde, hasta, CHUNK_DAYS):
        print(f"[MB51] Ejecutando tramo: {s.strftime('%d%m%Y')} -> {e.strftime('%d%m%Y')}")
        # Preparar pantalla y filtros en SAP
        session.findById("wnd[0]/usr/ctxtWERKS-LOW").text = centro
        session.findById("wnd[0]/usr/ctxtLGORT-LOW").text = lgort_low
        session.findById("wnd[0]/usr/ctxtLGORT-HIGH").text = lgort_high
        session.findById("wnd[0]/usr/ctxtBUDAT-LOW").text = s.strftime('%d%m%Y')
        session.findById("wnd[0]/usr/ctxtBUDAT-HIGH").text = e.strftime('%d%m%Y')
        session.findById("wnd[0]/usr/ctxtALV_DEF").text = variante

        # Ejecutar reporte
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        time.sleep(2)

        # Exportar (menú -> portapapeles)
        try:
            session.findById("wnd[0]/mbar/menu[0]/menu[1]/menu[2]").select()
            time.sleep(0.5)
            session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[4,0]").select()
            session.findById("wnd[1]/tbar[0]/btn[0]").press()
            time.sleep(1)
        except BaseException as e:
            # Capturar KeyboardInterrupt y otros errores graves
            if isinstance(e, KeyboardInterrupt):
                print(f"[MB51] [ERROR] Export interrumpido por KeyboardInterrupt en tramo {s} -> {e}")
                # Guardar estado parcial minimal y abortar
                run_file = os.path.join(log_dir, f'mb51_run_interrupt_{datetime.now().strftime("%Y%m%d%H%M%S")}.json')
                try:
                    import json
                    run_log['error'] = 'KeyboardInterrupt during export'
                    with open(run_file, 'w', encoding='utf-8') as fh:
                        json.dump(run_log, fh, indent=2, default=str, ensure_ascii=False)
                    print(f"[MB51] Estado interrumpido guardado en {run_file}")
                except Exception:
                    pass
                raise
            else:
                print(f"[MB51] [ERROR] Error exportando tramo {s} - {e}")
                continue

        # Leer portapapeles
        import win32clipboard
        win32clipboard.OpenClipboard()
        try:
            clipboard_data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()

        # Press "Back" to return to transaction UI so filters can be updated for next tramo
        try:
            # Prefer toolbar back button
            session.findById("wnd[0]/tbar[0]/btn[3]").press()
        except Exception:
            try:
                session.findById("wnd[0]").sendVKey(3)
            except Exception:
                pass

        # Preparar bitacora (por corrida)
        from pathlib import Path
        log_dir = os.getenv('MB51_LOG_DIR', str(Path(__file__).resolve().parents[2] / 'MB51' / 'logs'))
        os.makedirs(log_dir, exist_ok=True)
        run_id = datetime.now().strftime('%Y%m%d%H%M%S')
        run_file = os.path.join(log_dir, f'mb51_run_{run_id}.json')
        # Cargar historico de tramos ya ingestados para evitar reprocesar
        ingested_chunks = set()
        for lf in Path(log_dir).glob('mb51_run_*.json'):
            try:
                import json
                with open(lf, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)
                for ch in data.get('chunks', []):
                    if ch.get('ingesta'):
                        ingested_chunks.add((ch.get('start'), ch.get('end')))
            except Exception:
                pass

        # Inicializar registro de corrida
        run_log = {
            'run_id': run_id,
            'started': datetime.now().isoformat(),
            'chunks': []
        }

        # Procesar y cargar este tramo inmediatamente
        chunk_key = (s.isoformat(), e.isoformat())
        if chunk_key in ingested_chunks:
            print(f"[MB51] Tramo {s} -> {e} ya procesado con ingesta previa. Saltando.")
        else:
            chunk_entry = {
                'start': s.isoformat(),
                'end': e.isoformat(),
                'download_sap': False,
                'rows': 0,
                'ingesta': False,
                'error': None
            }
            try:
                df = _parse_clipboard(clipboard_data)
                # Aplicar limpieza robusta basada en el ejemplo Polars del repo
                df = _clean_clipboard_df(df)

                chunk_entry['download_sap'] = True
                chunk_entry['rows'] = len(df)
                print(f"[MB51] Tramo {s} -> {e} filas: {len(df)} columnas: {len(df.columns)}")

                # Añadir timestamp
                df['timestamp_ingestion'] = datetime.now()

                # Asegurar esquema/tabla: create or alter to add missing cols
                from sqlalchemy import text
                try:
                    # Preparar mapeo de columnas: usar nombres crudos del encabezado, deduplicando sufijos si es necesario
                    raw_cols = list(df.drop(columns=['timestamp_ingestion']).columns)
                    seen_cols = {}
                    db_cols = []
                    columns_map = []  # list of {original:..., db:...}
                    for c in raw_cols:
                        base = str(c).strip()
                        dbname = base
                        if dbname in seen_cols:
                            seen_cols[dbname] += 1
                            dbname = f"{base}__{seen_cols[dbname]}"
                        else:
                            seen_cols[dbname] = 0
                        # Truncar nombre si demasiado largo (max identifier 128)
                        if len(dbname) > 120:
                            dbname = dbname[:120]
                        db_cols.append(dbname)
                        columns_map.append({'original': c, 'db': dbname})

                    chunk_entry['columns_map'] = columns_map

                    # Crear df temporal con nombres db_cols (crudos o canónicos) para generar DDL e insertar
                    # Mapamos columnas a esquema canonico si es posible
                    canonical = [
                        'Ce.','Alm.','CMv','Razión','Registrado','Hora','Doc.mat.','Usuario','Fecha doc.','Material',
                        'Texto breve de material','Lote','Cantidad','Impte.ML','Txt.cab.doc.','Pedido','Proveedor','Txt clase-mov.'
                    ]

                    # Normalizer helper for matching header names (remove diacritics, punctuation, lower)
                    def _norm_key(s: str) -> str:
                        import unicodedata, re
                        s = str(s)
                        s = unicodedata.normalize('NFKD', s)
                        s = ''.join(ch for ch in s if not unicodedata.combining(ch))
                        s = s.lower()
                        s = re.sub(r"[^a-z0-9]","", s)
                        return s

                    raw_cols = list(df.drop(columns=['timestamp_ingestion']).columns)
                    raw_map = { _norm_key(c): c for c in raw_cols }

                    final_cols = []
                    columns_map = []
                    for can in canonical:
                        nk = _norm_key(can)
                        if nk in raw_map:
                            final_cols.append(can)
                            columns_map.append({'original': raw_map[nk], 'db': can})
                        else:
                            # If not present in raw, keep missing but still include column to preserve final schema
                            final_cols.append(can)
                            columns_map.append({'original': None, 'db': can})

                    chunk_entry['columns_map'] = columns_map

                    # Build df_for_schema using canonical final_cols in that order
                    df_for_schema = pd.DataFrame({c: df.get(raw) if raw else None for (raw,c) in [(m['original'], m['db']) for m in columns_map]})
                    # Ensure types are pandas-friendly (objects) and fill missing series with None-series of correct length
                    for c in df_for_schema.columns:
                        if df_for_schema[c] is None:
                            df_for_schema[c] = pd.Series([None] * len(df), dtype=object)
                        else:
                            df_for_schema[c] = df_for_schema[c].astype(object)

                    # Add timestamp_ingestion column with current datetime for all rows
                    if 'timestamp_ingestion' not in df_for_schema.columns:
                        df_for_schema['timestamp_ingestion'] = pd.Series([datetime.now()] * len(df))
                    else:
                        # ensure it's populated
                        df_for_schema['timestamp_ingestion'] = pd.to_datetime(df_for_schema['timestamp_ingestion'], errors='coerce')

                    # Define canonical types (canonical schema provided by user)
                    canonical_types = {
                        'Ce.': 'STRING', 'Alm.': 'STRING', 'CMv': 'STRING', 'Razión': 'STRING',
                        'Registrado': 'DATE', 'Hora': 'STRING', 'Doc.mat.': 'STRING', 'Usuario': 'STRING',
                        'Fecha doc.': 'DATE', 'Material': 'STRING', 'Texto breve de material': 'STRING',
                        'Lote': 'STRING', 'Cantidad': 'NUMERIC', 'Impte.ML': 'NUMERIC', 'Txt.cab.doc.': 'STRING',
                        'Pedido': 'STRING', 'Proveedor': 'STRING', 'Txt clase-mov.': 'STRING', 'timestamp_ingestion': 'DATETIME'
                    }

                    # Use canonical column list for creation and insertion
                    db_cols = list(df_for_schema.columns)

                    with repo.engine.begin() as conn:
                        # Crear tabla si no existe usando esquema canonico (evita discrepancias entre tramos)
                        create_table_sql = _generate_canonical_table_sql(db_name, table_schema, table_name)
                        # Guardar DDL en bitacora
                        chunk_entry['ddl'] = create_table_sql

                        conn.execute(text(create_table_sql))

                        # Verificar que la tabla fue creada
                        obj = conn.execute(text(f"SELECT OBJECT_ID('[{db_name}].[{table_schema}].[{table_name}]')")).fetchone()
                        chunk_entry['create_ok'] = bool(obj and obj[0])

                        # Añadir columnas faltantes si hay (comparando en minusculas)
                        existing_cols = {r[0].lower() for r in conn.execute(text(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_CATALOG = '{db_name}' AND TABLE_SCHEMA = '{table_schema}' AND TABLE_NAME = '{table_name}'")).fetchall()}
                        for dbc in db_cols:
                            if dbc.lower() not in existing_cols:
                                print(f"[MB51] Añadiendo columna '{dbc}' a tabla destino (NVARCHAR(MAX))")
                                conn.execute(text(f"ALTER TABLE [{db_name}].[{table_schema}].[{table_name}] ADD [{dbc}] NVARCHAR(MAX) NULL"))

                        # Preparar df para insercion usando df_for_schema (ya mapeada a columnas canonicas)
                        df_to_insert = df_for_schema.copy()
                        # Asegurar que df_to_insert tenga el mismo numero de filas que df (si df_for_schema fue construido con series)
                        # Si df_for_schema columnas son None, reemplazarlas por None series con len(df)
                        for c in df_to_insert.columns:
                            if df_to_insert[c] is None:
                                df_to_insert[c] = pd.Series([None]*len(df), dtype=object)
                        # Seleccionar por orden db_cols para consistencia
                        df_to_insert = df_to_insert[[c for c in db_cols]]

                        # Coerciones por tipo según el esquema canónico (no inferir)
                        type_map = {c: canonical_types.get(c, 'STRING') for c in df_for_schema.columns}
                        for c in df_to_insert.columns:
                            t = type_map.get(c, '').upper()
                            if t == 'DATETIME' or t.startswith('DATETIME') or t == 'DATETIME2' or c == 'timestamp_ingestion':
                                df_to_insert[c] = pd.to_datetime(df_to_insert[c], errors='coerce')
                            elif t == 'DATE':
                                tmp = df_to_insert[c].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
                                res = pd.to_datetime(tmp, format='%d-%m-%Y', errors='coerce')
                                res2 = pd.to_datetime(tmp, format='%Y-%m-%d', errors='coerce')
                                df_to_insert[c] = res.fillna(res2)
                            elif t == 'NUMERIC':
                                df_to_insert[c] = pd.to_numeric(df_to_insert[c].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
                            elif t == 'INT' or t == 'BIGINT':
                                df_to_insert[c] = pd.to_numeric(df_to_insert[c].astype(str).str.replace('.', '').str.replace(',', ''), errors='coerce')
                            else:
                                # Keep original strings (preserve values like 'YR1' in CMv)
                                df_to_insert[c] = df_to_insert[c].astype(object)


                        # Cargar a tabla de staging (única por corrida) y luego insertar (append)
                        short = uuid.uuid4().hex[:8]
                        tmp_table = f"tmp_mb51_chunk_{short}"
                        print(f"[MB51] [DEBUG] Creando staging table {table_schema}.{tmp_table} ...")
                        df_to_insert.to_sql(tmp_table, con=conn, if_exists='replace', index=False, schema=table_schema)
                        # Insert into main con lista explícita de columnas para evitar mismatch
                        col_list = ', '.join([f'[{c}]' for c in db_cols])
                        conn.execute(text(f"INSERT INTO [{db_name}].[{table_schema}].[{table_name}] ({col_list}) SELECT {col_list} FROM [{db_name}].[{table_schema}].[{tmp_table}]"))
                        # Cleanup staging table
                        try:
                            conn.execute(text(f"DROP TABLE [{db_name}].[{table_schema}].[{tmp_table}]") )
                        except Exception:
                            pass

                    chunk_entry['ingesta'] = True
                except Exception as e_inner:
                    import traceback
                    tb = traceback.format_exc()
                    chunk_entry['error'] = tb
                    chunk_entry['create_ok'] = False
                    print(f"[MB51] [ERROR] Fallo creando/insertando tabla: {e_inner}\n{tb}")

                    # Intentar fallback conservador: crear tabla con NVARCHAR(MAX) para todas las columnas
                    try:
                        # Use df_for_schema (columnas normalizadas) for fallback DDL to keep names consistent
                        fallback_ddl = _generate_generic_table_sql(db_name, table_schema, table_name, df_for_schema)
                        chunk_entry['ddl_fallback'] = fallback_ddl
                        print(f"[MB51] [INFO] Intentando fallback conservador para crear tabla {table_name}...")
                        with repo.engine.begin() as conn2:
                            conn2.execute(text(fallback_ddl))
                            # Verificar creación
                            obj2 = conn2.execute(text(f"SELECT OBJECT_ID('[{db_name}].[{table_schema}].[{table_name}]')")).fetchone()
                            if not (obj2 and obj2[0]):
                                raise RuntimeError('Fallback DDL ejecutado pero la tabla sigue sin existir')

                            # Añadir columnas faltantes si hay (usando nombres db_cols normalizados)
                            existing_cols2 = {r[0].lower() for r in conn2.execute(text(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_CATALOG = '{db_name}' AND TABLE_SCHEMA = '{table_schema}' AND TABLE_NAME = '{table_name}'")).fetchall()}
                            for dbc in db_cols:
                                if dbc.lower() not in existing_cols2:
                                    conn2.execute(text(f"ALTER TABLE [{db_name}].[{table_schema}].[{table_name}] ADD [{dbc}] NVARCHAR(MAX) NULL"))

                            # Preparar df renombrado para insert (usar las columnas canonicas) y mantener solo esas columnas
                            df_to_insert_fb = df_for_schema.copy()
                            for c in df_to_insert_fb.columns:
                                if df_to_insert_fb[c] is None:
                                    df_to_insert_fb[c] = pd.Series([None]*len(df), dtype=object)
                            df_to_insert_fb = df_to_insert_fb[[c for c in db_cols]]

                            # Coerciones por tipo antes del fallback insert (usando esquema canonico)
                            type_map_fb = {c: canonical_types.get(c, 'STRING') for c in df_for_schema.columns}
                            for c in df_to_insert_fb.columns:
                                t = type_map_fb.get(c, '').upper()
                                if t == 'DATETIME' or t.startswith('DATETIME') or t == 'DATETIME2' or c == 'timestamp_ingestion':
                                    df_to_insert_fb[c] = pd.to_datetime(df_to_insert_fb[c], errors='coerce')
                                elif t == 'DATE':
                                    tmp = df_to_insert_fb[c].astype(str).str.replace('.', '-', regex=False).str.replace('/', '-', regex=False)
                                    res = pd.to_datetime(tmp, format='%d-%m-%Y', errors='coerce')
                                    res2 = pd.to_datetime(tmp, format='%Y-%m-%d', errors='coerce')
                                    df_to_insert_fb[c] = res.fillna(res2)
                                elif t == 'NUMERIC':
                                    df_to_insert_fb[c] = pd.to_numeric(df_to_insert_fb[c].astype(str).str.replace('.', '').str.replace(',', '.'), errors='coerce')
                                elif t == 'INT' or t == 'BIGINT':
                                    df_to_insert_fb[c] = pd.to_numeric(df_to_insert_fb[c].astype(str).str.replace('.', '').str.replace(',', ''), errors='coerce')
                                else:
                                    df_to_insert_fb[c] = df_to_insert_fb[c].astype(object)

                            # Cargar a tabla de staging (única por corrida) y luego insertar
                            short_fb = uuid.uuid4().hex[:8]
                            tmp_table = f"tmp_mb51_chunk_{short_fb}"
                            print(f"[MB51] [DEBUG] Creando staging table {table_schema}.{tmp_table} (fallback) ...")
                            df_to_insert_fb.to_sql(tmp_table, con=conn2, if_exists='replace', index=False, schema=table_schema)
                            col_list_fb = ', '.join([f'[{c}]' for c in db_cols])
                            conn2.execute(text(f"INSERT INTO [{db_name}].[{table_schema}].[{table_name}] ({col_list_fb}) SELECT {col_list_fb} FROM [{db_name}].[{table_schema}].[{tmp_table}]") )
                            try:
                                conn2.execute(text(f"DROP TABLE [{db_name}].[{table_schema}].[{tmp_table}]") )
                            except Exception:
                                pass

                        chunk_entry['ingesta'] = True
                        chunk_entry['create_ok'] = True
                        chunk_entry['error'] = None
                        print(f"[MB51] [INFO] Fallback exitoso: tabla {table_name} creada e ingesta completada para tramo {s} -> {e}.")
                    except Exception as fallback_exc:
                        f_tb = traceback.format_exc()
                        chunk_entry['error_fallback'] = f_tb
                        print(f"[MB51] [ERROR] Fallback fallido: {fallback_exc}\n{f_tb}")
                    # fin fallback


            except Exception as e:
                chunk_entry['error'] = str(e)
                print(f"[MB51] [ERROR] Tramo {s} -> {e}")

            # Guardar estado parcial en el archivo de corrida
            try:
                import json
                run_log['chunks'].append(chunk_entry)
                with open(run_file, 'w', encoding='utf-8') as fh:
                    json.dump(run_log, fh, indent=2, default=str, ensure_ascii=False)
                print(f"[MB51] Estado de tramo guardado en {run_file}")
            except Exception as e:
                print(f"[MB51] [WARN] No se pudo escribir bitacora: {e}")

    if not frames:
        print('[MB51] [INFO] No se obtuvieron filas para el rango solicitado.')
        return 0

    final_df = pd.concat(frames, ignore_index=True, sort=False)
    # Añadir timestamp de ingestion
    final_df['timestamp_ingestion'] = datetime.now()

    # --- Normalizar nombres de columna para SQL (snake_case, unicos) ---
    def normalize_col(c: str) -> str:
        c = str(c).strip().lower()
        c = c.replace('-', ' ').replace('/', ' ')
        c = ''.join(ch if ch.isalnum() or ch == ' ' else '_' for ch in c)
        c = '_'.join(c.split())
        return c

    cols = list(final_df.columns)
    new_cols = []
    seen = {}
    for i, c in enumerate(cols):
        nc = normalize_col(c)
        if nc in seen:
            seen[nc] += 1
            nc = f"{nc}__{seen[nc]}"
        else:
            seen[nc] = 0
        new_cols.append(nc)
    final_df.columns = new_cols

    # Inferir esquema SQL a partir de muestras
    import re


    # Ingest SQL (misma logica que MB52)
    print('[MB51] Intentando leer credenciales SQL2022_* desde Vault...')
    db_host = Vault.get_secret('SQL2022_HOST')
    db_user = Vault.get_secret('SQL2022_USER')
    db_pw = Vault.get_secret('SQL2022_PW')
    db_name = os.getenv('SQL2022_DB', 'Retail')

    if not (db_host and db_user and db_pw):
        env_host = os.getenv('SQL2022_HOST')
        env_user = os.getenv('SQL2022_USER')
        env_pw = os.getenv('SQL2022_PW')
        if env_host or env_user or env_pw:
            print('[MB51] [WARN] Secrets SQL2022_* no encontrados en Vault. Usando variables de entorno para esta ejecución.')
            db_host = db_host or env_host
            db_user = db_user or env_user
            db_pw = db_pw or env_pw
        else:
            raise Exception('Secrets SQL2022_* no encontrados en Vault ni en variables de entorno. Agregue los secrets en Vault (Environment: SAP_Jorge)')

    # Repositorio SQL local (copiado y adaptado)
    from sqlalchemy import create_engine, text
    import urllib

    class SqlRepository:
        def __init__(self, host, db, user=None, password=None, driver=None):
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
                if not selected_driver:
                    for d in preferred:
                        if d in available:
                            selected_driver = d
                            break
                if not selected_driver:
                    raise RuntimeError(f"No se encontró un driver ODBC compatible. Drivers instalados: {available}")
            except Exception as e:
                raise RuntimeError(f"Error detectando drivers ODBC: {e}")

            print(f"[MB51] [INFO] Usando driver ODBC: {selected_driver}")
            if user and password:
                connection_string = (
                    f"DRIVER={{{selected_driver}}};"
                    f"SERVER={host};"
                    f"DATABASE={db};"
                    f"UID={user};"
                    f"PWD={password};"
                    "Encrypt=no;TrustServerCertificate=yes;"
                )
            else:
                connection_string = (
                    f"DRIVER={{{selected_driver}}};"
                    f"SERVER={host};"
                    f"DATABASE={db};"
                    "Trusted_Connection=yes;"
                )
            params = urllib.parse.quote_plus(connection_string)
            self.engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}", fast_executemany=True)

    repo = SqlRepository(host=db_host, db=db_name, user=db_user, password=db_pw)

    table_schema = 'Retail'
    table_name = 'mb51'
    history_table = 'mb51_historica'

    try:
        with repo.engine.begin() as conn:
            tmp_table = '#tmp_mb51'
            print('[MB51] Creando tabla temporal y cargando datos...')
            final_df.to_sql(tmp_table, con=conn, if_exists='replace', index=False)

            r = conn.execute(text("SELECT COUNT(1) FROM #tmp_mb51")).fetchone()[0]
            print(f"[MB51] Filas en temp: {r}")

            # Crear tabla historica si no existe
            ensure_sql = f"""
IF OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]','U') IS NULL
BEGIN
    SELECT TOP 0 *, CAST(NULL AS datetime2) AS ingestion_date
    INTO [{db_name}].[{table_schema}].[{history_table}]
    FROM [{db_name}].[{table_schema}].[{table_name}];

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

            # Antes de insertar, asegurar que la tabla destino exista y tenga tipos apropiados
            create_table_sql = _generate_create_table_sql(db_name, table_schema, table_name, final_df.drop(columns=['timestamp_ingestion']))
            conn.execute(text(create_table_sql))

            # Asegurar tabla historica con ingestion_date
            ensure_hist_sql = f"""
IF OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]','U') IS NULL
BEGIN
    CREATE TABLE [{db_name}].[{table_schema}].[{history_table}] (
        -- se crea con la misma estructura que la principal + ingestion_date
        -- la siguiente instruccion creara la estructura vacia a partir de la tabla principal
    );
END
"""
            # Si la tabla principal fue creada, recreamos la historica como copia vacia con ingestion_date
            # Usamos SELECT TOP 0 para copiar columnas (si historica no existe)
            conn.execute(text(f"IF OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]','U') IS NULL BEGIN SELECT TOP 0 *, CAST(NULL AS datetime2) AS ingestion_date INTO [{db_name}].[{table_schema}].[{history_table}] FROM [{db_name}].[{table_schema}].[{table_name}]; END"))

            # crear indice de ingestion_date si falta
            conn.execute(text(f"IF NOT EXISTS (SELECT name FROM sys.indexes WHERE name = 'IX_{history_table}_ingestion_date' AND object_id = OBJECT_ID('[{db_name}].[{table_schema}].[{history_table}]')) BEGIN CREATE INDEX IX_{history_table}_ingestion_date ON [{db_name}].[{table_schema}].[{history_table}] (ingestion_date); END"))

            # 2) Insertar el contenido actual de la tabla destino en la tabla historica con la fecha de ingesta
            ingest_ts = datetime.now()
            cols = ', '.join([c for c in final_df.columns if c != 'timestamp_ingestion'] + ['timestamp_ingestion'])
            insert_hist_sql = f"INSERT INTO [{db_name}].[{table_schema}].[{history_table}] ({cols}, ingestion_date) SELECT {cols}, :ingest_ts FROM [{db_name}].[{table_schema}].[{table_name}];"
            conn.execute(text(insert_hist_sql), {'ingest_ts': ingest_ts})

            # 3) Reemplazar la tabla destino con los datos nuevos
            conn.execute(text(f"DELETE FROM [{db_name}].[{table_schema}].[{table_name}]") )
            conn.execute(text(f"INSERT INTO [{db_name}].[{table_schema}].[{table_name}] SELECT * FROM #tmp_mb51"))

        print('[MB51] [SUCCESS] Ingesta completa y consistente. Tabla reemplazada.')
        print(f"[MB51] [INFO] Filas ingestadas: {int(r)}")
        return int(r)
    except Exception as e:
        print(f"[MB51] [ERROR] Ingesta fallida, se realizó rollback automático: {e}")
        raise
