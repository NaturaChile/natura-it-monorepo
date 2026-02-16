import os
import shutil
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

def _log(tag: str, msg: str):
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    print(f"[{ts}] [{tag}] {msg}")

@dataclass
class FileInfo:
    """Información de archivo para compatibilidad con StateManager"""
    filename: str
    full_path: str  # Ruta completa del archivo
    mtime: float
    size: int

class LocalFileClient:
    """Cliente para leer archivos directamente de carpetas locales.
    
    Soporta dos modos:
    - Legacy: lectura directa desde source_path (list_files + get_file_path)
    - Micro-batch: mover archivos a _processing/, leer desde ahí, archivar al terminar
    """
    
    def __init__(self, source_path: str):
        """
        Args:
            source_path: Ruta local donde rclone descarga archivos (ej: E:\\Datalake\\Archivos\\EWM\\...)
        """
        self.source_path = source_path
        # Carpetas de micro-batch (hermanas de source_path)
        parent = os.path.dirname(source_path)
        self.processing_path = os.path.join(parent, "_processing")
        self.archive_path = os.path.join(parent, "_archive")
        
        if not os.path.exists(source_path):
            raise ValueError(f"La ruta no existe: {source_path}")
    
    # ── Modo Legacy (compatibilidad) ──────────────────────────────
    
    def list_files(self) -> List[FileInfo]:
        """
        Lista archivos en la carpeta, excluyendo .partial (rclone en descarga).
        Retorna lista con rutas completas para procesamiento directo.
        """
        return self._scan_dir(self.source_path)
    
    def get_file_path(self, filename: str) -> str:
        return os.path.join(self.source_path, filename)
    
    # ── Modo Micro-batch (nuevo) ──────────────────────────────────
    
    def batch_move_to_processing(self) -> List[FileInfo]:
        """Mueve atómicamente todos los .txt de source_path a _processing/.
        
        Returns:
            Lista de FileInfo con rutas apuntando a _processing/
        """
        os.makedirs(self.processing_path, exist_ok=True)
        
        source_files = self._scan_dir(self.source_path)
        if not source_files:
            return []
        
        moved: List[FileInfo] = []
        for fi in source_files:
            dest = os.path.join(self.processing_path, fi.filename)
            # Intentos con retry para errores temporales (locks/antivirus)
            success = False
            for attempt in range(1, 4):
                try:
                    # Intentar rename/move atómico
                    shutil.move(fi.full_path, dest)
                    success = True
                    break
                except PermissionError as e:
                    _log('FILE-IO', f'Permiso denegado moviendo {fi.filename} (intento {attempt}): {e}')
                except OSError as e:
                    # Windows puede devolver errno 13 / WinError 5
                    _log('FILE-IO', f'Error OS moviendo {fi.filename} (intento {attempt}): {e}')
                # Intentar relajar permisos y reintentar
                try:
                    os.chmod(fi.full_path, 0o666)
                except Exception:
                    pass
                import time
                time.sleep(0.5 * attempt)

            # Fallback: intentar copy2 + remove (útil si el archivo está en otro volumen)
            if not success:
                try:
                    _log('FILE-IO', f'Intentando fallback copy para {fi.filename}')
                    shutil.copy2(fi.full_path, dest)
                    try:
                        os.remove(fi.full_path)
                    except Exception as e_rm:
                        _log('FILE-IO', f'Warning: no se pudo borrar original {fi.filename} tras copy: {e_rm}')
                    success = True
                except Exception as e2:
                    _log('FILE-IO', f'Error moviendo {fi.filename} a _processing (fallback falló): {e2}')

            if success:
                moved.append(FileInfo(
                    filename=fi.filename,
                    full_path=dest,
                    mtime=fi.mtime,
                    size=fi.size
                ))
            else:
                _log('FILE-IO', f'Fallo definitivo moviendo {fi.filename}; se omite por ahora')
        
        _log('FILE-IO', f'Movidos {len(moved)}/{len(source_files)} archivos a _processing/')
        return moved
    
    def archive_processed(self, filenames: List[str]):
        """Mueve archivos ya procesados de _processing/ a _archive/YYYYMMDD/.
        
        Args:
            filenames: Lista de nombres de archivo a archivar
        """
        date_folder = datetime.now().strftime("%Y%m%d")
        dest_dir = os.path.join(self.archive_path, date_folder)
        os.makedirs(dest_dir, exist_ok=True)
        
        archived = 0
        for fname in filenames:
            src = os.path.join(self.processing_path, fname)
            if os.path.exists(src):
                dest = os.path.join(dest_dir, fname)
                try:
                    shutil.move(src, dest)
                    archived += 1
                except Exception as e:
                    _log('FILE-IO', f'Error archivando {fname}: {e}')
                    # Intentar fallback copy
                    try:
                        shutil.copy2(src, dest)
                        try:
                            os.remove(src)
                            archived += 1
                        except Exception:
                            _log('FILE-IO', f'Warning: no se pudo borrar origen {fname} tras copy a archive')
                    except Exception as e2:
                        _log('FILE-IO', f'Fallback archivado falló para {fname}: {e2}')
        
        _log('FILE-IO', f'Archivados {archived}/{len(filenames)} -> {dest_dir}')
    
    def get_processing_path(self) -> str:
        """Retorna ruta de _processing/ (para lectura masiva con DuckDB)."""
        return self.processing_path
    
    def cleanup_processing(self):
        """Limpia carpeta _processing/ (por si quedaron residuos)."""
        if os.path.exists(self.processing_path):
            for f in os.listdir(self.processing_path):
                fp = os.path.join(self.processing_path, f)
                if os.path.isfile(fp):
                    try:
                        os.remove(fp)
                    except Exception as e:
                        _log('FILE-IO', f'No se pudo limpiar {fp}: {e}')
    
    # ── Internos ──────────────────────────────────────────────────
    
    def _scan_dir(self, directory: str) -> List[FileInfo]:
        """Escanea un directorio retornando FileInfo, excluyendo .partial."""
        try:
            files = []
            for filename in os.listdir(directory):
                if filename.endswith('.partial'):
                    continue
                full_path = os.path.join(directory, filename)
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
            _log('FILE-IO', f'Error listando archivos en {directory}: {e}')
            return []
    
    def close(self):
        """Método para compatibilidad con interfaz SFTP (no hace nada)"""
        pass
