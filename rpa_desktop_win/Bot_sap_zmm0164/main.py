"""
main.py

Punto de entrada del robot ZMM0164.
Solo tiene una responsabilidad: leer la configuración e iniciar el caso de uso.
No contiene lógica de negocio ni detalles técnicos.

Uso:
    python main.py
"""

import sys

# Asegurar que el módulo src está disponible
sys.path.insert(0, str(__file__.rsplit("\\", 1)[0]))

from src.domain.export_data import (
    ExportConfig,
    SAPCredentials,
    SAPConnection,
)
from src.use_cases.release_process import ExportZMM0164UseCase


# ============================================
# CONFIGURACIÓN
# ============================================

# Parámetros de conexión a SAP
SAP_CONNECTION = SAPConnection(
    sap_logon_path=r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
    connection_name="1.02 - PRD - Produção/Producción",
    transaction="zmm0164",
)

# Credenciales
CREDENTIALS = SAPCredentials(
    client="210",
    user="BOTSCL",
    password="La.Nueva.Clave.2026",
    language="ES",
)

# Configuración de exportación
EXPORT_CONFIG = ExportConfig(
    material_code="4100",
    output_folder=r"Z:\Publico\RPA\Plan Chile\zmm0164",
    file_format="XLS",
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
