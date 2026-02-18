# 🏛️ Arquitectura del Proyecto

## Diagrama de Capas

```
┌─────────────────────────────────────────────────────────────┐
│                         MAIN.PYd                             │
│              (Punto de Entrada / Detonador)                 │
└──────────────────────────┬──────────────────────────────────┘
                           │ Crea instancia
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                 USE_CASES LAYER                             │
│          (Lógica de Negocio / Orquestación)                 │
│  ExportZMM0164UseCase.execute()                             │
│  ├─ Conecta                                                 │
│  ├─ Realiza login                                           │
│  ├─ Navega a transacción                                    │
│  ├─ Busca datos                                             │
│  ├─ Exporta                                                 │
│  └─ Guarda archivo                                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ Orquesta
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              ADAPTERS LAYER (Interfaces)                    │
│            (Detalles Técnicos / Implementación)             │
│                                                              │
│  SAPDriver (Adaptador para SAP GUI)                         │
│  ├─ connect()                                               │
│  ├─ login(client, user, password, language)                │
│  ├─ send_command(cmd)                                       │
│  ├─ set_field_text(field_id, text)                         │
│  ├─ press_button(button_id)                                │
│  ├─ press_function_key(key_code)                           │
│  └─ disconnect()                                            │
│                                                              │
│  [pywin32 / win32com]                                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ Usa
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              DOMAIN LAYER                                   │
│         (Modelos de Datos / Estructuras)                    │
│                                                              │
│  ExportConfig                                               │
│  ├─ material_code: str                                      │
│  ├─ output_folder: str                                      │
│  └─ file_format: str                                        │
│                                                              │
│  SAPCredentials                                             │
│  ├─ client: str                                             │
│  ├─ user: str                                               │
│  ├─ password: str                                           │
│  └─ language: str                                           │
│                                                              │
│  SAPConnection                                              │
│  ├─ sap_logon_path: str                                     │
│  ├─ connection_name: str                                    │
│  └─ transaction: str                                        │
└─────────────────────────────────────────────────────────────┘
```

## Flujo de Datos

```
┌─────────────────────────────────────────────────────────────┐
│ 1. CONFIGURACIÓN (main.py)                                  │
│    SAP_CONNECTION = {...}                                   │
│    CREDENTIALS = {...}                                      │
│    EXPORT_CONFIG = {...}                                    │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. CREAR INSTANCIA DEL CASO DE USO                          │
│    use_case = ExportZMM0164UseCase(                         │
│        sap_connection=SAP_CONNECTION,                       │
│        credentials=CREDENTIALS,                             │
│        export_config=EXPORT_CONFIG,                         │
│    )                                                         │
└──────────────────────────┬──────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. EJECUTAR CASO DE USO                                     │
│    use_case.execute()                                       │
└──────────────────────────┬──────────────────────────────────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
        ▼                  ▼                  ▼
   ┌─────────┐        ┌─────────┐      ┌─────────┐
   │ Connect │        │  Login  │      │  Naveg. │
   │ Driver  │        │ (Creds) │      │ (Trans) │
   └────┬────┘        └────┬────┘      └────┬────┘
        │                  │                │
        └──────────────────┼────────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
                ┌────────┐    ┌──────────┐
                │ Search │    │ Export & │
                │ Material│   │  Save    │
                └────┬───┘    └────┬─────┘
                     │            │
                     └─────┬──────┘
                           │
                           ▼
                    ┌────────────────┐
                    │  Disconnect    │
                    └────────────────┘
```

## Descomposición de Responsabilidades

### 🎯 main.py - Punto de Entrada
```
Responsabilidad: INICIAR
├─ Leer parámetros
├─ Crear objetos de configuración
├─ Instanciar caso de uso
└─ Llamar execute()
```

### 🧠 use_cases/release_process.py - Lógica de Negocio
```
Responsabilidad: ORQUESTAR
├─ Coordinar pasos del proceso
├─ Tomar decisiones de negocio
├─ Delegar acciones técnicas al driver
├─ Manejo de errores y recuperación
└─ Logging del flujo
```

### 🛠️ adapters/sap_driver.py - Adaptador Técnico
```
Responsabilidad: IMPLEMENTAR (CÓMO)
├─ Conectar a SAP con pywin32
├─ Navegar GUI
├─ Presionar botones
├─ Escribir campos
├─ Leer datos
└─ Desconectar
```

### 📊 domain/export_data.py - Modelos de Datos
```
Responsabilidad: DEFINIR (QUÉ)
├─ ExportConfig (qué exportar)
├─ SAPCredentials (con qué autenticarse)
└─ SAPConnection (a dónde conectar)
```

## Interacción Entre Capas

```
main.py (Configuración)
  │
  └─> ExportZMM0164UseCase (Domain Objects + Driver)
       │
       ├─> Paso 1: driver.connect()
       │   └─> SAPDriver.connect()
       │       └─> win32com.client.GetObject("SAPGUI")
       │
       ├─> Paso 2: driver.login(credentials)
       │   └─> SAPDriver.login()
       │       └─ Usa SAPCredentials.client, user, password
       │
       ├─> Paso 3: driver.send_command(f"/n{transaction}")
       │   └─> SAPDriver.send_command()
       │
       ├─> Paso 4: driver.set_field_text(field_id, material_code)
       │   └─ Usa ExportConfig.material_code
       │
       └─> Paso 5: driver.set_field_text(path, output_folder)
           └─ Usa ExportConfig.output_folder
```

## Aislamiento de Dependencias

```
                         ┌─────────────┐
                         │ pywin32     │
                         └──────▲──────┘
                                │
                         ┌──────┴─────────┐
                         │ SAPDriver      │
                         │ (adapters/)    │
                         └──────▲─────────┘
                                │
                      ┌─────────┴─────────┐
                      │ ExportZMM0164     │
                      │ UseCase           │
                      │ (use_cases/)      │
                      └──────▲────────────┘
                             │
                   ┌─────────┴────────┐
                   │ main.py          │
                   │ + config.py      │
                   └──────────────────┘

Flujo de Dependencias: ↑ (hacia arriba)
- main.py depende de: use_cases, domain, config
- use_cases depende de: adapters, domain
- adapters depende de: pywin32 (externa)
- domain: NO depende de nada (pura)

Ventaja: Cambio en pywin32 → solo afecta adapters
```

## Patrón: Inyección de Dependencias

```python
# ✅ BIEN: Dependencias inyectadas en constructor
class ExportZMM0164UseCase:
    def __init__(self, sap_connection, credentials, export_config):
        self.driver = SAPDriver(...)  # Creado dentro
        # O mejor:
        # self.driver = driver  # Inyectado (para testing)

# ❌ MAL: Dependencias globales
SAP_SESSION = None  # Global
def export():
    SAP_SESSION.connect()  # Acoplado
```

## Testabilidad

```
┌─────────────────────────────────────────────────────────────┐
│                      TESTS                                   │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ 1. Unit Tests (domain/)                                      │
│    └─ Test ExportConfig, SAPCredentials, SAPConnection      │
│       [No dependen de nada → fáciles de testear]             │
│                                                              │
│ 2. Unit Tests (adapters/) con Mock                          │
│    └─ Test SAPDriver con mock de win32com                   │
│       [Inyectar mock → sin SAP real necesario]               │
│                                                              │
│ 3. Integration Tests (use_cases/) con Mock                  │
│    └─ Test ExportZMM0164UseCase con driver mock             │
│       [Inyectar mock driver → test de lógica sin SAP]        │
│                                                              │
│ 4. E2E Tests (main.py)                                      │
│    └─ Test completo contra SAP real (opcional)              │
│       [Ejecuta todo el flujo]                               │
└─────────────────────────────────────────────────────────────┘
```

## Escalabilidad Horizontal

```
Bot_sap_zmm0164/               Bot_sap_zmm0165/
├── main.py                    ├── main.py
├── src/use_cases/             ├── src/use_cases/
│   └── release_process.py     │   └── approval_process.py
└── requirements.txt           └── requirements.txt

        ↑ Ambos reutilizan ↑

shared/ (opcional en producción)
├── adapters/
│   └── sap_driver.py          ← Compartido
├── domain/
│   └── export_data.py         ← Compartido
└── requirements.txt
```

## Matriz de Decisiones Arquitectónicas

| Decisión | Razón | Alternativas Rechazadas |
|----------|-------|------------------------|
| **Separar en 3 capas** | Responsabilidad única | Todo en 1 archivo |
| **Domain como dataclasses** | Validación y claridad | Dicts simples |
| **Driver como clase** | Encapsulación de estado | Funciones globales |
| **Inyección de configuración** | Múltiples ambientes | Hardcoded |
| **main.py minimal** | Punto de entrada claro | Lógica mezclada en main |
| **pywin32 solo en adapter** | Aislamiento técnico | Importar en cualquier módulo |

---

**Conclusión**: Esta arquitectura es **profesional, mantenible y escalable** 🚀
