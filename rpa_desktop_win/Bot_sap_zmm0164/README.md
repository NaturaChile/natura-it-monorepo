# 🤖 Bot SAP ZMM0164 - Exportación de Datos

Bot de RPA para automatizar la exportación de datos de la transacción **ZMM0164** en SAP.

## 📁 Estructura del Proyecto

```
Bot_sap_zmm0164/
├── main.py                          # Punto de entrada (detonador)
├── requirements.txt                 # Dependencias
├── Bot_sap_zmm0164.py              # Script original (para referencia)
└── src/
    ├── domain/                      # Modelo de datos (dominio de negocio)
    │   ├── __init__.py
    │   └── export_data.py           # Dataclasses: ExportConfig, SAPCredentials, SAPConnection
    │
    ├── adapters/                    # Adaptadores técnicos
    │   ├── __init__.py
    │   └── sap_driver.py            # Driver de SAP GUI (pywin32)
    │
    └── use_cases/                   # Lógica de negocio
        ├── __init__.py
        └── release_process.py       # Orquestación del proceso de exportación
```

## 🏗️ Arquitectura

Esta estructura sigue el patrón **Domain-Driven Design (DDD)** adaptado para RPA:

### 1. **domain/** - El Modelo de Datos
- Define **QUÉ** es una exportación, credencial, conexión, etc.
- Dataclasses puras sin lógica técnica.
- Protege la integridad de datos.
- **Archivo**: `export_data.py`
  - `ExportConfig`: Configuración de exportación (material, ruta, formato)
  - `SAPCredentials`: Credenciales de acceso
  - `SAPConnection`: Parámetros de conexión SAP

### 2. **adapters/** - Las Herramientas Técnicas
- Encapsula **CÓMO** se comunica con SAP.
- Solo aquí se usan `pywin32` y detalles de GUI.
- Si SAP cambia, solo modificas este módulo.
- **Archivo**: `sap_driver.py`
  - Conexión robusta a SAP
  - Login
  - Navegación (comandos, campos)
  - Acciones (presionar botones, escribir texto)
  - Exportación y guardado

### 3. **use_cases/** - La Lógica de Negocio
- Orquesta el flujo del proceso.
- Coordina: Conexión → Login → Transacción → Exportación → Guardado.
- Se lee casi como un documento de procedimiento.
- **Archivo**: `release_process.py`
  - `ExportZMM0164UseCase`: Caso de uso principal

### 4. **main.py** - El Detonador
- Punto de entrada único.
- Lee configuración, inicia el caso de uso.
- No contiene lógica de negocio.

## 🚀 Uso

### Instalación

```bash
# Navegar a la carpeta del proyecto
cd Bot_sap_zmm0164

# Instalar dependencias
pip install -r requirements.txt
```

### Ejecución

```bash
# Ejecutar desde la raíz del proyecto
python main.py
```

### En GitHub Actions (desde el servidor RPA)

```yaml
- name: Correr Robot ZMM0164
  run: |
    cd rpa_desktop_win/Bot_sap_zmm0164
    pip install -r requirements.txt
    python main.py
```

## ⚙️ Configuración

Edita los parámetros en [main.py](main.py):

```python
# Conexión a SAP
SAP_CONNECTION = SAPConnection(
    sap_logon_path=r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
    connection_name="1.02 - PRD - Produção/Producción",
    transaction="zmm0164",
)

# Credenciales
CREDENTIALS = SAPCredentials(
    client="210",
    user="BOTSCL",
    password="La.Nueva.Clave.2026",  # ⚠️ Usa variables de entorno en producción
    language="ES",
)

# Exportación
EXPORT_CONFIG = ExportConfig(
    material_code="4100",
    output_folder=r"Z:\Publico\RPA\Plan Chile\zmm0164",
    file_format="XLS",
)
```

## 🔍 Flujo del Proceso

```
1. CONECTAR A SAP
   └─ Lanza saplogon.exe si no está disponible
   
2. LOGIN
   └─ Ingresa credenciales (cliente, usuario, contraseña, idioma)
   
3. NAVEGAR A ZMM0164
   └─ Transacción SAP para búsqueda de materiales
   
4. BUSCAR MATERIAL
   └─ Ingresa código de material (ej: 4100)
   └─ Ejecuta F8 (buscar)
   
5. EXPORTAR DATOS
   └─ Presiona botones de exportación
   └─ Selecciona formato XLS
   
6. GUARDAR ARCHIVO
   └─ Configura ruta de destino
   └─ Configura nombre de archivo con fecha
   └─ Confirma sobrescritura si es necesario
   
7. DESCONECTAR
   └─ Ejecuta /nex (logout)
   └─ Cierra saplogon.exe
```

## 📋 Beneficios de Esta Estructura

✅ **Separación de responsabilidades**: Cada módulo tiene una función clara.
✅ **Mantenibilidad**: Cambios en SAP solo afectan al driver.
✅ **Testabilidad**: Cada componente puede probarse independientemente.
✅ **Reutilizable**: Otros bots pueden importar el driver o el caso de uso.
✅ **Escalable**: Fácil agregar más transacciones o procesos.

## 🛠️ Desarrollo Futuro

Para agregar nuevas transacciones:

```python
# Crear nuevo caso de uso en src/use_cases/
class NewTransactionUseCase:
    def __init__(self, sap_connection, credentials, config):
        self.driver = SAPDriver(...)
    
    def execute(self):
        self.driver.connect()
        self.driver.login(...)
        # Tu lógica aquí
        self.driver.disconnect()
```

## 📌 Notas Importantes

- ⚠️ **Contraseñas**: En producción, usa variables de entorno (GitHub Secrets).
- 🔐 **Seguridad**: No guardes credenciales en código fuente.
- 🖥️ **Windows Only**: Requiere `pywin32` y SAP GUI local.
- 📅 **Fechas**: Los archivos se nombran con la fecha actual automáticamente.

## 📞 Soporte

Si el bot falla:
1. Verifica que SAP esté accesible
2. Confirma que las credenciales sean correctas
3. Revisa la ruta de salida (Z:\Publico\...)
4. Consulta los logs de consola para más detalles
