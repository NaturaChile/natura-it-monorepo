"""
DuckDB Batch Processor — Motor de transformación vectorizada para SAP EWM.

Reemplaza FileParser para lectura masiva de directorios completos.
Patrón: "Clean in Python/DuckDB, Validate in SQL"

Cada fuente tiene su método batch_* que:
  1. Lee todo _processing/*.txt en una operación con DuckDB
  2. Aplica limpieza técnica (TRIM, cast, null handling) vectorizada 
  3. Retorna dict de {nombre_tabla_staging: pyarrow.Table}
"""

import os
import re
import time
import duckdb
import pyarrow as pa
from datetime import datetime


def _log(tag: str, msg: str):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")


class DuckDBBatchProcessor:
    """Motor de transformación vectorizada con DuckDB para archivos SAP EWM."""

    def __init__(self):
        # Conexión in-memory, cada lote es efímero
        self.con = duckdb.connect(database=':memory:')
        _log('DUCKDB', 'Motor DuckDB inicializado (in-memory)')

    def close(self):
        self.con.close()

    # ═══════════════════════════════════════════════════════════════
    # FUENTE 1: CARTONING
    # ═══════════════════════════════════════════════════════════════

    def batch_cartoning(self, processing_dir: str) -> dict:
        """Lee y limpia todos los archivos de Cartoning en un directorio.
        
        Returns:
            {'Staging_EWM_Cartoning': pyarrow.Table} o {} si vacío
        """
        tag = 'DUCK-CART'
        t0 = time.time()
        glob_pattern = os.path.join(processing_dir, '*.txt').replace('\\', '/')

        try:
            # Cartoning usa ; como separador pero a veces tiene espacios extra
            # Pre-procesamos: leemos cada archivo, aplicamos regex, concatenamos
            all_rows = []
            file_count = 0
            for fname in os.listdir(processing_dir):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.join(processing_dir, fname)
                with open(fpath, 'r', encoding='latin-1', errors='replace') as f:
                    raw = f.read()
                # Regla de negocio: insertar ; donde faltan separadores
                clean = re.sub(r'(\d)\s{2,}(\d)', r'\1;\2', raw)
                for line in clean.splitlines():
                    if line.strip():
                        parts = line.split(';')
                        all_rows.append(parts + [fname])
                file_count += 1

            if not all_rows:
                _log(tag, 'Sin archivos / sin datos')
                return {}

            # Determinar max columnas (SAP varía)
            max_cols = max(len(r) for r in all_rows)
            # Normalizar a misma longitud
            for r in all_rows:
                while len(r) < max_cols:
                    r.append(None)

            # Columnas: TipoRegistro, C1..C14, NombreArchivo
            col_names = ['TipoRegistro'] + [f'C{i}' for i in range(1, max_cols - 1)] + ['NombreArchivo']
            # Ajustar si hay más columnas de las esperadas
            col_names = col_names[:max_cols]

            # Crear tabla DuckDB desde lista de listas
            self.con.execute("DROP TABLE IF EXISTS raw_cartoning")
            placeholders = ', '.join([f'col{i} VARCHAR' for i in range(max_cols)])
            self.con.execute(f"CREATE TABLE raw_cartoning ({placeholders})")

            # Insertar batch
            self.con.executemany(
                f"INSERT INTO raw_cartoning VALUES ({', '.join(['?'] * max_cols)})",
                all_rows
            )

            # Renombrar columnas y aplicar trim vectorizado
            rename_clauses = []
            for i, name in enumerate(col_names):
                rename_clauses.append(f"TRIM(col{i}) AS {name}")

            query = f"""
                SELECT {', '.join(rename_clauses)}
                FROM raw_cartoning
                WHERE TRIM(COALESCE(col0, '')) <> ''
            """
            result = self.con.execute(query).arrow()
            
            _log(tag, f'OK: {file_count} archivos → {result.num_rows} filas en {time.time()-t0:.2f}s')
            return {'Staging_EWM_Cartoning': result}

        except Exception as e:
            _log(tag, f'ERROR: {e}')
            return {}

    # ═══════════════════════════════════════════════════════════════
    # FUENTE 2: WAVECONFIRM
    # ═══════════════════════════════════════════════════════════════

    def batch_waveconfirm(self, processing_dir: str) -> dict:
        """Lee y limpia todos los archivos de WaveConfirm.
        
        Returns:
            {'Staging_EWM_WaveConfirm': pyarrow.Table} o {} si vacío
        """
        tag = 'DUCK-WAVE'
        t0 = time.time()
        glob_pattern = os.path.join(processing_dir, '*.txt').replace('\\', '/')

        try:
            result = self.con.execute(f"""
                SELECT 
                    TRIM(column0)  AS WaveID,
                    TRIM(column1)  AS PedidoID,
                    TRIM(column2)  AS columna0,
                    TRIM(column3)  AS CajaID,
                    TRIM(column4)  AS columna_extra,
                    filename       AS NombreArchivo
                FROM read_csv(
                    '{glob_pattern}',
                    delim = ';',
                    header = false,
                    columns = {{
                        'column0': 'VARCHAR',
                        'column1': 'VARCHAR',
                        'column2': 'VARCHAR',
                        'column3': 'VARCHAR',
                        'column4': 'VARCHAR'
                    }},
                    filename = true,
                    encoding = 'latin1',
                    ignore_errors = true,
                    null_padding = true
                )
                WHERE TRIM(COALESCE(column0, '')) <> ''
            """).arrow()

            # Extraer solo basename del filename
            result = self._fix_filename_column(result)

            _log(tag, f'OK: {result.num_rows} filas en {time.time()-t0:.2f}s')
            return {'Staging_EWM_WaveConfirm': result}

        except Exception as e:
            _log(tag, f'ERROR: {e}')
            return {}

    # ═══════════════════════════════════════════════════════════════
    # FUENTE 3: OUTBOUND DELIVERY (SHP_OBDLV_SAVE_REPLICA)
    # ═══════════════════════════════════════════════════════════════

    def batch_outbound_delivery(self, processing_dir: str) -> dict:
        """Lee y limpia archivos IDoc de OutboundDelivery.
        
        Estructura: segmentos E1BPOBDLVHDR, E1BPOBDLVITEM, E1BPADR1, E1BPEXTC
        Retorna 2 tablas staging.
        
        Returns:
            {'Staging_EWM_OutboundDelivery_Header': arrow, 
             'Staging_EWM_OutboundDelivery_Items': arrow} o {} si vacío
        """
        tag = 'DUCK-OBD'
        t0 = time.time()

        try:
            headers_data = []
            items_data = []

            for fname in sorted(os.listdir(processing_dir)):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.join(processing_dir, fname)
                with open(fpath, 'r', encoding='latin-1', errors='replace') as f:
                    lines = [line.strip() for line in f if line.strip()]

                current_delivery_id = None
                current_header = {}
                current_block_lines = []

                for line in lines:
                    cols = line.split(';')
                    seg = cols[0].strip() if cols else ''

                    if seg == 'E1BPOBDLVHDR':
                        # Flush previous
                        if current_delivery_id and current_header:
                            current_header = self._enrich_obd_header(current_header, current_block_lines)
                            current_header['NombreArchivo'] = fname
                            headers_data.append(current_header)

                        current_delivery_id = cols[1].strip() if len(cols) > 1 else None
                        peso = cols[6].strip() if len(cols) > 6 else None
                        volumen = cols[10].strip() if len(cols) > 10 else None
                        current_header = {
                            'Delivery_ID': current_delivery_id,
                            'Peso_Bruto': peso if peso else None,
                            'Volumen': volumen if volumen else None,
                        }
                        current_block_lines = [line]

                    elif current_delivery_id:
                        current_block_lines.append(line)
                        if seg == 'E1BPOBDLVITEM':
                            items_data.append({
                                'Delivery_ID_FK': cols[1].strip() if len(cols) > 1 else None,
                                'Item_Number': cols[2].strip() if len(cols) > 2 else None,
                                'Material_SKU': cols[3].strip() if len(cols) > 3 else None,
                                'Descripcion': cols[5].strip() if len(cols) > 5 else None,
                                'Cantidad': cols[8].strip() if len(cols) > 8 else None,
                                'Unidad_Medida': cols[9].strip() if len(cols) > 9 else None,
                                'Peso_Neto_Item': cols[15].strip() if len(cols) > 15 else None,
                                'NombreArchivo': fname,
                            })

                # Flush last block
                if current_delivery_id and current_header:
                    current_header = self._enrich_obd_header(current_header, current_block_lines)
                    current_header['NombreArchivo'] = fname
                    headers_data.append(current_header)

            if not headers_data:
                _log(tag, 'Sin datos de cabecera')
                return {}

            # Limpiar con DuckDB vectorizado
            self.con.execute("DROP TABLE IF EXISTS raw_obd_hdr")
            self.con.execute("DROP TABLE IF EXISTS raw_obd_itm")

            self.con.execute("CREATE TABLE raw_obd_hdr AS SELECT * FROM ?", [pa.Table.from_pylist(headers_data)])
            hdr_result = self.con.execute("""
                SELECT 
                    TRIM(Delivery_ID) AS Delivery_ID,
                    TRY_CAST(REPLACE(NULLIF(TRIM(Peso_Bruto), ''), ',', '.') AS DECIMAL(18,3)) AS Peso_Bruto,
                    TRY_CAST(REPLACE(NULLIF(TRIM(Volumen), ''), ',', '.') AS DECIMAL(18,3)) AS Volumen,
                    TRIM(Destinatario) AS Destinatario,
                    TRIM(Direccion) AS Direccion,
                    TRIM(Region) AS Region,
                    TRIM(Transportista) AS Transportista,
                    TRIM(Fecha_Entrega) AS Fecha_Entrega,
                    NombreArchivo
                FROM raw_obd_hdr
                WHERE TRIM(COALESCE(Delivery_ID, '')) <> ''
            """).arrow()

            if items_data:
                self.con.execute("CREATE TABLE raw_obd_itm AS SELECT * FROM ?", [pa.Table.from_pylist(items_data)])
                itm_result = self.con.execute("""
                    SELECT 
                        TRIM(Delivery_ID_FK) AS Delivery_ID_FK,
                        TRIM(Item_Number) AS Item_Number,
                        TRIM(Material_SKU) AS Material_SKU,
                        TRIM(Descripcion) AS Descripcion,
                        TRY_CAST(REPLACE(NULLIF(TRIM(Cantidad), ''), ',', '.') AS DECIMAL(18,3)) AS Cantidad,
                        TRIM(Unidad_Medida) AS Unidad_Medida,
                        TRY_CAST(REPLACE(NULLIF(TRIM(Peso_Neto_Item), ''), ',', '.') AS DECIMAL(18,3)) AS Peso_Neto_Item,
                        NombreArchivo
                    FROM raw_obd_itm
                    WHERE TRIM(COALESCE(Delivery_ID_FK, '')) <> ''
                """).arrow()
            else:
                itm_result = pa.table({'Delivery_ID_FK': [], 'Item_Number': [], 'Material_SKU': [],
                                       'Descripcion': [], 'Cantidad': [], 'Unidad_Medida': [],
                                       'Peso_Neto_Item': [], 'NombreArchivo': []})

            _log(tag, f'OK: {hdr_result.num_rows} headers, {itm_result.num_rows} items en {time.time()-t0:.2f}s')
            return {
                'Staging_EWM_OutboundDelivery_Header': hdr_result,
                'Staging_EWM_OutboundDelivery_Items': itm_result,
            }

        except Exception as e:
            _log(tag, f'ERROR: {e}')
            return {}

    @staticmethod
    def _enrich_obd_header(header: dict, block_lines: list) -> dict:
        """Enriquecer cabecera OBD con datos de E1BPADR1 y E1BPEXTC."""
        enriched = header.copy()
        enriched.setdefault('Destinatario', None)
        enriched.setdefault('Direccion', None)
        enriched.setdefault('Region', None)
        enriched.setdefault('Transportista', None)
        enriched.setdefault('Fecha_Entrega', None)

        for line in block_lines:
            cols = line.split(';')
            seg = cols[0].strip() if cols else ''
            if seg == 'E1BPADR1':
                enriched['Destinatario'] = cols[3].strip() if len(cols) > 3 else None
                ciudad = cols[8].strip() if len(cols) > 8 else ''
                calle = cols[16].strip() if len(cols) > 16 else ''
                enriched['Direccion'] = f"{calle} {ciudad}".strip() or None
                enriched['Region'] = cols[28].strip() if len(cols) > 28 else None
            elif seg == 'E1BPEXTC':
                z_field = cols[1].strip() if len(cols) > 1 else None
                z_value = cols[2].strip() if len(cols) > 2 else None
                if z_field == 'ZCARRIER_NAME':
                    enriched['Transportista'] = z_value
                elif z_field == 'ZDELV_DATE':
                    enriched['Fecha_Entrega'] = z_value
        return enriched

    # ═══════════════════════════════════════════════════════════════
    # FUENTE 4: OUTBOUND DELIVERY CONFIRM (SHP_OBDLV_CONFIRM_DECENTRAL)
    # ═══════════════════════════════════════════════════════════════

    def batch_outbound_delivery_confirm(self, processing_dir: str) -> dict:
        """Lee y limpia archivos IDoc de OutboundDeliveryConfirm.
        
        Returns:
            dict con 6 tablas staging como pyarrow.Table, o {} si vacío
        """
        tag = 'DUCK-OBDC'
        t0 = time.time()

        cabecera_data = []
        posiciones_data = []
        control_data = []
        unidades_data = []
        contenido_data = []
        extensiones_data = []

        try:
            for fname in sorted(os.listdir(processing_dir)):
                if not fname.lower().endswith('.txt'):
                    continue
                fpath = os.path.join(processing_dir, fname)
                with open(fpath, 'r', encoding='latin-1', errors='replace') as f:
                    lines = [line.strip() for line in f if line.strip()]

                current_delivery_id = None

                for line in lines:
                    cols = [c.strip() for c in line.split(';')]
                    seg = cols[0] if cols else ''

                    # Identificar número de entrega
                    if len(cols) > 1 and cols[1] and cols[1].isdigit():
                        current_delivery_id = cols[1]

                    # CABECERA
                    if seg in ('E1BPOBDLVHDRCON', 'E1BPOBDLVHDRCTRLCON'):
                        if current_delivery_id and not any(
                            c['Numero_Entrega'] == current_delivery_id for c in cabecera_data
                            if c['NombreArchivo'] == fname
                        ):
                            cabecera_data.append({
                                'Numero_Entrega': current_delivery_id,
                                'Fecha_WSHDRLFDAT': None,
                                'Fecha_WSHDRWADTI': None,
                                'NombreArchivo': fname,
                            })

                    elif seg == 'E1BPDLVDEADLN' and current_delivery_id:
                        fecha_tipo = cols[2] if len(cols) > 2 else None
                        fecha_valor = cols[3] if len(cols) > 3 else None
                        for cab in cabecera_data:
                            if cab['Numero_Entrega'] == current_delivery_id and cab['NombreArchivo'] == fname:
                                if fecha_tipo == 'WSHDRLFDAT':
                                    cab['Fecha_WSHDRLFDAT'] = fecha_valor
                                elif fecha_tipo == 'WSHDRWADTI':
                                    cab['Fecha_WSHDRWADTI'] = fecha_valor

                    # POSICIONES
                    elif seg == 'E1BPOBDLVITEMCON' and current_delivery_id:
                        posiciones_data.append({
                            'Numero_Entrega': current_delivery_id,
                            'Numero_Posicion': cols[2] if len(cols) > 2 else None,
                            'Pedido_Ref': cols[3] if len(cols) > 3 else None,
                            'Material_SKU': cols[4] if len(cols) > 4 else None,
                            'Cantidad': cols[5] if len(cols) > 5 else None,
                            'Unidad': cols[8] if len(cols) > 8 else None,
                            'NombreArchivo': fname,
                        })

                    # CONTROL POSICIONES
                    elif seg == 'E1BPOBDLVITEMCTRLCON' and current_delivery_id:
                        control_data.append({
                            'Numero_Entrega': current_delivery_id,
                            'Numero_Posicion': cols[2] if len(cols) > 2 else None,
                            'Flag_Confirmacion': cols[3] if len(cols) > 3 else None,
                            'NombreArchivo': fname,
                        })

                    # UNIDADES HU
                    elif seg == 'E1BPDLVHDUNHDR' and current_delivery_id:
                        unidades_data.append({
                            'Numero_Entrega': current_delivery_id,
                            'ID_Unidad_Manipulacion': cols[2] if len(cols) > 2 else None,
                            'Tipo_Embalaje': cols[3] if len(cols) > 3 else None,
                            'HU_Nivel': cols[4] if len(cols) > 4 else None,
                            'Numero_Externo': cols[5] if len(cols) > 5 else None,
                            'Cantidad_HU': cols[6] if len(cols) > 6 else None,
                            'NombreArchivo': fname,
                        })

                    # CONTENIDO EMBALAJE
                    elif seg == 'E1BPDLVHDUNITM':
                        contenido_data.append({
                            'ID_Unidad_Manipulacion_Padre': cols[1] if len(cols) > 1 else None,
                            'ID_Unidad_Manipulacion_Hijo': cols[2] if len(cols) > 2 else None,
                            'Numero_Entrega': cols[3] if len(cols) > 3 else None,
                            'Numero_Posicion': cols[4] if len(cols) > 4 else None,
                            'Cantidad_Empacada': cols[5] if len(cols) > 5 else None,
                            'Unidad': cols[6] if len(cols) > 6 else None,
                            'Material_SKU': cols[7] if len(cols) > 7 else None,
                            'Nivel_HU': cols[8] if len(cols) > 8 else None,
                            'NombreArchivo': fname,
                        })

                    # EXTENSIONES
                    elif seg == 'E1BPEXTC':
                        extensiones_data.append({
                            'Nombre_Campo': cols[1] if len(cols) > 1 else None,
                            'ID_Referencia': cols[2] if len(cols) > 2 else None,
                            'Valor_1': cols[3] if len(cols) > 3 else None,
                            'Valor_2': cols[4] if len(cols) > 4 else None,
                            'Valor_3': cols[5] if len(cols) > 5 else None,
                            'NombreArchivo': fname,
                        })

            if not cabecera_data:
                _log(tag, 'Sin datos de cabecera')
                return {}

            # Limpiar con DuckDB vectorizado (TRIM + cast numéricos)
            tables_raw = {
                'cab': (cabecera_data, 'Staging_EWM_OBDConfirm_Cabecera'),
                'pos': (posiciones_data, 'Staging_EWM_OBDConfirm_Posiciones'),
                'ctl': (control_data, 'Staging_EWM_OBDConfirm_Control_Posiciones'),
                'uni': (unidades_data, 'Staging_EWM_OBDConfirm_Unidades_HDR'),
                'con': (contenido_data, 'Staging_EWM_OBDConfirm_Contenido_Embalaje'),
                'ext': (extensiones_data, 'Staging_EWM_OBDConfirm_Extensiones'),
            }

            result = {}

            # Cabecera — solo trim
            if cabecera_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_cab")
                self.con.execute("CREATE TABLE raw_obdc_cab AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(cabecera_data)])
                result['Staging_EWM_OBDConfirm_Cabecera'] = self.con.execute("""
                    SELECT TRIM(Numero_Entrega) AS Numero_Entrega,
                           TRIM(Fecha_WSHDRLFDAT) AS Fecha_WSHDRLFDAT,
                           TRIM(Fecha_WSHDRWADTI) AS Fecha_WSHDRWADTI,
                           NombreArchivo
                    FROM raw_obdc_cab
                    WHERE TRIM(COALESCE(Numero_Entrega, '')) <> ''
                """).arrow()

            # Posiciones — trim + cast cantidad
            if posiciones_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_pos")
                self.con.execute("CREATE TABLE raw_obdc_pos AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(posiciones_data)])
                result['Staging_EWM_OBDConfirm_Posiciones'] = self.con.execute("""
                    SELECT TRIM(Numero_Entrega) AS Numero_Entrega,
                           TRIM(Numero_Posicion) AS Numero_Posicion,
                           TRIM(Pedido_Ref) AS Pedido_Ref,
                           TRIM(Material_SKU) AS Material_SKU,
                           TRIM(REPLACE(NULLIF(TRIM(Cantidad), ''), ',', '.')) AS Cantidad,
                           TRIM(Unidad) AS Unidad,
                           NombreArchivo
                    FROM raw_obdc_pos
                    WHERE TRIM(COALESCE(Numero_Entrega, '')) <> ''
                """).arrow()

            # Control
            if control_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_ctl")
                self.con.execute("CREATE TABLE raw_obdc_ctl AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(control_data)])
                result['Staging_EWM_OBDConfirm_Control_Posiciones'] = self.con.execute("""
                    SELECT TRIM(Numero_Entrega) AS Numero_Entrega,
                           TRIM(Numero_Posicion) AS Numero_Posicion,
                           TRIM(Flag_Confirmacion) AS Flag_Confirmacion,
                           NombreArchivo
                    FROM raw_obdc_ctl
                    WHERE TRIM(COALESCE(Numero_Entrega, '')) <> ''
                """).arrow()

            # Unidades HU — trim + cast cantidad
            if unidades_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_uni")
                self.con.execute("CREATE TABLE raw_obdc_uni AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(unidades_data)])
                result['Staging_EWM_OBDConfirm_Unidades_HDR'] = self.con.execute("""
                    SELECT TRIM(Numero_Entrega) AS Numero_Entrega,
                           TRIM(ID_Unidad_Manipulacion) AS ID_Unidad_Manipulacion,
                           TRIM(Tipo_Embalaje) AS Tipo_Embalaje,
                           TRIM(HU_Nivel) AS HU_Nivel,
                           TRIM(Numero_Externo) AS Numero_Externo,
                           TRIM(REPLACE(NULLIF(TRIM(Cantidad_HU), ''), ',', '.')) AS Cantidad_HU,
                           NombreArchivo
                    FROM raw_obdc_uni
                    WHERE TRIM(COALESCE(Numero_Entrega, '')) <> ''
                """).arrow()

            # Contenido embalaje — trim + cast cantidad
            if contenido_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_con")
                self.con.execute("CREATE TABLE raw_obdc_con AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(contenido_data)])
                result['Staging_EWM_OBDConfirm_Contenido_Embalaje'] = self.con.execute("""
                    SELECT TRIM(ID_Unidad_Manipulacion_Padre) AS ID_Unidad_Manipulacion_Padre,
                           TRIM(ID_Unidad_Manipulacion_Hijo) AS ID_Unidad_Manipulacion_Hijo,
                           TRIM(Numero_Entrega) AS Numero_Entrega,
                           TRIM(Numero_Posicion) AS Numero_Posicion,
                           TRIM(REPLACE(NULLIF(TRIM(Cantidad_Empacada), ''), ',', '.')) AS Cantidad_Empacada,
                           TRIM(Unidad) AS Unidad,
                           TRIM(Material_SKU) AS Material_SKU,
                           TRIM(Nivel_HU) AS Nivel_HU,
                           NombreArchivo
                    FROM raw_obdc_con
                """).arrow()

            # Extensiones — solo trim
            if extensiones_data:
                self.con.execute("DROP TABLE IF EXISTS raw_obdc_ext")
                self.con.execute("CREATE TABLE raw_obdc_ext AS SELECT * FROM ?",
                                 [pa.Table.from_pylist(extensiones_data)])
                result['Staging_EWM_OBDConfirm_Extensiones'] = self.con.execute("""
                    SELECT TRIM(Nombre_Campo) AS Nombre_Campo,
                           TRIM(ID_Referencia) AS ID_Referencia,
                           TRIM(Valor_1) AS Valor_1,
                           TRIM(Valor_2) AS Valor_2,
                           TRIM(Valor_3) AS Valor_3,
                           NombreArchivo
                    FROM raw_obdc_ext
                """).arrow()

            # Resumen
            for tbl_name, tbl in result.items():
                short = tbl_name.replace('Staging_EWM_OBDConfirm_', '')
                _log(tag, f'  {short}: {tbl.num_rows} filas')
            _log(tag, f'OK: procesado en {time.time()-t0:.2f}s')

            return result

        except Exception as e:
            _log(tag, f'ERROR: {e}')
            return {}

    # ═══════════════════════════════════════════════════════════════
    # UTILIDADES
    # ═══════════════════════════════════════════════════════════════

    @staticmethod
    def _fix_filename_column(table: pa.Table) -> pa.Table:
        """Reemplaza rutas completas por solo el basename en columna NombreArchivo."""
        idx = table.schema.get_field_index('NombreArchivo')
        if idx < 0:
            return table
        col = table.column('NombreArchivo')
        basenames = pa.array([os.path.basename(v.as_py()) if v.is_valid else None for v in col])
        return table.set_column(idx, 'NombreArchivo', basenames)
