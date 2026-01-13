import os
import re
import pandas as pd
from io import StringIO

class FileParser:
    """Responsable de transformar archivos crudos en datos estructurados."""
    
    @staticmethod
    def parse_cartoning_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser para archivos de Cartoning"""
        try:
            # 1. Leer y corregir formato (Regla de negocio de limpieza)
            with open(file_path, 'r', encoding='latin-1', errors='replace') as f:
                raw_content = f.read()
            
            # Regex: Insertar separador donde faltan espacios
            clean_content = re.sub(r'(\d)\s{2,}(\d)', r'\1;\2', raw_content)
            
            # 2. Convertir a DataFrame
            df = pd.read_csv(StringIO(clean_content), sep=';', header=None, on_bad_lines='skip', dtype=str)
            df = df.where(pd.notnull(df), None) # Null safety para SQL
            
            # 3. Enriquecer
            df['NombreArchivo'] = os.path.basename(file_path)
            
            # 4. Normalizar columnas para el Insert Masivo
            cols_map = {0: 'TipoRegistro'}
            for i in range(1, 15): 
                cols_map[i] = f'C{i}'
            df = df.rename(columns=cols_map)
            
            # Filtrar solo columnas válidas
            expected_cols = list(cols_map.values()) + ['NombreArchivo']
            return df[[c for c in df.columns if c in expected_cols]]
            
        except Exception as e:
            print(f"Error parseando Cartoning {os.path.basename(file_path)}: {e}")
            return None
    
    @staticmethod
    def parse_waveconfirm_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser para archivos de WaveConfirm"""
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
            df = df.dropna(axis=1, how='all')
            
            # Null safety para SQL
            df = df.where(pd.notnull(df), None)
            
            # Enriquecer con nombre de archivo
            df['NombreArchivo'] = os.path.basename(file_path)
            
            return df
            
        except Exception as e:
            print(f"Error parseando WaveConfirm {os.path.basename(file_path)}: {e}")
            return None
    
    @staticmethod
    def parse_to_dataframe(file_path: str) -> pd.DataFrame:
        """Parser genérico - mantiene compatibilidad con código legacy"""
        return FileParser.parse_cartoning_to_dataframe(file_path)