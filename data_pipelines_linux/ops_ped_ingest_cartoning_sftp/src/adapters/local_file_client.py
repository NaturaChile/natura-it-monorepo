import os
import shutil
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class FileInfo:
    """Información de archivo para compatibilidad con StateManager"""
    filename: str
    mtime: float
    size: int

class LocalFileClient:
    """Cliente para leer archivos de carpetas locales (reemplaza SFTP)"""
    
    def __init__(self, source_path: str):
        """
        Args:
            source_path: Ruta local donde rclone descarga archivos (ej: E:\\Datalake\\Archivos\\EWM\\...)
        """
        self.source_path = source_path
        if not os.path.exists(source_path):
            raise ValueError(f"La ruta no existe: {source_path}")
    
    def list_files(self) -> List[FileInfo]:
        """
        Lista archivos en la carpeta, excluyendo .partial (rclone en descarga).
        Retorna lista compatible con StateManager.
        """
        try:
            files = []
            for filename in os.listdir(self.source_path):
                # Ignorar archivos .partial (rclone descargando)
                if filename.endswith('.partial'):
                    continue
                
                full_path = os.path.join(self.source_path, filename)
                
                # Solo archivos (no directorios)
                if os.path.isfile(full_path):
                    stat = os.stat(full_path)
                    files.append(FileInfo(
                        filename=filename,
                        mtime=stat.st_mtime,
                        size=stat.st_size
                    ))
            
            return files
            
        except Exception as e:
            print(f"Error listando archivos en {self.source_path}: {e}")
            return []
    
    def download_file(self, remote_filename: str, local_path: str) -> bool:
        """
        'Descarga' archivo (realmente copia de carpeta local a landing).
        
        Args:
            remote_filename: Nombre del archivo en source_path
            local_path: Ruta destino completa (landing)
        
        Returns:
            True si se copió exitosamente
        """
        try:
            source_file = os.path.join(self.source_path, remote_filename)
            
            if not os.path.exists(source_file):
                print(f"Archivo no encontrado: {source_file}")
                return False
            
            # Crear directorio destino si no existe
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # Copiar archivo
            shutil.copy2(source_file, local_path)
            return True
            
        except Exception as e:
            print(f"Error copiando {remote_filename}: {e}")
            return False
    
    def close(self):
        """Método para compatibilidad con interfaz SFTP (no hace nada)"""
        pass
