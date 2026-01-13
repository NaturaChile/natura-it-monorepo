import os
import json

class StateManager:
    def __init__(self, state_file_path: str):
        self.path = state_file_path
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, 'r') as f: return json.load(f)
            except: pass
        return {}

    def save(self):
        with open(self.path, 'w') as f: json.dump(self.state, f, indent=4)

    def is_new_or_modified(self, filename: str, mtime: int, size: int) -> bool:
        stored = self.state.get(filename)
        if not stored:
            return True
        if mtime > stored['mtime'] or size != stored['size']:
            return True
        return False

    def register_download(self, filename: str, mtime: int, size: int):
        self.state[filename] = {
            'mtime': mtime,
            'size': size,
            'sql_ok': False # Al descargar, aún no está en SQL
        }
        self.save()

    def mark_as_processed_in_sql(self, filename: str):
        if filename in self.state:
            self.state[filename]['sql_ok'] = True
        self.save()
    
    def is_pending_sql(self, filename: str) -> bool:
        # Es pendiente si no existe en el state O si existe pero sql_ok es False
        record = self.state.get(filename)
        return not record or not record.get('sql_ok', False)