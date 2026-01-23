"""Helper simple para leer secretos (usa Vault central)."""
import os
from core_shared.security.vault import Vault


def get_secret(key: str):
    v = Vault.get_secret(key)
    if v:
        return v
    return os.getenv(key)
