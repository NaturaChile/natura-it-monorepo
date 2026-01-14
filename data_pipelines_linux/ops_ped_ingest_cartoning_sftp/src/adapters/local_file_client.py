import os
import shutil
from typing import List, Dict
from dataclasses import dataclass

@dataclass
class FileInfo:
    """Información de archivo para compatibilidad con StateManager"""
    filename: str
    full_path: str  # Ruta completa del archivo
    mtime: float
    size: int

class LocalFileClient:
    """Cliente para leer archivos directamente de carpetas locales (sin copia)"""
    
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
        Retorna lista con rutas completas para procesamiento directo.
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
                        full_path=full_path,
                        mtime=stat.st_mtime,
                        size=stat.st_size
                    ))
            
            return files
            
        except Exception as e:
            print(f"Error listando archivos en {self.source_path}: {e}")
            return []
    
    def get_file_path(self, filename: str) -> str:
        """
        Retorna la ruta completa de un archivo.
        
        Args:
            filename: Nombre del archivo
            
        Returns:
            Ruta completa del archivo
        """
        return os.path.join(self.source_path, filename)
    
    def close(self):
        """Método para compatibilidad con interfaz SFTP (no hace nada)"""
        pass
