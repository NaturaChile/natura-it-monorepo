"""
main.py

Punto de entrada del robot ZMM0164.
Solo tiene una responsabilidad: leer la configuración e iniciar el caso de uso.
No contiene lógica de negocio ni detalles técnicos.

Uso:
    python main.py
"""

import sys
import os

# Asegurar que el módulo src y paquetes del repo raíz están disponibles
# Añadimos el directorio del paquete local y la raíz del repositorio al inicio de sys.path
sys.path.insert(0, os.path.dirname(__file__))
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from src.domain.export_data import (
    ExportConfig,
    SAPCredentials,
    SAPConnection,
)
from src.use_cases.release_process import ExportZMM0164UseCase
from security.vault_helper import get_secret, mount_smb_windows


# ============================================
# CONFIGURACIÓN
# ============================================

# Parámetros de conexión a SAP
SAP_CONNECTION = SAPConnection(
    sap_logon_path=r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
    connection_name="1.02 - PRD - Produção/Producción",
    transaction="zmm0164",
)

# Credenciales desde variables de entorno
CREDENTIALS = SAPCredentials(
    client=get_secret("BOT_ZMM0164_SAP_CLIENT", "210"),
    user=get_secret("BOT_ZMM0164_SAP_USER", "BOTSCL"),
    password=get_secret("BOT_ZMM0164_SAP_PASSWORD"),  # Variable obligatoria
    language=get_secret("BOT_ZMM0164_SAP_LANGUAGE", "ES"),
)

# Credenciales de red para acceder a la carpeta de salida
NET_DOMAIN = get_secret("BOT_ZMM0164_OUTPUT_NET_DOMAIN", "NATURA")
NET_USER = get_secret("BOT_ZMM0164_OUTPUT_NET_USER", "cmancill")
NET_PASSWORD = get_secret("BOT_ZMM0164_OUTPUT_NET_PASSWORD")
NET_UNC_PATH = get_secret("BOT_ZMM0164_OUTPUT_UNC_PATH", r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164")

# Configurar carpeta de salida
OUTPUT_FOLDER = get_secret("BOT_ZMM0164_OUTPUT_FOLDER")

# Estrategia: intentar montaje SMB, pero siempre tener fallback a UNC
if not OUTPUT_FOLDER:
    # Si no hay variable de OUTPUT_FOLDER, intentar montar Z:
    if NET_PASSWORD and NET_UNC_PATH:
        if mount_smb_windows(NET_UNC_PATH, "Z", NET_USER, NET_PASSWORD, NET_DOMAIN):
            OUTPUT_FOLDER = r"Z:\Publico\RPA\Plan Chile\zmm0164"
        else:
            # Si falla montaje, usar UNC directamente
            OUTPUT_FOLDER = NET_UNC_PATH
            print("⚠️  No se pudo montar Z:, usando ruta UNC directamente")
    elif NET_UNC_PATH:
        # Sin credenciales, intentar UNC
        OUTPUT_FOLDER = NET_UNC_PATH
        print("⚠️  Usando ruta UNC sin credenciales adicionales")
    else:
        # Fallback final
        OUTPUT_FOLDER = r"Z:\Publico\RPA\Plan Chile\zmm0164"

print(f"📁 Carpeta de salida configurada: {OUTPUT_FOLDER}")

# Configuración de exportación desde variables de entorno
EXPORT_CONFIG = ExportConfig(
    material_code=get_secret("BOT_ZMM0164_MATERIAL_CODE", "4100"),
    output_folder=OUTPUT_FOLDER,
    file_format=get_secret("BOT_ZMM0164_FILE_FORMAT", "XLS"),
)


# ============================================
# EJECUCIÓN
# ============================================

def main():
    """Función principal que ejecuta el caso de uso."""
    try:
        # Crear instancia del caso de uso
        use_case = ExportZMM0164UseCase(
            sap_connection=SAP_CONNECTION,
            credentials=CREDENTIALS,
            export_config=EXPORT_CONFIG,
        )
        
        # Ejecutar
        use_case.execute()
        
        print("\n" + "=" * 60)
        print("✨ PROCESO COMPLETADO EXITOSAMENTE")
        print("=" * 60)
        return 0
    
    except Exception as e:
        print("\n" + "=" * 60)
        print(f"❌ ERROR CRÍTICO: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
