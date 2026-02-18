"""
config.py

Configuración del proyecto (alternativa a hardcodear en main.py).
Permite manejar múltiples ambientes (desarrollo, testing, producción).
"""

import os
from typing import Optional

# ============================================
# AMBIENTE
# ============================================

ENVIRONMENT = os.getenv("RPA_ENV", "development")  # development | testing | production

print(f"[CONFIG] Ambiente: {ENVIRONMENT}")


# ============================================
# SAP CONNECTION
# ============================================

SAP_CONFIG = {
    "development": {
        "sap_logon_path": r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
        "connection_name": "1.02 - DEV - Desarrollo",
        "transaction": "zmm0164",
    },
    "testing": {
        "sap_logon_path": r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
        "connection_name": "1.02 - TEST - Testing",
        "transaction": "zmm0164",
    },
    "production": {
        "sap_logon_path": r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
        "connection_name": "1.02 - PRD - Produção/Producción",
        "transaction": "zmm0164",
    },
}

SAP_SETTINGS = SAP_CONFIG.get(ENVIRONMENT, SAP_CONFIG["development"])


# ============================================
# CREDENCIALES (desde Variables de Entorno)
# ============================================

# En producción, estas deben estar en:
# - GitHub Secrets (si ejecutas desde Actions)
# - Variables de entorno del sistema (si ejecutas local)

CREDENTIALS_CONFIG = {
    "client": os.getenv("SAP_CLIENT", "210"),
    "user": os.getenv("SAP_USER", "BOTSCL"),
    "password": os.getenv("SAP_PASSWORD", ""),  # ⚠️ Nunca hardcodes contraseñas
    "language": os.getenv("SAP_LANGUAGE", "ES"),
}

if not CREDENTIALS_CONFIG["password"]:
    raise ValueError("SAP_PASSWORD no configurada en variables de entorno")


# ============================================
# EXPORTACIÓN
# ============================================

EXPORT_SETTINGS = {
    "development": {
        "material_code": "4100",
        "output_folder": r"C:\Temp\zmm0164",  # Local en desarrollo
        "file_format": "XLS",
    },
    "testing": {
        "material_code": "4100",
        "output_folder": r"Z:\Publico\RPA\Plan Chile\zmm0164_TEST",  # Carpeta de test
        "file_format": "XLS",
    },
    "production": {
        "material_code": "4100",
        "output_folder": r"Z:\Publico\RPA\Plan Chile\zmm0164",  # Carpeta de producción
        "file_format": "XLS",
    },
}

EXPORT_SETTINGS_CURRENT = EXPORT_SETTINGS.get(ENVIRONMENT, EXPORT_SETTINGS["development"])


# ============================================
# LOGGING
# ============================================

LOG_CONFIG = {
    "development": {
        "level": "DEBUG",
        "file": None,  # Console only
    },
    "testing": {
        "level": "INFO",
        "file": r"logs\zmm0164_test.log",
    },
    "production": {
        "level": "ERROR",
        "file": r"logs\zmm0164_prod.log",
    },
}

LOG_SETTINGS = LOG_CONFIG.get(ENVIRONMENT, LOG_CONFIG["development"])


# ============================================
# TIMEOUTS Y REINTENTOS
# ============================================

RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 5,  # segundos
    "timeout_sap_connect": 30,  # segundos
    "timeout_field_wait": 20,  # segundos
}


# ============================================
# VALIDACIONES
# ============================================

def validate_config() -> bool:
    """Valida que la configuración sea correcta."""
    errors = []
    
    # Validar credenciales
    if not CREDENTIALS_CONFIG["client"]:
        errors.append("SAP_CLIENT no configurada")
    
    if not CREDENTIALS_CONFIG["user"]:
        errors.append("SAP_USER no configurada")
    
    if not CREDENTIALS_CONFIG["password"]:
        errors.append("SAP_PASSWORD no configurada")
    
    # Validar exportación
    if not EXPORT_SETTINGS_CURRENT["material_code"]:
        errors.append("Material code no configurado")
    
    if not EXPORT_SETTINGS_CURRENT["output_folder"]:
        errors.append("Output folder no configurado")
    
    if errors:
        for error in errors:
            print(f"[ERROR] Error de configuración: {error}")
        return False
    
    print("[OK] Configuración válida")
    return True


# ============================================
# FUNCIONES DE UTILIDAD
# ============================================

def get_sap_connection_params() -> dict:
    """Retorna parámetros de conexión SAP."""
    return {
        "sap_logon_path": SAP_SETTINGS["sap_logon_path"],
        "connection_name": SAP_SETTINGS["connection_name"],
        "transaction": SAP_SETTINGS["transaction"],
    }


def get_credentials() -> dict:
    """Retorna credenciales SAP."""
    return CREDENTIALS_CONFIG.copy()


def get_export_config() -> dict:
    """Retorna configuración de exportación."""
    return EXPORT_SETTINGS_CURRENT.copy()


def get_environment() -> str:
    """Retorna el ambiente actual."""
    return ENVIRONMENT


# ============================================
# DEBUG
# ============================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("CONFIGURACIÓN ACTUAL")
    print("=" * 60)
    
    print(f"\nAmbiente: {ENVIRONMENT}")
    
    print("\nSAP Settings:")
    for key, value in SAP_SETTINGS.items():
        print(f"  {key}: {value}")
    
    print("\nCredentials:")
    for key, value in CREDENTIALS_CONFIG.items():
        if key == "password":
            print(f"  {key}: {'*' * len(value)}")  # Ocultar contraseña
        else:
            print(f"  {key}: {value}")
    
    print("\nExport Settings:")
    for key, value in EXPORT_SETTINGS_CURRENT.items():
        print(f"  {key}: {value}")
    
    print("\nLog Settings:")
    for key, value in LOG_SETTINGS.items():
        print(f"  {key}: {value}")
    
    print("\nRetry Config:")
    for key, value in RETRY_CONFIG.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    validate_config()
    print("=" * 60 + "\n")
