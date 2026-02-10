import os
import re
import time
import pandas as pd
from io import StringIO
from datetime import datetime

def _log(tag: str, msg: str):
    """Log centralizado con timestamp y etapa."""
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")

class FileParser:
    """Responsable de transformar archivos crudos en datos estructurados."""
    
    @staticmethod
    def _safe_numeric(value: str):
        """Convierte string SAP a valor numérico seguro para DECIMAL.
        Retorna None si vacío/solo espacios (evita error varchar→decimal)."""
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned if cleaned else None
    
    @staticmethod
    def parse_cartoning_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser para archivos de Cartoning"""
        fname = os.path.basename(file_path)
        _log('PARSER-CART', f'Inicio parseo: {fname}')
        t0 = time.time()
        try:
            # 1. Leer y corregir formato (Regla de negocio de limpieza)
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                raw_content = f.read()
            
            file_size_kb = len(raw_content) / 1024
            _log('PARSER-CART', f'  Archivo leído: {file_size_kb:.1f} KB')
            
            # Regex: Insertar separador donde faltan espacios
            clean_content = re.sub(r'(\d)\s{2,}(\d)', r'\1;\2', raw_content)
            
            # 2. Convertir a DataFrame
            df = pd.read_csv(StringIO(clean_content), sep=';', header=None, on_bad_lines='skip', dtype=str)
            df = df.where(pd.notnull(df), None) # Null safety para SQL
            
            # 3. Enriquecer
            df['NombreArchivo'] = fname
            
            # 4. Normalizar columnas para el Insert Masivo
            cols_map = {0: 'TipoRegistro'}
            for i in range(1, 15): 
                cols_map[i] = f'C{i}'
            df = df.rename(columns=cols_map)
            
            # Filtrar solo columnas válidas
            expected_cols = list(cols_map.values()) + ['NombreArchivo']
            result = df[[c for c in df.columns if c in expected_cols]]
            
            # Resumen por TipoRegistro
            if 'TipoRegistro' in result.columns:
                tipo_counts = result['TipoRegistro'].value_counts().to_dict()
                for tipo, count in tipo_counts.items():
                    _log('PARSER-CART', f'  TipoRegistro={tipo}: {count} filas')
            
            _log('PARSER-CART', f'  OK: {len(result)} filas, {len(result.columns)} cols en {time.time()-t0:.2f}s')
            return result
            
        except Exception as e:
            _log('PARSER-CART', f'  ERROR parseando {fname}: {e}')
            return None
    
    @staticmethod
    def parse_waveconfirm_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser para archivos de WaveConfirm"""
        fname = os.path.basename(file_path)
        _log('PARSER-WAVE', f'Inicio parseo: {fname}')
        t0 = time.time()
        try:
            # Leer archivo con separador ;
            df = pd.read_csv(
                file_path, 
                sep=';', 
                header=None, 
                on_bad_lines='skip',
                dtype=str,
                encoding='latin-1',
                names=['WaveID', 'PedidoID', 'columna0', 'CajaID', 'columna_extra']
            )
            
            # Limpiar columnas vacías al final
            cols_antes = len(df.columns)
            df = df.dropna(axis=1, how='all')
            cols_removidas = cols_antes - len(df.columns)
            if cols_removidas > 0:
                _log('PARSER-WAVE', f'  Columnas vacías removidas: {cols_removidas}')
            
            # Null safety para SQL
            df = df.where(pd.notnull(df), None)
            
            # Enriquecer con nombre de archivo
            df['NombreArchivo'] = fname
            
            # Validar datos
            nulls_wave = df['WaveID'].isna().sum() if 'WaveID' in df.columns else 0
            nulls_pedido = df['PedidoID'].isna().sum() if 'PedidoID' in df.columns else 0
            if nulls_wave > 0 or nulls_pedido > 0:
                _log('PARSER-WAVE', f'  WARN: {nulls_wave} WaveID nulos, {nulls_pedido} PedidoID nulos')
            
            _log('PARSER-WAVE', f'  OK: {len(df)} filas en {time.time()-t0:.2f}s')
            return df
            
        except Exception as e:
            _log('PARSER-WAVE', f'  ERROR parseando {fname}: {e}')
            return None
    
    @staticmethod
    def parse_outbound_delivery_to_dataframes(file_path: str) -> tuple:
        """
        Parser para archivos IDoc SAP (SHP_OBDLV_SAVE_REPLICA).
        Retorna (df_headers, df_items) - dos DataFrames separados.
        """
        fname = os.path.basename(file_path)
        _log('PARSER-OBD', f'Inicio parseo: {fname}')
        t0 = time.time()
        try:
            headers_data = []
            items_data = []
            segment_counts = {}
            
            # Leer archivo línea por línea
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                lines = [line.strip() for line in f.readlines()]
            
            _log('PARSER-OBD', f'  Archivo leído: {len(lines)} líneas')
            
            current_delivery_id = None
            current_header = {}
            current_block_lines = []
            
            for line in lines:
                if not line:
                    continue
                
                cols = line.split(';')
                segment_type = cols[0] if cols else ''
                segment_counts[segment_type] = segment_counts.get(segment_type, 0) + 1
                
                # Detectar inicio de nuevo delivery
                if segment_type == 'E1BPOBDLVHDR':
                    # Procesar bloque anterior si existe
                    if current_delivery_id and current_header:
                        enriched_header = FileParser._enrich_header(current_header, current_block_lines)
                        headers_data.append(enriched_header)
                    
                    # Iniciar nuevo delivery
                    current_delivery_id = cols[1] if len(cols) > 1 else None
                    current_header = {
                        'Delivery_ID': current_delivery_id,
                        'Peso_Bruto': FileParser._safe_numeric(cols[6]) if len(cols) > 6 else None,
                        'Volumen': FileParser._safe_numeric(cols[10]) if len(cols) > 10 else None,
                    }
                    current_block_lines = [line]
                
                elif current_delivery_id:
                    current_block_lines.append(line)
                    
                    # Extraer items
                    if segment_type == 'E1BPOBDLVITEM':
                        items_data.append({
                            'Delivery_ID_FK': cols[1].strip() if len(cols) > 1 else None,
                            'Item_Number': cols[2].strip() if len(cols) > 2 else None,
                            'Material_SKU': cols[3].strip() if len(cols) > 3 else None,
                            'Descripcion': cols[5].strip() if len(cols) > 5 else None,
                            'Cantidad': FileParser._safe_numeric(cols[8]) if len(cols) > 8 else None,
                            'Unidad_Medida': cols[9].strip() if len(cols) > 9 else None,
                            'Peso_Neto_Item': FileParser._safe_numeric(cols[15]) if len(cols) > 15 else None,
                        })
            
            # Procesar último bloque
            if current_delivery_id and current_header:
                enriched_header = FileParser._enrich_header(current_header, current_block_lines)
                headers_data.append(enriched_header)
            
            # Crear DataFrames
            df_headers = pd.DataFrame(headers_data) if headers_data else pd.DataFrame()
            df_items = pd.DataFrame(items_data) if items_data else pd.DataFrame()
            
            # Agregar nombre de archivo
            filename = os.path.basename(file_path)
            if not df_headers.empty:
                df_headers['NombreArchivo'] = filename
            if not df_items.empty:
                df_items['NombreArchivo'] = filename
            
            # Resumen de segmentos encontrados
            for seg, cnt in sorted(segment_counts.items()):
                _log('PARSER-OBD', f'  Segmento {seg}: {cnt} líneas')
            
            h_count = len(df_headers) if not df_headers.empty else 0
            i_count = len(df_items) if not df_items.empty else 0
            _log('PARSER-OBD', f'  OK: {h_count} headers, {i_count} items en {time.time()-t0:.2f}s')
            
            return df_headers, df_items
            
        except Exception as e:
            _log('PARSER-OBD', f'  ERROR parseando {fname}: {e}')
            return None, None
    
    @staticmethod
    def _enrich_header(header_dict: dict, block_lines: list) -> dict:
        """Enriquecer cabecera con datos de E1BPADR1 y E1BPEXTC"""
        enriched = header_dict.copy()
        
        for line in block_lines:
            cols = line.split(';')
            segment_type = cols[0] if cols else ''
            
            # Extraer dirección
            if segment_type == 'E1BPADR1':
                enriched['Destinatario'] = cols[3] if len(cols) > 3 else None
                ciudad = cols[8] if len(cols) > 8 else ''
                calle = cols[16] if len(cols) > 16 else ''
                enriched['Direccion'] = f"{calle} {ciudad}".strip()
                enriched['Region'] = cols[28] if len(cols) > 28 else None
            
            # Pivotar datos Z
            elif segment_type == 'E1BPEXTC':
                z_field = cols[1] if len(cols) > 1 else None
                z_value = cols[2] if len(cols) > 2 else None
                
                if z_field == 'ZCARRIER_NAME':
                    enriched['Transportista'] = z_value
                elif z_field == 'ZDELV_DATE':
                    enriched['Fecha_Entrega'] = z_value
        
        return enriched
    
    @staticmethod
    def parse_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser genérico - mantiene compatibilidad con código legacy"""
        return FileParser.parse_cartoning_to_dataframe(file_path)
    
    @staticmethod
    def parse_outbound_delivery_confirm_to_dataframes(file_path: str) -> tuple:
        """
        Parser para archivos IDoc SAP (SHP_OBDLV_CONFIRM_DECENTRAL).
        Retorna 6 DataFrames separados:
        (df_cabecera, df_posiciones, df_control_posiciones, df_unidades_hdr, df_contenido_embalaje, df_extensiones)
        """
        fname = os.path.basename(file_path)
        _log('PARSER-OBDC', f'Inicio parseo: {fname}')
        t0 = time.time()
        try:
            cabecera_data = []
            posiciones_data = []
            control_posiciones_data = []
            unidades_hdr_data = []
            contenido_embalaje_data = []
            extensiones_data = []
            segment_counts = {}
            
            # Leer archivo línea por línea
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                lines = [line.strip() for line in f.readlines()]
            
            _log('PARSER-OBDC', f'  Archivo leído: {len(lines)} líneas')
            
            current_delivery_id = None
            
            for line in lines:
                if not line:
                    continue
                
                cols = [c.strip() for c in line.split(';')]
                segment_type = cols[0] if cols else ''
                segment_counts[segment_type] = segment_counts.get(segment_type, 0) + 1
                
                # Identificar número de entrega
                if len(cols) > 1 and cols[1] and cols[1].isdigit():
                    current_delivery_id = cols[1]
                
                # TABLA 1: CABECERA_ENTREGA
                if segment_type in ['E1BPOBDLVHDRCON', 'E1BPOBDLVHDRCTRLCON']:
                    if current_delivery_id and not any(c['Numero_Entrega'] == current_delivery_id for c in cabecera_data):
                        cabecera_data.append({
                            'Numero_Entrega': current_delivery_id,
                            'Fecha_WSHDRLFDAT': None,
                            'Fecha_WSHDRWADTI': None
                        })
                
                elif segment_type == 'E1BPDLVDEADLN' and current_delivery_id:
                    # Actualizar fechas en cabecera
                    fecha_tipo = cols[2] if len(cols) > 2 else None
                    fecha_valor = cols[3] if len(cols) > 3 else None
                    
                    for cab in cabecera_data:
                        if cab['Numero_Entrega'] == current_delivery_id:
                            if fecha_tipo == 'WSHDRLFDAT':
                                cab['Fecha_WSHDRLFDAT'] = fecha_valor
                            elif fecha_tipo == 'WSHDRWADTI':
                                cab['Fecha_WSHDRWADTI'] = fecha_valor
                
                # TABLA 2: POSICIONES
                elif segment_type == 'E1BPOBDLVITEMCON' and current_delivery_id:
                    posiciones_data.append({
                        'Numero_Entrega': current_delivery_id,
                        'Numero_Posicion': cols[2] if len(cols) > 2 else None,
                        'Pedido_Ref': cols[3] if len(cols) > 3 else None,
                        'Material_SKU': cols[4] if len(cols) > 4 else None,
                        'Cantidad': cols[5] if len(cols) > 5 else None,
                        'Unidad': cols[8] if len(cols) > 8 else None
                    })
                
                # TABLA 3: CONTROL_POSICIONES
                elif segment_type == 'E1BPOBDLVITEMCTRLCON' and current_delivery_id:
                    control_posiciones_data.append({
                        'Numero_Entrega': current_delivery_id,
                        'Numero_Posicion': cols[2] if len(cols) > 2 else None,
                        'Flag_Confirmacion': cols[3] if len(cols) > 3 else None
                    })
                
                # TABLA 4: UNIDADES_MANIPULACION_HDR (Cajas/Pallets)
                elif segment_type == 'E1BPDLVHDUNHDR' and current_delivery_id:
                    unidades_hdr_data.append({
                        'Numero_Entrega': current_delivery_id,
                        'ID_Unidad_Manipulacion': cols[2] if len(cols) > 2 else None,
                        'Tipo_Embalaje': cols[3] if len(cols) > 3 else None,
                        'HU_Nivel': cols[4] if len(cols) > 4 else None,
                        'Numero_Externo': cols[5] if len(cols) > 5 else None,
                        'Cantidad_HU': cols[6] if len(cols) > 6 else None
                    })
                
                # TABLA 5: CONTENIDO_EMBALAJE (Qué hay en cada caja)
                elif segment_type == 'E1BPDLVHDUNITM':
                    contenido_embalaje_data.append({
                        'ID_Unidad_Manipulacion_Padre': cols[1] if len(cols) > 1 else None,
                        'ID_Unidad_Manipulacion_Hijo': cols[2] if len(cols) > 2 else None,
                        'Numero_Entrega': cols[3] if len(cols) > 3 else None,
                        'Numero_Posicion': cols[4] if len(cols) > 4 else None,
                        'Cantidad_Empacada': cols[5] if len(cols) > 5 else None,
                        'Unidad': cols[6] if len(cols) > 6 else None,
                        'Material_SKU': cols[7] if len(cols) > 7 else None,
                        'Nivel_HU': cols[8] if len(cols) > 8 else None
                    })
                
                # TABLA 6: EXTENSIONES (Datos Z)
                elif segment_type == 'E1BPEXTC':
                    extensiones_data.append({
                        'Nombre_Campo': cols[1] if len(cols) > 1 else None,
                        'ID_Referencia': cols[2] if len(cols) > 2 else None,
                        'Valor_1': cols[3] if len(cols) > 3 else None,
                        'Valor_2': cols[4] if len(cols) > 4 else None,
                        'Valor_3': cols[5] if len(cols) > 5 else None
                    })
            
            # Crear DataFrames
            filename = os.path.basename(file_path)
            
            df_cabecera = pd.DataFrame(cabecera_data) if cabecera_data else pd.DataFrame()
            df_posiciones = pd.DataFrame(posiciones_data) if posiciones_data else pd.DataFrame()
            df_control_posiciones = pd.DataFrame(control_posiciones_data) if control_posiciones_data else pd.DataFrame()
            df_unidades_hdr = pd.DataFrame(unidades_hdr_data) if unidades_hdr_data else pd.DataFrame()
            df_contenido_embalaje = pd.DataFrame(contenido_embalaje_data) if contenido_embalaje_data else pd.DataFrame()
            df_extensiones = pd.DataFrame(extensiones_data) if extensiones_data else pd.DataFrame()
            
            # Agregar nombre de archivo a todos
            for df in [df_cabecera, df_posiciones, df_control_posiciones, df_unidades_hdr, df_contenido_embalaje, df_extensiones]:
                if not df.empty:
                    df['NombreArchivo'] = filename
            
            # Resumen de segmentos
            for seg, cnt in sorted(segment_counts.items()):
                _log('PARSER-OBDC', f'  Segmento {seg}: {cnt} líneas')
            
            _log('PARSER-OBDC', f'  OK: Cab={len(df_cabecera) if not df_cabecera.empty else 0}'
                 f' | Pos={len(df_posiciones) if not df_posiciones.empty else 0}'
                 f' | Ctrl={len(df_control_posiciones) if not df_control_posiciones.empty else 0}'
                 f' | Uni={len(df_unidades_hdr) if not df_unidades_hdr.empty else 0}'
                 f' | Cont={len(df_contenido_embalaje) if not df_contenido_embalaje.empty else 0}'
                 f' | Ext={len(df_extensiones) if not df_extensiones.empty else 0}'
                 f' en {time.time()-t0:.2f}s')
            
            return (df_cabecera, df_posiciones, df_control_posiciones, 
                    df_unidades_hdr, df_contenido_embalaje, df_extensiones)
            
        except Exception as e:
            _log('PARSER-OBDC', f'  ERROR parseando {fname}: {e}')
            return None, None, None, None, None, None
