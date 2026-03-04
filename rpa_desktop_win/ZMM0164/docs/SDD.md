# Software Design Document (SDD) - Bot SAP ZMM0164
**Exportación Automatizada de Datos de Materiales desde Transacción SAP ZMM0164**

---

## 📋 Metadatos del Documento

| Propiedad | Valor |
|-----------|-------|
| **Versión** | 1.0 |
| **Estado** | ✅ Aprobado para desarrollo TDD |
| **Fecha Creación** | 2026-03-02 |
| **Última Actualización** | 2026-03-02 |
| **Autor** | Equipo RPA - NaturaChile |
| **Proyecto** | SAP RPA Automation - NaturaChile |
| **Repositorio** | `NaturaChile/natura-it-monorepo/rpa_desktop_win/ZMM0164` |
| **Ambiente Objetivo** | DEV, TEST, PROD |
| **Lenguaje** | Python 3.9+ (Windows Server) |

---

## 🎯 Resumen Ejecutivo

### Problema
Exportación **manual** de datos de materiales desde ZMM0164 en SAP:
- ⏱️ **Tiempo:** ~15 minutos por material
- 🔴 **Riesgo:** Errores humanos (omisiones, formato incorrecto)
- 📊 **Volumen:** 240+ materiales/turno requeridos

### Solución
Bot RPA automatizado que:
- ✅ **Reduce tiempo:** <2 minutos por material (7.5x más rápido)
- ✅ **Elimina errores:** 100% consistencia en exportación
- ✅ **Escalable:** Reutilizable para ZMM0165, ZMM0166, etc.
- ✅ **Seguro:** Credenciales centralizadas (Vault), sin hardcoding

### Alcance
| Incluye | Excluye |
|---------|---------|
| ✅ Conexión/Autenticación SAP GUI | ❌ Modificación de datos SAP (solo lectura) |
| ✅ Navegación a ZMM0164 | ❌ Validación de lógica de negocio |
| ✅ Búsqueda de material | ❌ Sincronización con otros sistemas |
| ✅ Exportación a XLS | ❌ Procesamiento de datos post-exportación |
| ✅ Guardado en carpeta compartida | |
| ✅ Cierre seguro y limpio (logout) | |

---

## 🏗️ Arquitectura (DDD - Domain-Driven Design)

### Capas de Separación de Responsabilidades

```
┌──────────────────────────────────────────────────────┐
│            ENTRADA: main.py                          │
│   (Punto único de ejecución - OrquestaFlujo)        │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│        USE_CASES (Lógica de Negocio)                │
│  • ExportZMM0164UseCase                             │
│  • Orquesta adapters                                │
│  • Manejo de errores y reintentos                   │
└────────────────────┬─────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌──────────────────┐    ┌──────────────────┐
│  ADAPTERS        │    │  SECURITY        │
│                  │    │                  │
│ • SAPDriver      │    │ • vault_helper   │
│ • FileAdapter    │    │ • get_secret()   │
│ • SMBMount       │    │ (centralizado)   │
└────────────────────────┬─────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│         DOMAIN (Modelos Puros)                      │
│  • ExportConfig (dataclass)                         │
│  • SAPCredentials (dataclass)                       │
│  • ExportedFile (dataclass)                         │
│  • Exceptions (CustomError, AuthError, etc.)        │
└──────────────────────────────────────────────────────┘
```

### Regla Critica: **CERO Dependencias Externas en Domain**
```python
# ✅ VÁLIDO - Domain puro
@dataclass
class ExportConfig:
    material_code: str
    output_folder: str
    file_format: str = "XLS"
    
    @property
    def filename(self) -> str:
        """Genera nombre sin dependencias"""
        return f"zmm0164-{self.material_code}-{date.today()}.xls"

# ❌ PROHIBIDO - Domain con imports externos
@dataclass
class ExportConfig:
    material_code: str
    
    def __post_init__(self):
        import os  # ❌ PROHIBIDO: Dependencia externa
        self.path = os.path.join(...)
```

---

## 📐 Componentes Arquitectónicos

### 1. **DOMAIN** - Modelos de Negocio Puros

#### 1.1 `src/domain/export_data.py`
```python
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional

class SAPEnvironment(Enum):
    """Ambientes SAP soportados"""
    DESARROLLO = "development"
    TESTING = "testing"
    PRODUCCION = "production"

class FileFormat(Enum):
    """Formatos de exportación soportados"""
    XLS = "XLS"
    XLSX = "XLSX"
    CSV = "CSV"

@dataclass
class SAPCredentials:
    """Credenciales de autenticación SAP (nunca loguear directamente)"""
    client: str                    # Ej: "210"
    user: str                      # Ej: "BOTSCL"
    password: str                  # ⚠️ SENSIBLE - solo en Vault
    language: str = "ES"           # Idioma SAP
    
    def __repr__(self) -> str:
        """Sanitizar credenciales en logs"""
        return f"SAPCredentials(client={self.client}, user={self.user}, language={self.language})"

@dataclass
class ExportConfig:
    """Configuración de exportación (entrada del UseCase)"""
    material_code: str             # Código del material a exportar
    output_folder: str             # Ruta donde guardar archivo
    file_format: FileFormat = FileFormat.XLS
    sap_environment: SAPEnvironment = SAPEnvironment.PRODUCCION
    max_retries: int = 3
    retry_delay_seconds: int = 5
    connection_timeout_seconds: int = 30
    
    def __post_init__(self):
        """Validaciones básicas"""
        if not self.material_code.strip():
            raise ValueError("material_code no puede estar vacío")
        if not self.output_folder.strip():
            raise ValueError("output_folder no puede estar vacío")

@dataclass
class ExportedFile:
    """Resultado exitoso de exportación (salida del UseCase)"""
    filename: str                  # Ej: "zmm0164-4100-2026-03-02.xls"
    full_path: str                 # Ej: "Z:\Publico\RPA\..." o UNC
    file_size_bytes: int
    material_code: str
    exported_at: str               # ISO format timestamp
    sap_user: str                  # Quién ejecutó (para auditoría)

class ExportError(Exception):
    """Error base para exportaciones"""
    code: str
    message: str
    
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")

class SAPConnectionError(ExportError):
    """No se pudo conectar a SAP"""
    pass

class SAPAuthenticationError(ExportError):
    """Credenciales inválidas o usuario sin permisos"""
    pass

class TransactionNotFoundError(ExportError):
    """Transacción ZMM0164 no encontrada o no disponible"""
    pass

class MaterialNotFoundError(ExportError):
    """Material code no existe en SAP"""
    pass

class FileSystemError(ExportError):
    """Error al guardar archivo (disco lleno, sin permisos, etc.)"""
    pass

class ExportTimeoutError(ExportError):
    """Timeout en operación SAP (>30 seg)"""
    pass
```

#### 1.2 Interface/Puerto - `src/domain/sap_port.py`
```python
from abc import ABC, abstractmethod
from typing import Optional
from .export_data import SAPCredentials, ExportedFile

class SAPPort(ABC):
    """Puerto abstracto: qué debe saber hacer un driver SAP"""
    
    @abstractmethod
    def connect(self, connection_name: str, timeout_seconds: int) -> 'SAPPort':
        """Conectar a SAP GUI (retorna self para chaining)"""
        pass
    
    @abstractmethod
    def login(self, credentials: SAPCredentials, timeout_seconds: int) -> 'SAPPort':
        """Autenticarse en SAP (retorna self para chaining)"""
        pass
    
    @abstractmethod
    def navigate_to_transaction(self, transaction_code: str, timeout_seconds: int) -> 'SAPPort':
        """Navegar a transacción (ej: /nzmm0164)"""
        pass
    
    @abstractmethod
    def find_and_export_material(self, material_code: str, output_path: str) -> ExportedFile:
        """Buscar material y exportar a archivo"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """¿Está conectado?"""
        pass
    
    @abstractmethod
    def disconnect(self) -> bool:
        """Desconectar limpiamente (logout + cierre proceso)"""
        pass
```

---

### 2. **ADAPTERS** - Implementación de Infraestructura

#### 2.1 `src/adapters/sap_driver.py` - SAP GUI Automation
```python
from typing import Optional
import time
import logging
from win32com import client as win32_client
from win32com.client import GetObject
import subprocess
import os

from ..domain.export_data import (
    SAPCredentials, ExportedFile, ExportConfig,
    SAPConnectionError, SAPAuthenticationError,
    TransactionNotFoundError, MaterialNotFoundError,
    ExportTimeoutError
)
from ..domain.sap_port import SAPPort

logger = logging.getLogger(__name__)

class SAPDriver(SAPPort):
    """Implementación concreta: interacción con SAP GUI via pywin32"""
    
    def __init__(self, saplogon_path: str):
        self.saplogon_path = saplogon_path
        self.sap_app = None
        self.connection = None
        self.session = None
        self._is_connected = False
        logger.debug(f"SAPDriver initialized with saplogon: {saplogon_path}")
    
    def connect(self, connection_name: str = "PROD", timeout_seconds: int = 30) -> 'SAPDriver':
        """
        Conectar a SAP GUI
        
        Args:
            connection_name: Nombre de conexión en saplogon.ini (ej: "PROD", "TEST")
            timeout_seconds: Timeout máximo de conexión
        
        Returns:
            self (para method chaining)
        
        Raises:
            SAPConnectionError: Si no se puede conectar
            ExportTimeoutError: Si excede timeout
        """
        try:
            logger.info(f"Iniciando conexión a SAP: {connection_name}")
            start_time = time.time()
            
            # Obtener aplicación SAP
            self.sap_app = GetObject("SAPGUI")
            if self.sap_app is None:
                raise SAPConnectionError(
                    "SAP_CONNECT_FAILED",
                    "No se pudo obtener instancia de SAPGUI (¿SAP GUI instalado?)"
                )
            
            # Obtener conexión
            desktop = self.sap_app.GetScriptingEngine.Desktop
            self.connection = desktop.OpenConnection(connection_name, "", "", "")
            
            if self.connection is None:
                raise SAPConnectionError(
                    "SAP_CONNECTION_NOT_FOUND",
                    f"Conexión '{connection_name}' no encontrada en saplogon.ini"
                )
            
            # Obtener sesión
            self.session = self.connection.Children(0)
            self._is_connected = True
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Conexión exitosa en {elapsed:.2f}s")
            return self
            
        except Exception as e:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise ExportTimeoutError(
                    "SAP_CONNECT_TIMEOUT",
                    f"Timeout conectando a SAP ({elapsed:.2f}s > {timeout_seconds}s)"
                )
            if isinstance(e, ExportError):
                raise
            raise SAPConnectionError(
                "SAP_CONNECT_ERROR",
                f"Error conectando a SAP: {str(e)}"
            )
    
    def login(self, credentials: SAPCredentials, timeout_seconds: int = 30) -> 'SAPDriver':
        """
        Autenticarse en SAP
        
        Raises:
            SAPAuthenticationError: Si credenciales inválidas
        """
        if not self._is_connected:
            raise SAPConnectionError(
                "NOT_CONNECTED",
                "Llamar connect() antes de login()"
            )
        
        try:
            logger.info(f"Autenticándose como {credentials.user} en cliente {credentials.client}")
            start_time = time.time()
            
            # Rellenar campos de login
            self.session.FindById("wnd[0]/usr/ctxtSAPUSERID").text = credentials.user
            self.session.FindById("wnd[0]/usr/ctxtSAPPASSWORD").text = credentials.password
            self.session.FindById("wnd[0]/usr/ctxtSAPCLIENT").text = credentials.client
            self.session.FindById("wnd[0]/usr/ctxtSAPLANG").text = credentials.language
            
            # Presionar Enter (enviar login)
            self.session.FindById("wnd[0]").sendVKey(0)
            
            # Esperar a que se procese
            time.sleep(2)
            
            # Validar si hubo modal de error
            try:
                error_modal = self.session.FindById("wnd[1]/usr/ctxtRV50M-MSGID")
                if error_modal:
                    error_text = error_modal.text
                    logger.error(f"❌ Login fallido: {error_text}")
                    raise SAPAuthenticationError(
                        "SAP_AUTH_FAILED",
                        f"Credenciales inválidas o usuario sin acceso: {error_text}"
                    )
            except:
                pass  # No hay modal = éxito
            
            elapsed = time.time() - start_time
            logger.info(f"✅ Login exitoso en {elapsed:.2f}s")
            return self
            
        except ExportError:
            raise
        except Exception as e:
            raise SAPAuthenticationError(
                "SAP_LOGIN_ERROR",
                f"Error en login: {str(e)}"
            )
    
    def navigate_to_transaction(self, transaction_code: str, timeout_seconds: int = 20) -> 'SAPDriver':
        """Navegar a transacción SAP (ej: /nzmm0164)"""
        if not self.session:
            raise SAPConnectionError("NOT_CONNECTED", "Sesión no establecida")
        
        try:
            logger.info(f"Navegando a transacción: {transaction_code}")
            start_time = time.time()
            
            # Field de comando SAP (esquina superior izquierda)
            cmd_field = self.session.FindById("wnd[0]/tbar[0]/okcd")
            cmd_field.text = f"/n{transaction_code}"
            self.session.FindById("wnd[0]").sendVKey(0)  # Enter
            
            # Esperar carga
            time.sleep(2)
            
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise ExportTimeoutError(
                    "TXN_LOAD_TIMEOUT",
                    f"Transacción tardó > {timeout_seconds}s en cargar"
                )
            
            logger.info(f"✅ Transacción {transaction_code} cargada en {elapsed:.2f}s")
            return self
            
        except ExportError:
            raise
        except Exception as e:
            raise TransactionNotFoundError(
                "TXN_NOT_FOUND",
                f"Error navegando a {transaction_code}: {str(e)}"
            )
    
    def find_and_export_material(self, material_code: str, output_path: str) -> ExportedFile:
        """
        Buscar material e ingresar código en ZMM0164
        
        Returns:
            ExportedFile: Información del archivo generado
        """
        if not self.session:
            raise SAPConnectionError("NOT_CONNECTED", "Sesión no establecida")
        
        try:
            logger.info(f"Buscando material: {material_code}")
            
            # Encontrar campo de material (varía por transacción)
            material_field = self.session.FindById("wnd[0]/usr/ctxtMATNR")
            material_field.text = material_code
            
            # Presionar Enter para buscar
            self.session.FindById("wnd[0]").sendVKey(0)
            time.sleep(3)
            
            # Validar que datos se cargaron
            try:
                material_label = self.session.FindById("wnd[0]/usr/ctxtMAKTX").text
                if not material_label:
                    raise MaterialNotFoundError(
                        "MATERIAL_NOT_FOUND",
                        f"Material {material_code} no encontrado o sin datos"
                    )
            except:
                raise MaterialNotFoundError(
                    "MATERIAL_NOT_FOUND",
                    f"Material {material_code} no encontrado"
                )
            
            # Exportar (ej: Ctrl+Shift+X o menú)
            # Esto depende de la transacción específica
            self._export_to_file(output_path)
            
            # Validar que archivo fue creado
            if not os.path.exists(output_path):
                raise FileSystemError(
                    "FILE_NOT_CREATED",
                    f"Archivo no se creó en: {output_path}"
                )
            
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                raise FileSystemError(
                    "FILE_EMPTY",
                    f"Archivo creado pero vacío: {output_path}"
                )
            
            logger.info(f"✅ Material {material_code} exportado ({file_size} bytes)")
            
            return ExportedFile(
                filename=os.path.basename(output_path),
                full_path=output_path,
                file_size_bytes=file_size,
                material_code=material_code,
                exported_at=datetime.now().isoformat(),
                sap_user=self._get_current_user()
            )
            
        except ExportError:
            raise
        except Exception as e:
            raise FileSystemError("EXPORT_ERROR", f"Error exportando material: {str(e)}")
    
    def _export_to_file(self, output_path: str):
        """Lógica específica de exportación (varía por transacción)"""
        # Implementación específica: presionar botón export, dialogs, etc.
        # Este es un placeholder
        logger.debug(f"Exportando a: {output_path}")
        # ... SAP GUI automation para export ...
    
    def _get_current_user(self) -> str:
        """Obtener usuario actual de la sesión"""
        try:
            return self.session.FindById("wnd[0]/sbar/pft[0]/el1").text.split()[0]
        except:
            return "UNKNOWN"
    
    def is_connected(self) -> bool:
        return self._is_connected and self.session is not None
    
    def disconnect(self) -> bool:
        """
        Desconectar limpiamente de SAP
        
        ⚠️ CRÍTICO: Debe ejecutarse en finally{} para evitar bloqueos de puerto
        """
        try:
            if not self.session:
                logger.warning("No hay sesión SAP abierta")
                return False
            
            logger.info("Desconectando de SAP...")
            
            # Enviar comando /nex (logout)
            cmd_field = self.session.FindById("wnd[0]/tbar[0]/okcd")
            cmd_field.text = "/nex"
            self.session.FindById("wnd[0]").sendVKey(0)
            time.sleep(2)
            
            # Cerrar conexión
            if self.connection:
                self.connection.Close()
            
            self._is_connected = False
            self.session = None
            self.connection = None
            
            # Forzar cierre de proceso (critical!)
            subprocess.run(
                ["taskkill", "/F", "/IM", "saplogon.exe"],
                capture_output=True,
                timeout=5
            )
            
            logger.info("✅ Desconexión completada")
            return True
            
        except Exception as e:
            logger.error(f"⚠️ Error desconectando: {str(e)}")
            # Intentar forzar cierre aún si hubo error
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", "saplogon.exe"],
                    capture_output=True,
                    timeout=5
                )
            except:
                pass
            return False
```

#### 2.2 `src/adapters/file_adapter.py` - Manejo de Archivos
```python
import os
import logging
from pathlib import Path
from datetime import date

from ..domain.export_data import FileSystemError

logger = logging.getLogger(__name__)

class FileAdapter:
    """Adaptador para operaciones con el sistema de archivos"""
    
    @staticmethod
    def ensure_folder_exists(folder_path: str) -> bool:
        """Asegurar que carpeta existe (crearla si no)"""
        try:
            Path(folder_path).mkdir(parents=True, exist_ok=True)
            logger.debug(f"Carpeta garantizada: {folder_path}")
            return True
        except Exception as e:
            raise FileSystemError(
                "FOLDER_CREATE_FAILED",
                f"No se pudo crear/acceder carpeta {folder_path}: {str(e)}"
            )
    
    @staticmethod
    def check_disk_space(folder_path: str, min_bytes: int = 10_485_760) -> bool:
        """Validar que hay espacio en disco (default: 10 MB)"""
        try:
            import shutil
            stat = shutil.disk_usage(folder_path)
            if stat.free < min_bytes:
                raise FileSystemError(
                    "DISK_SPACE_LOW",
                    f"Espacio en disco insuficiente: {stat.free} bytes < {min_bytes}"
                )
            logger.debug(f"Espacio disco OK: {stat.free / 1_048_576:.2f} MB")
            return True
        except FileSystemError:
            raise
        except Exception as e:
            raise FileSystemError(
                "DISK_CHECK_ERROR",
                f"Error verificando espacio: {str(e)}"
            )
    
    @staticmethod
    def generate_filename(material_code: str, file_format: str = "XLS") -> str:
        """Generar nombre de archivo con patrón: zmm0164-[MATERIAL]-[DATE].[EXT]"""
        today = date.today().isoformat()  # YYYY-MM-DD
        extension = file_format.lower() if file_format else "xls"
        filename = f"zmm0164-{material_code}-{today}.{extension}"
        logger.debug(f"Nombre generado: {filename}")
        return filename
    
    @staticmethod
    def validate_file_created(file_path: str, min_size_bytes: int = 1) -> bool:
        """Validar que archivo existe y no está vacío"""
        try:
            if not os.path.exists(file_path):
                raise FileSystemError(
                    "FILE_NOT_EXISTS",
                    f"Archivo no existe: {file_path}"
                )
            
            file_size = os.path.getsize(file_path)
            if file_size < min_size_bytes:
                raise FileSystemError(
                    "FILE_TOO_SMALL",
                    f"Archivo demasiado pequeño ({file_size} bytes)"
                )
            
            logger.info(f"✅ Archivo validado: {file_path} ({file_size} bytes)")
            return True
            
        except FileSystemError:
            raise
        except Exception as e:
            raise FileSystemError(
                "FILE_VALIDATION_ERROR",
                f"Error validando archivo: {str(e)}"
            )
```

#### 2.3 `src/adapters/smb_mount.py` - Montaje de Carpeta Compartida
```python
import subprocess
import logging
import os
from ..domain.export_data import FileSystemError

logger = logging.getLogger(__name__)

class SMBMount:
    """Adaptador para montar carpetas compartidas (SMB/CIFS) en Windows"""
    
    @staticmethod
    def mount_network_drive(
        unc_path: str,
        drive_letter: str = "Z",
        username: str = None,
        password: str = None,
        domain: str = "NATURA",
        persistent: bool = True
    ) -> bool:
        """
        Montar carpeta compartida SMB
        
        Args:
            unc_path: Ruta UNC (ej: \\10.156.145.28\Areas\Publico\RPA)
            drive_letter: Letra de unidad (Z)
            username: Usuario red (ej: cmancill)
            password: Contraseña (⚠️ sensible)
            domain: Dominio (NATURA)
            persistent: Persistir entre reinicios
        
        Returns:
            True si éxito, False si ya montado o error no crítico
        
        Raises:
            FileSystemError: Si falla de forma crítica
        """
        try:
            mount_point = f"{drive_letter}:"
            
            # Chequear si ya está montado
            if os.path.exists(mount_point):
                logger.info(f"Unidad {mount_point} ya montada")
                # Intentar acceso para validar
                try:
                    os.listdir(mount_point)
                    return True
                except PermissionError:
                    logger.warning(f"Unidad {mount_point} montada pero sin acceso")
                    return False
            
            # Construir comando net use
            cmd = [
                "net", "use",
                f"{mount_point}",
                unc_path,
            ]
            
            if username:
                # Formato: /user:DOMINIO\usuario
                user_spec = f"{domain}\\{username}" if domain else username
                cmd.extend(["/user:" + user_spec])
            
            if password:
                cmd.append(password)
            
            if persistent:
                cmd.append("/persistent:yes")
            
            logger.info(f"Montando {unc_path} en {mount_point}...")
            
            # Ejecutar comando (sin output de contraseña en logs)
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                # Chequear si es "ya montado"
                if "already" in error_msg.lower() or "1219" in error_msg:
                    logger.warning(f"Unidad ya montada: {error_msg}")
                    return True  # No es error crítico
                
                raise FileSystemError(
                    "MOUNT_FAILED",
                    f"Error montando {mount_point}: {error_msg}"
                )
            
            logger.info(f"✅ Montaje exitoso: {mount_point}")
            return True
            
        except FileSystemError:
            raise
        except subprocess.TimeoutExpired:
            raise FileSystemError(
                "MOUNT_TIMEOUT",
                f"Timeout montando {unc_path}"
            )
        except Exception as e:
            raise FileSystemError(
                "MOUNT_ERROR",
                f"Error inesperado montando: {str(e)}"
            )
    
    @staticmethod
    def get_unc_path_fallback(unc_path: str, drive_letter: str = "Z") -> str:
        """
        Retornar ruta alternativa si montaje falla
        
        Prioridad:
        1. Z:\... (si está montado)
        2. UNC path directo (\\server\share)
        """
        mount_point = f"{drive_letter}:\\"
        
        if os.path.exists(mount_point):
            logger.info(f"Usando ruta montada: {mount_point}")
            return mount_point
        
        logger.warning(f"Unidad {drive_letter} no disponible, usando UNC directo")
        return unc_path
```

---

### 3. **USE_CASES** - Lógica de Orquestación

#### 3.1 `src/use_cases/export_zmm0164.py`
```python
import logging
import time
from typing import Optional
from datetime import datetime

from ..domain.export_data import (
    ExportConfig, SAPCredentials, ExportedFile,
    ExportError, SAPConnectionError, ExportTimeoutError,
    FileSystemError
)
from ..domain.sap_port import SAPPort
from ..adapters.file_adapter import FileAdapter
from ..adapters.smb_mount import SMBMount

logger = logging.getLogger(__name__)

class ExportZMM0164UseCase:
    """
    Caso de uso: Exportar datos de material desde ZMM0164
    
    Responsabilidades:
    - Orquestar flujo SAP + File system
    - Manejar reintentos automáticos
    - Loguear cada paso
    - Asegurar cleanup en caso de error
    """
    
    def __init__(
        self,
        sap_driver: SAPPort,
        file_adapter: FileAdapter = None,
        smb_mount: SMBMount = None
    ):
        self.sap_driver = sap_driver
        self.file_adapter = file_adapter or FileAdapter()
        self.smb_mount = smb_mount or SMBMount()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def execute(self, config: ExportConfig, credentials: SAPCredentials) -> ExportedFile:
        """
        Ejecutar exportación completa
        
        Flujo:
        1. Validar configuración y permisos (disco, carpeta)
        2. Montar carpeta compartida (SMB)
        3. Conectar a SAP GUI
        4. Autenticarse
        5. Navegar a ZMM0164
        6. Buscar y exportar material
        7. Validar archivo creado
        8. Retornar resultado
        
        Manejo de errores:
        - Reintentos automáticos (max 3) con exponential backoff
        - No reintentar: credenciales inválidas, material no encontrado
        - Siempre ejecutar disconnect() en finally{}
        
        Returns:
            ExportedFile: Información del archivo exportado
        
        Raises:
            ExportError: Si falla tras reintentos
        """
        attempt = 0
        last_error = None
        
        while attempt < config.max_retries:
            try:
                attempt += 1
                self.logger.info(
                    f"Iniciando exportación ZMM0164 "
                    f"(intento {attempt}/{config.max_retries})"
                )
                
                # PASO 1: Validaciones previas
                self._validate_prerequisites(config)
                
                # PASO 2: Montar carpeta compartida (SMB)
                self._mount_output_folder(config)
                
                # Generar ruta de salida
                filename = FileAdapter.generate_filename(
                    config.material_code,
                    config.file_format.value
                )
                output_path = os.path.join(config.output_folder, filename)
                
                # PASO 3-6: Flujo SAP
                result = self._execute_sap_export(
                    credentials,
                    config,
                    output_path
                )
                
                self.logger.info("✅ Exportación completada exitosamente")
                return result
                
            except SAPAuthenticationError as e:
                # NO reintentar: credenciales inválidas
                self.logger.error(f"🔐 Error de autenticación: {e.message}")
                raise
                
            except MaterialNotFoundError as e:
                # NO reintentar: material no existe
                self.logger.error(f"📦 Material no encontrado: {e.message}")
                raise
                
            except (SAPConnectionError, ExportTimeoutError) as e:
                # SÍ reintentar: errores transitorios
                last_error = e
                if attempt < config.max_retries:
                    delay = config.retry_delay_seconds * (2 ** (attempt - 1))  # Exponential backoff
                    self.logger.warning(
                        f"⚠️ {e.message} - Reintentando en {delay}s "
                        f"(intento {attempt + 1}/{config.max_retries})"
                    )
                    time.sleep(delay)
                else:
                    self.logger.critical(f"❌ Falló tras {config.max_retries} intentos")
                    raise
                    
            except ExportError as e:
                # Otros errores: no reintentar
                self.logger.error(f"❌ Error crítico: {e.message}")
                raise
                
            finally:
                # SIEMPRE desconectar
                try:
                    if self.sap_driver.is_connected():
                        self.sap_driver.disconnect()
                except Exception as e:
                    self.logger.error(f"⚠️ Error en disconnect: {str(e)}")
    
    def _validate_prerequisites(self, config: ExportConfig):
        """Validar configuración antes de ejecutar"""
        self.logger.debug("Validando prerequisitos...")
        
        # Validar carpeta de salida
        try:
            FileAdapter.ensure_folder_exists(config.output_folder)
            FileAdapter.check_disk_space(config.output_folder)
        except FileSystemError as e:
            self.logger.critical(f"📁 {e.message}")
            raise
        
        self.logger.debug("✅ Validación completada")
    
    def _mount_output_folder(self, config: ExportConfig):
        """Intentar montar carpeta compartida (SMB)"""
        self.logger.debug("Intentando montar carpeta compartida...")
        
        # Este paso depende de si output_folder es UNC o local
        # Placeholder: en config.py se proporciona UNC_PATH, NET_USER, NET_PASSWORD
        # Implementación real:
        # try:
        #     SMBMount.mount_network_drive(...)
        # except FileSystemError:
        #     logger.warning("Montaje SMB falló, intentando UNC directo")
    
    def _execute_sap_export(
        self,
        credentials: SAPCredentials,
        config: ExportConfig,
        output_path: str
    ) -> ExportedFile:
        """Ejecutar flujo SAP (connect → login → navigate → export)"""
        
        # PASO 3: Conectar
        self.sap_driver.connect(
            connection_name=self._get_sap_connection_name(config.sap_environment),
            timeout_seconds=config.connection_timeout_seconds
        )
        
        # PASO 4: Autenticarse
        self.sap_driver.login(
            credentials=credentials,
            timeout_seconds=config.connection_timeout_seconds
        )
        
        # PASO 5: Navegar a transacción
        self.sap_driver.navigate_to_transaction(
            transaction_code="zmm0164",
            timeout_seconds=20
        )
        
        # PASO 6: Buscar y exportar material
        result = self.sap_driver.find_and_export_material(
            material_code=config.material_code,
            output_path=output_path
        )
        
        # PASO 7: Validar archivo
        FileAdapter.validate_file_created(output_path)
        
        return result
    
    @staticmethod
    def _get_sap_connection_name(sap_environment) -> str:
        """Mapear ambiente a nombre de conexión SAP"""
        mapping = {
            "development": "DEV",
            "testing": "TEST",
            "production": "PROD"
        }
        return mapping.get(sap_environment.value, "PROD")
```

---

### 4. **SECURITY** - Manejo Centralizado de Secretos

#### 4.1 `security/vault_helper.py`
```python
import logging
from core_shared.security.vault import Vault

logger = logging.getLogger(__name__)

def get_secret(key: str, default: str = None) -> str:
    """
    Helper centralizado para obtener secretos
    
    ⚠️ CRÍTICO: Usar SIEMPRE en lugar de os.getenv() directo
    
    Prioridad:
    1. Variables de entorno del Sistema Operativo
    2. GitHub Secrets (inyectados via CI/CD)
    3. Valor default (si no es crítico)
    
    Args:
        key: Clave (ej: "BOT_ZMM0164_SAP_PASSWORD")
        default: Valor default si no existe
    
    Returns:
        str: Valor del secreto
    
    Raises:
        ValueError: Si no existe y no hay default
    
    Example:
        >>> password = get_secret("BOT_ZMM0164_SAP_PASSWORD")
        >>> client = get_secret("BOT_ZMM0164_SAP_CLIENT", "210")
    """
    try:
        value = Vault.get_secret(key, default=default)
        if value is None and default is None:
            raise ValueError(f"Secreto requerido no encontrado: {key}")
        
        # Log sanitizado (nunca loguear valor completo)
        if value and "PASSWORD" in key:
            logger.debug(f"✓ Secreto cargado: {key} (****)")
        else:
            logger.debug(f"✓ Secreto cargado: {key} = {value}")
        
        return value
        
    except Exception as e:
        logger.error(f"❌ Error obteniendo secreto {key}: {str(e)}")
        raise
```

---

### 5. **CONFIGURACIÓN** - `config.py`

```python
"""
Configuración multambiente para Bot ZMM0164

Variables de entorno esperadas:
- RPA_ENV: "development" | "testing" | "production"
- BOT_ZMM0164_SAP_CLIENT, BOT_ZMM0164_SAP_USER, etc.
"""

import os
import logging
from enum import Enum
from security.vault_helper import get_secret
from src.domain.export_data import SAPEnvironment

# Ambiente actual
RPA_ENV = os.getenv("RPA_ENV", "production").lower()

# Mapeo de ambientes
ENVIRONMENTS = {
    "development": {
        "sap_client": "100",
        "sap_connection_name": "DEV",
        "log_level": "DEBUG",
        "timeout_seconds": 60,
        "unc_path": r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164_DEV",
        "drive_letter": "Z",
    },
    "testing": {
        "sap_client": "200",
        "sap_connection_name": "TEST",
        "log_level": "INFO",
        "timeout_seconds": 45,
        "unc_path": r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164_TEST",
        "drive_letter": "Z",
    },
    "production": {
        "sap_client": "210",
        "sap_connection_name": "PROD",
        "log_level": "INFO",
        "timeout_seconds": 30,
        "unc_path": r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164",
        "drive_letter": "Z",
    },
}

# Configuración activa
CONFIG = ENVIRONMENTS.get(RPA_ENV, ENVIRONMENTS["production"])

# SAP Credentials (SIEMPRE desde Vault)
SAP_CLIENT = get_secret("BOT_ZMM0164_SAP_CLIENT", CONFIG["sap_client"])
SAP_USER = get_secret("BOT_ZMM0164_SAP_USER")  # Sin default - requerido
SAP_PASSWORD = get_secret("BOT_ZMM0164_SAP_PASSWORD")  # Sin default - requerido
SAP_LANGUAGE = get_secret("BOT_ZMM0164_SAP_LANGUAGE", "ES")

# Network credentials (para SMB mount)
NET_UNC_PATH = CONFIG["unc_path"]
NET_DOMAIN = get_secret("BOT_ZMM0164_OUTPUT_NET_DOMAIN", "NATURA")
NET_USER = get_secret("BOT_ZMM0164_OUTPUT_NET_USER")
NET_PASSWORD = get_secret("BOT_ZMM0164_OUTPUT_NET_PASSWORD")

# Rutas SAP
SAP_LOGON_PATH = r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe"

# Logging
LOG_LEVEL = CONFIG["log_level"]
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(f"logs/zmm0164_{RPA_ENV}.log"),
        logging.StreamHandler()
    ]
)
```

#### 5.2 `main.py` - Punto de Entrada (SOLO ORQUESTACIÓN)

```python
"""
Bot SAP ZMM0164 - Exportación Automatizada de Materiales
Punto de entrada único (NO lógica aquí)
"""

import sys
import logging
from datetime import date
import os

from config import (
    SAP_CLIENT, SAP_USER, SAP_PASSWORD, SAP_LANGUAGE,
    NET_UNC_PATH, NET_DOMAIN, NET_USER, NET_PASSWORD,
    SAP_LOGON_PATH, RPA_ENV
)
from src.domain.export_data import (
    SAPCredentials, ExportConfig, SAPEnvironment, 
    FileFormat, ExportError
)
from src.adapters.sap_driver import SAPDriver
from src.adapters.file_adapter import FileAdapter
from src.adapters.smb_mount import SMBMount
from src.use_cases.export_zmm0164 import ExportZMM0164UseCase

logger = logging.getLogger(__name__)

def main(material_code: str = None) -> int:
    """
    Punto de entrada principal
    
    Args:
        material_code: Código de material a exportar (ej: "4100")
                      Si no se proporciona, se lee de variable de entorno
    
    Returns:
        int: Exit code (0 = éxito, 1 = error)
    """
    
    # Obtener material_code
    if not material_code:
        material_code = os.getenv("BOT_ZMM0164_MATERIAL_CODE")
    
    if not material_code:
        logger.error("📦 No se proporcionó material_code")
        return 1
    
    try:
        # =========================
        # PASO 1: Configurar experimento
        # =========================
        logger.info(f"🚀 Iniciando Bot ZMM0164 (ambiente: {RPA_ENV})")
        logger.info(f"📦 Material a exportar: {material_code}")
        
        # Crear credenciales (NUNCA loguear valores)
        credentials = SAPCredentials(
            client=SAP_CLIENT,
            user=SAP_USER,
            password=SAP_PASSWORD,
            language=SAP_LANGUAGE
        )
        logger.debug(f"Credenciales: {credentials}")  # Sanitizado por __repr__
        
        # Crear configuración de exportación
        output_folder_path = os.path.join(
            NET_UNC_PATH if os.path.exists(NET_UNC_PATH) else "Z:\\",
            "exportados"
        )
        
        config = ExportConfig(
            material_code=material_code,
            output_folder=output_folder_path,
            file_format=FileFormat.XLS,
            sap_environment=SAPEnvironment(f"production" if RPA_ENV == "production" else "testing"),
            max_retries=3,
            retry_delay_seconds=5,
            connection_timeout_seconds=30
        )
        
        # =========================
        # PASO 2: Montar carpeta compartida
        # =========================
        logger.info("📂 Montando carpeta compartida...")
        try:
            SMBMount.mount_network_drive(
                unc_path=NET_UNC_PATH,
                drive_letter="Z",
                username=NET_USER,
                password=NET_PASSWORD,
                domain=NET_DOMAIN,
                persistent=True
            )
        except Exception as e:
            logger.warning(f"⚠️ Montaje SMB falló, usando UNC directo: {str(e)}")
            config.output_folder = NET_UNC_PATH
        
        # =========================
        # PASO 3: Ejecutar caso de uso
        # =========================
        sap_driver = SAPDriver(sap_logon_path=SAP_LOGON_PATH)
        use_case = ExportZMM0164UseCase(
            sap_driver=sap_driver,
            file_adapter=FileAdapter(),
            smb_mount=SMBMount()
        )
        
        result = use_case.execute(config=config, credentials=credentials)
        
        # =========================
        # PASO 4: Reportar éxito
        # =========================
        logger.info("=" * 60)
        logger.info("✅ EXPORTACIÓN COMPLETADA EXITOSAMENTE")
        logger.info("=" * 60)
        logger.info(f"📄 Archivo: {result.filename}")
        logger.info(f"📍 Ruta: {result.full_path}")
        logger.info(f"📊 Tamaño: {result.file_size_bytes} bytes")
        logger.info(f"⏰ Hora: {result.exported_at}")
        logger.info("=" * 60)
        
        return 0
        
    except ExportError as e:
        logger.critical(f"❌ ERROR [{e.code}]: {e.message}")
        return 1
        
    except Exception as e:
        logger.critical(f"❌ ERROR INESPERADO: {str(e)}", exc_info=True)
        return 1
        
    finally:
        logger.info("Limpieza finalizada")

if __name__ == "__main__":
    # Ejecutable: python main.py [material_code]
    material = sys.argv[1] if len(sys.argv) > 1 else None
    exit_code = main(material_code=material)
    sys.exit(exit_code)
```

---

## 🧪 Plan de Testing (TDD)

### Estructura de Tests

```
tests/
├── __init__.py
├── conftest.py                    # Fixtures compartidas (mock SAP, config)
├── unit/
│   ├── test_domain_models.py      # TC-D001 a D011
│   ├── test_sap_driver.py         # TC-A001 a A007 (mocked)
│   ├── test_file_adapter.py       # TC-A008 a A012 (filesystem)
│   └── test_use_case.py           # TC-U001 a U004 (orquestación)
├── integration/
│   └── test_end_to_end.py         # IT-001 (con SAP real, opcional)
└── fixtures/
    ├── mock_sap_objects.py        # MagicMock de pywin32
    └── test_data.py                # datos de prueba
```

### Test Cases (Red → Green → Refactor)

#### **DOMAIN TESTS** (TC-D001 a D011)
| TC | Caso | Entrada | Esperado |
|----|------|---------|----------|
| D001 | SAPCredentials válidas | client="210", user="BOT", lang="ES" | Repr sanitizado (sin password) |
| D002 | ExportConfig validación | material_code="" | ValueError |
| D003 | ExportConfig filename | material="4100", date=2026-03-02 | "zmm0164-4100-2026-03-02.xls" |
| D004 | ExportedFile construcción | filename, path, size | Objeto completo |
| D005 | SAPConnectionError | code="SAP_FAIL", msg="Error..." | Exception con atributos |
| D006 | MaterialNotFoundError extends | formato | Hereda de ExportError |
| D007 | SAPEnvironment enum | "production" | SAPEnvironment.PRODUCCION |
| D008 | FileFormat enum | FileFormat.XLS.value | "XLS" |
| D009 | ExportConfig max_retries | max_retries=5 | 5 (sin límite en domain) |
| D010 | SAPEnvironment validación | "invalid" | ValueError |
| D011 | ExportConfig connection_timeout | timeout=10 | 10 (sin validación min/max) |

#### **ADAPTER TESTS** (TC-A001 a A012) - **MOCKED**

```python
# tests/unit/test_sap_driver.py

import unittest
from unittest.mock import Mock, MagicMock, patch
from src.adapters.sap_driver import SAPDriver
from src.domain.export_data import (
    SAPCredentials, SAPConnectionError, SAPAuthenticationError
)

class TestSAPDriver(unittest.TestCase):
    
    def setUp(self):
        """Preparar mocks antes de cada test"""
        self.mock_sap_gui = MagicMock()
        self.driver = SAPDriver(saplogon_path=r"C:\SAP\saplogon.exe")
    
    # TC-A001: connect() exitoso
    @patch('src.adapters.sap_driver.GetObject')
    def test_connect_success(self, mock_get_object):
        """Conexión exitosa a SAP"""
        # Arrange
        mock_gui = MagicMock()
        mock_get_object.return_value = mock_gui
        mock_desktop = MagicMock()
        mock_gui.GetScriptingEngine.Desktop = mock_desktop
        mock_connection = MagicMock()
        mock_desktop.OpenConnection.return_value = mock_connection
        mock_session = MagicMock()
        mock_connection.Children.return_value = [mock_session]
        
        # Act
        result = self.driver.connect("TEST")
        
        # Assert
        assert result is self.driver  # Chaining
        assert self.driver.is_connected() is True
        assert self.driver.session == mock_session
    
    # TC-A002: connect() timeout
    @patch('src.adapters.sap_driver.GetObject')
    @patch('src.adapters.sap_driver.time.sleep')
    def test_connect_timeout(self, mock_sleep, mock_get_object):
        """Timeout si conexión demora >30s"""
        mock_get_object.side_effect = [...large delay...]
        
        with pytest.raises(ExportTimeoutError) as exc:
            self.driver.connect("TEST", timeout_seconds=1)
        
        assert exc.value.code == "SAP_CONNECT_TIMEOUT"
    
    # TC-A003: login() exitoso
    def test_login_success(self):
        """Login con credenciales válidas"""
        # Arrange
        self.driver._is_connected = True
        self.driver.session = MagicMock()
        credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="pass123",
            language="ES"
        )
        
        mock_user_field = MagicMock()
        mock_pwd_field = MagicMock()
        self.driver.session.FindById.side_effect = [
            mock_user_field,
            mock_pwd_field,
            MagicMock(),  # client field
            MagicMock(),  # language field
        ]
        
        # Act
        result = self.driver.login(credentials)
        
        # Assert
        assert result is self.driver
        mock_user_field.text = "BOTSCL"
        mock_pwd_field.text = "pass123"
    
    # TC-A004: login() credenciales inválidas
    def test_login_invalid_credentials(self):
        """Login falla con contraseña incorrecta"""
        self.driver._is_connected = True
        self.driver.session = MagicMock()
        
        # Mock de modal de error SAP
        self.driver.session.FindById.return_value.text = "Usuario/contraseña inválidos"
        
        credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="wrongpass"
        )
        
        with pytest.raises(SAPAuthenticationError) as exc:
            self.driver.login(credentials)
        
        assert exc.value.code == "SAP_AUTH_FAILED"
    
    # ... más tests para navigate_to_transaction, find_and_export_material, disconnect ...

# TC-A005: navigate_to_transaction()
# TC-A006: find_and_export_material() éxito
# TC-A007: find_and_export_material() material not found
# TC-A008: FileAdapter.ensure_folder_exists()
# TC-A009: FileAdapter.check_disk_space() insuficiente
# TC-A010: FileAdapter.generate_filename()
# TC-A011: SMBMount.mount_network_drive() éxito
# TC-A012: SMBMount.mount_network_drive() ya montado
```

#### **USE_CASE TESTS** (TC-U001 a U004)

```python
# tests/unit/test_use_case.py

import unittest
from unittest.mock import Mock, MagicMock, patch
import pytest
from src.use_cases.export_zmm0164 import ExportZMM0164UseCase
from src.domain.export_data import (
    ExportConfig, SAPCredentials, SAPEnvironment, 
    FileFormat, MaterialNotFoundError, ExportedFile
)

class TestExportZMM0164UseCase(unittest.TestCase):
    
    def setUp(self):
        """Preparar mocks"""
        self.mock_driver = MagicMock()
        self.mock_file_adapter = MagicMock()
        self.mock_smb = MagicMock()
        
        self.use_case = ExportZMM0164UseCase(
            sap_driver=self.mock_driver,
            file_adapter=self.mock_file_adapter,
            smb_mount=self.mock_smb
        )
    
    # TC-U001: execute() flujo completo exitoso
    def test_execute_success_full_flow(self):
        """Ejecutar ZMM0164 exitosamente end-to-end"""
        # Arrange
        config = ExportConfig(
            material_code="4100",
            output_folder="Z:\\",
            file_format=FileFormat.XLS
        )
        credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="pass"
        )
        
        # Mock de todas las operaciones
        self.mock_driver.is_connected.return_value = False
        self.mock_file_adapter.ensure_folder_exists.return_value = True
        self.mock_file_adapter.check_disk_space.return_value = True
        self.mock_driver.connect.return_value = self.mock_driver
        self.mock_driver.login.return_value = self.mock_driver
        self.mock_driver.navigate_to_transaction.return_value = self.mock_driver
        
        mock_exported = ExportedFile(
            filename="zmm0164-4100-2026-03-02.xls",
            full_path="Z:\\zmm0164-4100-2026-03-02.xls",
            file_size_bytes=15000,
            material_code="4100",
            exported_at="2026-03-02T10:00:00",
            sap_user="BOTSCL"
        )
        self.mock_driver.find_and_export_material.return_value = mock_exported
        self.mock_file_adapter.validate_file_created.return_value = True
        
        # Act
        result = self.use_case.execute(config, credentials)
        
        # Assert
        assert result.filename == "zmm0164-4100-2026-03-02.xls"
        assert result.file_size_bytes == 15000
        self.mock_driver.connect.assert_called_once()
        self.mock_driver.login.assert_called_once()
        self.mock_driver.disconnect.assert_called_once()  # Cleanup
    
    # TC-U002: execute() reintento automático (error transitorio)
    def test_execute_retry_on_connection_error(self):
        """Reintenta automáticamente en caso de ConnectionError"""
        config = ExportConfig(
            material_code="4100",
            output_folder="Z:\\",
            max_retries=3,
            retry_delay_seconds=0  # Sin espera en tests
        )
        credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="pass"
        )
        
        # Primera llamada falla, segunda éxito
        mock_exported = ExportedFile(...)
        self.mock_driver.connect.side_effect = [
            SAPConnectionError("SAP_FAIL", "Network timeout"),  # Intento 1
            self.mock_driver  # Intento 2: éxito
        ]
        self.mock_driver.login.return_value = self.mock_driver
        # ... rest of mocks ...
        
        result = self.use_case.execute(config, credentials)
        
        # Assert: llamadas múltiples
        assert self.mock_driver.connect.call_count == 2
        assert result is not None
    
    # TC-U003: execute() NO reintenta en auth error
    def test_execute_no_retry_on_auth_error(self):
        """No reintenta si falla autenticación"""
        config = ExportConfig(
            material_code="4100",
            output_folder="Z:\\",
            max_retries=3
        )
        credentials = SAPCredentials(
            client="210",
            user="BOTSCL",
            password="wrongpass"
        )
        
        self.mock_driver.connect.return_value = self.mock_driver
        self.mock_driver.login.side_effect = SAPAuthenticationError(
            "AUTH_FAILED",
            "Contraseña inválida"
        )
        
        with pytest.raises(SAPAuthenticationError):
            self.use_case.execute(config, credentials)
        
        # Assert: solo 1 intento (no reintentó)
        assert self.mock_driver.login.call_count == 1
        self.mock_driver.disconnect.assert_called_once()  # Cleanup igual
    
    # TC-U004: execute() disconnect siempre (finally)
    def test_execute_cleanup_on_exception(self):
        """Llama a disconnect() incluso si hay excepción"""
        config = ExportConfig(
            material_code="4100",
            output_folder="Z:\\"
        )
        
        self.mock_driver.connect.side_effect = RuntimeError("Inesperado")
        
        with pytest.raises(RuntimeError):
            self.use_case.execute(config, ...)
        
        # Assert: disconnect llamado a pesar de error
        self.mock_driver.disconnect.assert_called_once()
```

#### **INTEGRATION TEST** (IT-001)
```python
# tests/integration/test_end_to_end.py
# (Solo ejecutar en TEST environment con SAP real)

@pytest.mark.skipif(
    os.getenv("RPA_ENV") != "testing",
    reason="Requiere SAP TEST"
)
class TestEndToEndZMM0164:
    
    def test_full_export_workflow_sap_real(self):
        """
        E2E con SAP real (TEST environment)
        
        Precondiciones:
        - Material 4100 existe en SAP TEST
        - Carpeta Z:\Publico\RPA\Plan Chile\zmm0164_TEST existe
        
        Verificaciones:
        - Archivo generado
        - Contenido válido (encabezados SAP)
        - Log completo
        """
        # No usar mocks; usar instancias reales
        sap_driver = SAPDriver(r"C:\...\saplogon.exe")
        use_case = ExportZMM0164UseCase(sap_driver)
        
        config = ExportConfig(
            material_code="4100",
            output_folder=r"Z:\Publico\RPA\Plan Chile\zmm0164_TEST"
        )
        credentials = SAPCredentials(
            client="200",
            user=os.getenv("BOT_ZMM0164_SAP_USER"),
            password=os.getenv("BOT_ZMM0164_SAP_PASSWORD")
        )
        
        # Act
        result = use_case.execute(config, credentials)
        
        # Assert
        assert os.path.exists(result.full_path)
        assert result.file_size_bytes > 100  # No vacío
        assert "4100" in result.filename
```

---

## 📊 Criteria de Aceptación

| Criterio | Especificación | Validación |
|----------|----------------|-----------|
| **CA-001: Arquitectura Limpia** | ✅ Domain puro (sin imports externos) | Code review + linter |
| **CA-002: Secretos Centralizados** | ✅ CERO os.getenv() disperso, 100% Vault | grep -r "os.getenv" (debe fallar) |
| **CA-003: Cobertura Tests** | ✅ Mínimo 80% (unit + integration) | pytest --cov |
| **CA-004: Documentación** | ✅ Docstrings + README + SDD | Doc check |
| **CA-005: Formato Respuestas** | ✅ { "success": bool, "data"/"error" } | Integration tests |
| **CA-006: Manejo de Errores** | ✅ Reintentos (3x) + cleanup garantizado | Logs validados |
| **CA-007: Performance** | ✅ <2 minutos end-to-end | Timing en logs |
| **CA-008: Type Hints** | ✅ 100% de funciones tipadas | mypy check |

---

## 🚀 Plan de Implementación TDD (Red → Green → Refactor)

### **Iteración 1: Domain Models (Sprint 1)**
- [ ] Escribir TC-D001 a D011 (todos fallan)
- [ ] Implementar dataclasses en domain/
- [ ] TCs pasan
- [ ] Refactorización minimalista

### **Iteración 2: Adapters - SAP Driver (Sprint 2)**
- [ ] Escribir TC-A001 a A007 (con mocks)
- [ ] Implementar SAPDriver
- [ ] TCs pasan
- [ ] Refactor

### **Iteración 3: Adapters - File & SMB (Sprint 2)**
- [ ] Escribir TC-A008 a A012
- [ ] Implementar FileAdapter + SMBMount
- [ ] TCs pasan

### **Iteración 4: Use Case (Sprint 3)**
- [ ] Escribir TC-U001 a U004
- [ ] Implementar ExportZMM0164UseCase
- [ ] Orquestar adapters
- [ ] TCs pasan

### **Iteración 5: Integration & E2E (Sprint 4)**
- [ ] IT-001 (manual en TEST environment)
- [ ] main.py integrado
- [ ] Validación en producción
- [ ] UAT

---

## 🔗 Referencias Cruzadas

| Documento | Sección | Relevancia |
|-----------|---------|-----------|
| REQUISITO_NUEVO.md | RF-001 a RF-004 | Requisitos funcionales |
| regla_capas.md | Arquitectura Limpia | Reglas de design |
| copilot-instructions.md | Naming + Testing | Estándares del monorepo |
| config.py | Environments | Multambiente (DEV/TEST/PROD) |

---

## 📝 Changelog

| Versión | Fecha | Cambios |
|---------|-------|---------|
| 1.0 | 2026-03-02 | SDD inicial - Arquitectura DDD, TDD, 25+ test cases |

---

**Próximo paso:** Iniciar **Iteración 1 (Domain Models)** creando los archivos de test siguiendo patrón TDD (Red → Green → Refactor).