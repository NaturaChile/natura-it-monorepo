# 🧩 Cómo Reutilizar Este Código

## Escenario: Crear un nuevo bot para la transacción ZMM0165

### Paso 1: Crear la carpeta del nuevo bot

```
Bot_sap_zmm0164/  ← Existe (driver compartido)
Bot_sap_zmm0165/  ← Nuevo bot
  ├── main.py
  ├── requirements.txt (puede ser idéntico)
  └── src/
      └── use_cases/
          └── zmm0165_process.py
```

### Paso 2: Reutilizar el adapter (SAPDriver)

No necesitas copiar `sap_driver.py`. Puedes hacer referencia o compartir en un paquete común:

**Opción A: Referencia relativa (para desarrollo)**

```python
# Bot_sap_zmm0165/src/use_cases/zmm0165_process.py

import sys
sys.path.insert(0, r"..\..\Bot_sap_zmm0164")

from src.adapters.sap_driver import SAPDriver
from Bot_sap_zmm0164.src.domain.export_data import SAPConnection, SAPCredentials
```

**Opción B: Paquete compartido (recomendado para producción)**

```
rpa_desktop_win/
├── shared/
│   ├── adapters/
│   │   └── sap_driver.py
│   └── domain/
│       └── export_data.py
├── Bot_sap_zmm0164/
│   └── ...
└── Bot_sap_zmm0165/
    └── ...
```

### Paso 3: Extender con nueva lógica

```python
# Bot_sap_zmm0165/src/use_cases/zmm0165_process.py

from src.adapters.sap_driver import SAPDriver
from src.domain.export_data import (
    SAPConnection,
    SAPCredentials,
)

class ExportZMM0165UseCase:
    """Nuevo caso de uso reutilizando SAPDriver."""
    
    def __init__(self, sap_connection: SAPConnection, credentials: SAPCredentials):
        self.driver = SAPDriver(
            sap_logon_path=sap_connection.sap_logon_path,
            connection_name=sap_connection.connection_name,
        )
        self.credentials = credentials
    
    def execute(self):
        try:
            # Usar el mismo driver
            self.driver.connect()
            self.driver.login(
                client=self.credentials.client,
                user=self.credentials.user,
                password=self.credentials.password,
            )
            
            # Nueva lógica específica
            self.driver.send_command("/nzmm0165")
            
            # ... tu lógica aquí
            
        finally:
            self.driver.disconnect()
```

---

## 🏗️ Estructura Recomendada para Múltiples Bots

```
rpa_desktop_win/                 ← Carpeta raíz (GitHub repo)
│
├── shared/                       ← Código compartido
│   ├── __init__.py
│   ├── adapters/
│   │   ├── __init__.py
│   │   ├── sap_driver.py        ← Reutilizable por todos
│   │   └── sap_navigator.py     ← Utilitarios SAP
│   │
│   └── domain/
│       ├── __init__.py
│       ├── export_data.py       ← Modelos comunes
│       └── credentials.py       ← Manejo de credenciales
│
├── Bot_sap_zmm0164/             ← Bot específico #1
│   ├── main.py
│   ├── requirements.txt
│   └── src/
│       └── use_cases/
│           └── release_process.py
│
├── Bot_sap_zmm0165/             ← Bot específico #2
│   ├── main.py
│   ├── requirements.txt
│   └── src/
│       └── use_cases/
│           └── approval_process.py
│
└── .github/
    └── workflows/
        └── rpa.yml              ← CI/CD para todos
```

### workflow/rpa.yml (un solo workflow para todos):

```yaml
name: Ejecutar Bots RPA

on:
  workflow_dispatch:
    inputs:
      bot:
        description: 'Bot a ejecutar'
        required: true
        default: 'Bot_sap_zmm0164'
        type: choice
        options:
          - Bot_sap_zmm0164
          - Bot_sap_zmm0165
          - Bot_sap_other

jobs:
  run:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Instalar dependencias
        run: |
          cd ${{ github.event.inputs.bot }}
          pip install -r requirements.txt
      
      - name: Ejecutar bot
        run: |
          cd ${{ github.event.inputs.bot }}
          python main.py
```

---

## 🔌 Crear un Adaptador Nuevo

Si necesitas conectar a una nueva herramienta (ej: Excel, bases de datos):

```python
# shared/adapters/excel_adapter.py

import openpyxl

class ExcelAdapter:
    """Adaptador para manejo de Excel."""
    
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.workbook = None
    
    def open(self):
        self.workbook = openpyxl.load_workbook(self.filepath)
    
    def save(self):
        self.workbook.save(self.filepath)
    
    def write_cell(self, sheet: str, row: int, col: int, value: str):
        ws = self.workbook[sheet]
        ws.cell(row, col).value = value

# Usar en un nuevo caso de uso:
class DataValidationUseCase:
    def __init__(self):
        self.sap_driver = SAPDriver(...)
        self.excel_adapter = ExcelAdapter(...)
    
    def execute(self):
        # Traer datos de SAP
        data = self.sap_driver.get_table_data()
        
        # Guardar en Excel
        self.excel_adapter.write_cell("Sheet1", 1, 1, data)
        self.excel_adapter.save()
```

---

## 📋 Checklist para Nuevo Bot

Cuando crees un nuevo bot basado en esta estructura:

- [ ] Copia la carpeta `Bot_sap_zmm0164` como template
- [ ] Renombra a `Bot_sap_zmm0165` (o el código transacción)
- [ ] Edita `main.py`: Ajusta parámetros de conexión y transacción
- [ ] Edita `src/use_cases/release_process.py`: Cambia lógica específica
- [ ] Mantén `sap_driver.py` IGUAL (o reutiliza desde `shared/`)
- [ ] Actualiza `requirements.txt` si necesitas nuevas dependencias
- [ ] Prueba localmente antes de comitear
- [ ] Crea un nuevo job en GitHub Actions

---

## 🧪 Ejemplo: Crear un caso de uso genérico

Puedes crear adapters que se usen en múltiples bots:

```python
# shared/use_cases/generic_export.py

from shared.adapters.sap_driver import SAPDriver
from shared.domain.export_data import SAPConnection, SAPCredentials

class GenericExportUseCase:
    """Caso de uso genérico para cualquier exportación SAP."""
    
    def __init__(
        self,
        sap_connection: SAPConnection,
        credentials: SAPCredentials,
        transaction: str,
        material_code: str,
        output_path: str,
    ):
        self.driver = SAPDriver(
            sap_connection.sap_logon_path,
            sap_connection.connection_name,
        )
        self.credentials = credentials
        self.transaction = transaction
        self.material_code = material_code
        self.output_path = output_path
    
    def execute(self):
        try:
            self.driver.connect()
            self.driver.login(
                self.credentials.client,
                self.credentials.user,
                self.credentials.password,
            )
            
            # Genérico
            self.driver.send_command(f"/n{self.transaction}")
            self.driver.set_field_text("wnd[0]/usr/ctxtSP$00006-LOW", self.material_code)
            self.driver.press_function_key(8)
            
            # Exportar
            self.driver.press_button("wnd[0]/tbar[1]/btn[30]")
            self.driver.press_button("wnd[0]/tbar[1]/btn[45]")
            
            # Guardar
            self.driver.set_field_text("wnd[1]/usr/ctxtDY_PATH", self.output_path)
            self.driver.press_button("wnd[1]/tbar[0]/btn[0]")
            
        finally:
            self.driver.disconnect()

# Reutilizar en múltiples bots:
# Bot_sap_zmm0164/main.py
use_case = GenericExportUseCase(
    sap_connection=SAP_CONNECTION,
    credentials=CREDENTIALS,
    transaction="zmm0164",
    material_code="4100",
    output_path=r"Z:\Publico\zmm0164",
)

# Bot_sap_zmm0165/main.py
use_case = GenericExportUseCase(
    sap_connection=SAP_CONNECTION,
    credentials=CREDENTIALS,
    transaction="zmm0165",  ← Solo cambias esto
    material_code="5200",   ← Y esto
    output_path=r"Z:\Publico\zmm0165",
)
```

---

## 💡 Mejores Prácticas

1. **DRY (Don't Repeat Yourself)**
   - Driver compartido en `shared/adapters/`
   - Modelos compartidos en `shared/domain/`

2. **Dependencias Explícitas**
   - Inyecta configuración en constructores
   - Evita variables globales

3. **Error Handling**
   - Try/finally para garantizar `disconnect()`
   - Logs claros en cada paso

4. **Testing**
   - Mock del driver para tests unitarios
   - Fixtures para datos de prueba

5. **Versionado**
   - Incrementa versión cuando cambies adapter
   - Documenta cambios breaking

---

Así tu código crece de forma limpia y reutilizable. 🚀
