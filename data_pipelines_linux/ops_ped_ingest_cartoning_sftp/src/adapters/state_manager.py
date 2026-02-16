"""
StateManager — Rastreo de estado por lotes.

Cambios v2:
  - mark_batch_processed(): registra un lote completo de archivos de golpe
  - Mantiene retrocompatibilidad con métodos individuales
  - Guarda timestamp ISO y fuente para auditoría
"""

import os
import json
from datetime import datetime


class StateManager:
    def __init__(self, state_file_path: str):
        self.path = state_file_path
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save(self):
        with open(self.path, 'w') as f:
            json.dump(self.state, f, indent=4)

    # ─── Métodos legacy (retrocompatibilidad) ───────────────────

    def is_new_or_modified(self, filename: str, mtime: int, size: int) -> bool:
        stored = self.state.get(filename)
        if not stored:
            return True
        if mtime > stored.get('mtime', 0) or size != stored.get('size', 0):
            return True
        return False

    def register_download(self, filename: str, mtime: int, size: int):
        self.state[filename] = {
            'mtime': mtime,
            'size': size,
            'sql_ok': False
        }
        self.save()

    def mark_as_processed_in_sql(self, filename: str):
        if filename in self.state:
            self.state[filename]['sql_ok'] = True
        self.save()

    def is_pending_sql(self, filename: str) -> bool:
        record = self.state.get(filename)
        return not record or not record.get('sql_ok', False)

    # ─── Métodos nuevos v2: batch ───────────────────────────────

    def mark_batch_processed(self, source_name: str, filenames: list):
        """Registra un lote completo como procesado exitosamente.
        
        Args:
            source_name: Nombre de la fuente (Cartoning, WaveConfirm, etc.)
            filenames: Lista de nombres de archivo procesados
        """
        ts = datetime.now().isoformat()
        for fname in filenames:
            state_key = f"{source_name}:{fname}"
            self.state[state_key] = {
                'sql_ok': True,
                'processed_at': ts,
                'source': source_name,
            }
        self.save()

    def is_file_processed(self, source_name: str, filename: str) -> bool:
        """Verifica si un archivo específico ya fue procesado."""
        state_key = f"{source_name}:{filename}"
        record = self.state.get(state_key)
        return record is not None and record.get('sql_ok', False)