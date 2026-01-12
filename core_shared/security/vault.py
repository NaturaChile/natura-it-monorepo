import os

class Vault:
    @staticmethod
    def get_secret(key_name: str, default: str = None) -> str:
        val = os.getenv(key_name)
        if val is None:
            if default is not None:
                return default
            # Opcional: Lanzar error si falta una variable crítica
            print(f"⚠️ Advertencia: Variable {key_name} no encontrada en el entorno.")
            return ""
        return val