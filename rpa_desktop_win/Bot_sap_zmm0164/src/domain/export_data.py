"""
domain/export_data.py

Modelo de datos de dominio para el proceso de exportación ZMM0164.
Define la estructura de datos que se exporta desde SAP.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ExportConfig:
    """Configuración de exportación de datos ZMM0164."""
    
    material_code: str  # Código de material a buscar (ej: "4100")
    output_folder: str  # Ruta de carpeta destino (ej: r"Z:\Publico\RPA\Plan Chile\zmm0164")
    file_format: str = "XLS"  # Formato de exportación
    
    @property
    def filename(self) -> str:
        """Genera nombre de archivo con fecha actual."""
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        return f"zmm0164-{fecha_hoy}.{self.file_format.lower()}"
    
    @property
    def full_path(self) -> str:
        """Retorna la ruta completa del archivo."""
        return f"{self.output_folder}\\{self.filename}"


@dataclass
class SAPCredentials:
    """Credenciales de acceso a SAP."""
    
    client: str  # Cliente SAP (ej: "210")
    user: str  # Usuario (ej: "BOTSCL")
    password: str  # Contraseña
    language: str = "ES"  # Idioma (por defecto español)


@dataclass
class SAPConnection:
    """Parámetros de conexión a SAP."""
    
    sap_logon_path: str  # Ruta a saplogon.exe
    connection_name: str  # Nombre de la conexión (ej: "1.02 - PRD - Produção/Producción")
    transaction: str = "zmm0164"  # Transacción a ejecutar
