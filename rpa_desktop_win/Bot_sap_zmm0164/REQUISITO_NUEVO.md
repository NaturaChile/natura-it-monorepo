# REQUISITO: Bot SAP ZMM0164 - Exportación Automatizada de Datos de Materiales

**Versión:** 1.0  
**Estado:** Borrador - Análisis y Diseño  
**Fecha Creación:** 2026-03-02  
**Autor:** Equipo RPA - NaturaChile  
**Última Actualización:** 2026-03-02  
**Proyecto:** SAP RPA Automation - NaturaChile  

---

## 1. DESCRIPCIÓN GENERAL

### 1.1 Resumen Ejecutivo
Actualmente, la exportación de datos de materiales desde la transacción ZMM0164 en SAP se realiza de forma manual por los usuarios de Logística y Compras, lo que consume tiempo y está expuesto a errores humanos. Se requiere automatizar este proceso mediante un bot de RPA que se conecte a SAP, inicie sesión, navegue a la transacción ZMM0164, busque el material especificado, exporte los datos a un archivo .XLS y lo guarde en la ruta compartida correspondiente. El bot debe ser escalable, permitiendo reutilizarse para otras transacciones SAP y adaptable a diferentes ambientes (desarrollo, testing, producción).

### 1.2 Objetivo
Desarrollar un bot de automatización robusta (RPA) que:
- **Específico:** Automatice la exportación de datos de materiales desde ZMM0164 en SAP
- **Medible:** Logre 100% de automatización del flujo manual, reduciendo tiempo de 15 minutos a <2 minutos por ejecución
- **Alcanzable:** Implementable en 2 semanas con tecnología pywin32 y arquitectura DDD
- **Relevante:** Aplicable a ambientes DEV, TEST y PROD, y reutilizable para otras transacciones
- **Dentro de plazo:** Completado y en UAT antes del 2026-03-20

### 1.3 Alcance
- **Incluye:**
  - Conectar a SAP GUI (usando pywin32)
  - Autenticarse con credenciales (cliente, usuario, contraseña, idioma)
  - Navegar a la transacción ZMM0164
  - Buscar y filtrar por código de material
  - Exportar datos a formato XLS
  - Guardar archivo en ruta compartida (Z:\Publico\RPA\Plan Chile\zmm0164)
  - Manejar errores y reintentos automáticos
  - Soportar múltiples ambientes (dev, test, prod)
  - Logging detallado de cada paso del proceso
  - Desconexión limpia de SAP

- **Excluye:**
  - Modificación de datos en SAP (solo lectura/exportación)
  - Integración con otros sistemas más allá de SAP
  - Procesamiento post-exportación complejo de archivos
  - Envío automático de archivos por email (fase 2)
  - Validación lógica de datos (responsabilidad del usuario destino)

---

## 2. REQUISITOS FUNCIONALES

### RF-001: Conexión Inicial a SAP GUI y Autenticación
- **Descripción:** El bot debe conectarse a SAP GUI usando pywin32 y realizar login con las credenciales proporcionadas
- **Entrada:** 
  - Ruta de saplogon.exe: `C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe`
  - Nombre de conexión: `1.02 - PRD - Produção/Producción` (según ambiente)
  - Credenciales: client (210), user (BOTSCL), password, language (ES)
- **Proceso:**
  1. **Paso 1a: Montaje de Carpeta Compartida (NUEVO)**
     - Validar ruta UNC: `\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164`
     - Ejecutar: `net use Z: \\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164 <password> /user:NATURA\cmancill /persistent:yes`
     - Si falla → Usar ruta UNC directamente (sin mapeo)
     - Timeout: 30 segundos
  2. **Paso 1b: Lanzar SAP GUI**
     - Si SAP no está corriendo, lanzar saplogon.exe
     - Esperar 5 segundos
  3. **Paso 1c: Obtener COM Object**
     - Conectar a SAPGUI vía win32com.client.GetObject("SAPGUI")
     - Reintentar hasta 30 veces (1 segundo cada reintento)
  4. **Paso 1d: Seleccionar Conexión**
     - Buscar conexión en lista que contenga "1.02" en descripción
     - Si no existe → Abrir conexión por nombre
  5. **Paso 1e: Login**
     - Campo cliente: `wnd[0]/usr/txtRSYST-MANDT` = "210"
     - Campo usuario: `wnd[0]/usr/txtRSYST-BNAME` = "BOTSCL"
     - Campo password: `wnd[0]/usr/pwdRSYST-BCODE` = <password>
     - Campo idioma: `wnd[0]/usr/txtRSYST-LANGU` = "ES"
     - Enviar Enter (sendVKey(0))
  6. **Paso 1f: Limpiar Message Bar**
     - Si `wnd[0]/sbar` tiene texto, enviar VKey(0) para limpiar
- **Salida:** Sesión de SAP activa en ventana wnd[0], listo para transacción
- **Criterios de Aceptación:**
  - [ ] Montaje SMB exitoso O ruta UNC disponible
  - [ ] Conexión SAP establece en < 30 segundos
  - [ ] Login exitoso con credenciales válidas
  - [ ] Manejo de error si contraseña inválida (reintento 3 veces máx)
  - [ ] Logging de inicios de sesión (exitosos y fallidos)
  - [ ] Exit code 0 si login OK, 1 si falla

### RF-002: Navegación a Transacción ZMM0164 y Búsqueda de Material
- **Descripción:** Navegar a la transacción ZMM0164, buscar e ingresar el código de material a exportar
- **Entrada:** Código de material (ej: 4100)
- **Proceso:**
  1. Enviar comando SAP: `/nzmm0164` en campo `wnd[0]/tbar[0]/okcd`
  2. Presionar VKey(0) para enviar (Enter)
  3. Esperar 2 segundos a que cargue la transacción
  4. Maximizar ventana: `wnd[0].maximize()`
  5. Ingresar código de material en campo específico: `wnd[0]/usr/ctxtSP$00006-LOW` = "4100"
  6. **Ejecutar búsqueda: Presionar botón F8** (VKey(8)) en `wnd[0]`
  7. Esperar 2 segundos a que aparezcan resultados
  8. Validar que datos se cargaron correctamente
- **Salida:** Datos del material cargados en la pantalla de ZMM0164 listos para exportar
- **Criterios de Aceptación:**
  - [ ] Transacción se abre correctamente (timeout < 20 seg)
  - [ ] Búsqueda de material retorna resultados válidos
  - [ ] Material no encontrado genera warning (reintento o log)
  - [ ] Timeout máximo de 20 segundos por navegación

### RF-003: Exportación de Datos a Archivo XLS
- **Descripción:** Generar y guardar el archivo de exportación en formato XLS
- **Entrada:** Datos de material cargados en ZMM0164, ruta de salida configurada
- **Proceso:**
  1. Presionar botón de Exportación/Save en GUI de SAP
  2. Seleccionar formato XLS en diálogo de exportación
  3. Especificar nombre de archivo: `zmm0164_[material_code]_[timestamp].xls`
  4. Seleccionar ruta de destino: `Z:\Publico\RPA\Plan Chile\zmm0164` (según ambiente)
  5. Confirmar y guardar archivo
  6. Validar que archivo fue creado exitosamente
- **Salida:** Archivo .XLS descargado en la carpeta compartida
- **Criterios de Aceptación:**
  - [ ] Archivo XLS generado con nombre descriptivo
  - [ ] Archivo contiene datos válidos y completos
  - [ ] Ruta de destino existe y tiene permisos
  - [ ] Timestamp añadido al nombre para evitar sobrescrituras
  - [ ] Validación de tamaño de archivo (> 0 bytes)

### RF-004: Manejo de Errores y Recuperación + Cierre Seguro
- **Descripción:** Gestión robusta de errores y cierre seguro del bot
- **Casos de Error:**
  - [ ] **Fallo de conexión SAP:** Reintento automático (max 3 intentos, delay 5 seg)
  - [ ] **Credenciales inválidas:** Marcar como error crítico, log y abort (no reintentar)
  - [ ] **Material no encontrado:** Log WARNING, continuar sin datos
  - [ ] **Timeout de GUI:** Reintento con incremento de timeout, max 3 veces
  - [ ] **Sin permisos en carpeta de salida:** Error crítico, alerta a administrador
  - [ ] **Espacio en disco insuficiente:** Error crítico con detalle
- **Cierre Seguro (CRÍTICO):**
  - Enviar comando: `/nex` en SAP (logout)
  - Esperar 2 segundos
  - **FORZAR cierre del proceso:** `taskkill /F /IM saplogon.exe`
    - /F = Fuerza el cierre (sin confirmar)
    - /IM = Especifica imagen (ejecutable)
    - Esto evita que SAP quede colgado entre ejecuciones
- **Reintentos:** 
  - Política: 3 reintentos máximo para errores transitorios
  - Delay: 5 segundos entre reintentos
  - No reintentar para errores de credenciales o permisos
- **Logging:** 
  - Nivel DEBUG en desarrollo
  - Nivel INFO en testing
  - Nivel ERROR en producción
  - Logs almacenados en: `logs/zmm0164_[ambiente]_[fecha].log`
  - Información a loguear: timestamp, nivel, mensaje, stack trace, valores de entrada/salida

---

## 3. REQUISITOS NO FUNCIONALES

### 3.1 Performance
- **Tiempo de respuesta:** Máximo 2 minutos de inicio a fin (conexión + búsqueda + exportación + guardado)
  - Conexión SAP: < 30 segundos
  - Navegación a transacción: < 20 segundos
  - Búsqueda de material: < 15 segundos
  - Exportación y guardado: < 30 segundos
- **Throughput:** Una ejecución por vez (proceso secuencial no concurrente).
  - Capacidad: 30 materiales por hora (2 min c/u)
  - 240 materiales por turno de 8 horas
- **Escalabilidad:** Inicialmente un bot único ejecutándose en schedule
  - Base para escalabilidad futura con múltiples instancias
  - Reutilizable para otras transacciones (ZMM0165, etc.)

### 3.2 Seguridad
- **Autenticación SAP:** 
  - Usuario SAP: BOTSCL (cuenta de servicio dedicada)
  - Variables de entorno: **BOT_ZMM0164_SAP_CLIENT, BOT_ZMM0164_SAP_USER, BOT_ZMM0164_SAP_PASSWORD** (con prefijo específico del bot)
  - Credenciales almacenadas en variables de entorno (NO en código)
  - Para GitHub Actions: GitHub Secrets
  - MFA: No requerida (cuenta de servicio SAP no soporta MFA)
- **Autenticación de Red (SMB/CIFS):**
  - Dominio: NATURA
  - Usuario: cmancill (o similar de credenciales compartidas)
  - Variables: **BOT_ZMM0164_OUTPUT_NET_DOMAIN, BOT_ZMM0164_OUTPUT_NET_USER, BOT_ZMM0164_OUTPUT_NET_PASSWORD**
  - Variables: **BOT_ZMM0164_OUTPUT_UNC_PATH** (ej: `\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164`)
  - Montaje con: `net use Z: \\10.156.145.28\Areas... /user:NATURA\cmancill /persistent:yes`
- **Autorización:**
  - Usuario BOTSCL debe tener role de lectura en ZMM0164
  - Acceso a carpeta compartida con permisos de escritura
  - No requiere modificación de transacciones (solo lectura)
- **Criptografía:**
  - Credenciales NO se loguean (ni completas ni parciales)
  - Archivos XLS almacenados en carpeta compartida (sin encriptación adicional requerida)
  - Manejo de secretos via GitHub Secrets para CI/CD
- **Cumplimiento:**
  - Cumple normativa interna de NaturaChile para bots RPA
  - Auditoría vía logs del bot y auditoría SAP (transacción ejecutada por BOTSCL)
  - Datos exportados no contienen información PII (material procurement data)

### 3.3 Confiabilidad
- **Disponibilidad:** 
  - Objetivo: 99% uptime durante horarios de negocio (7:00-19:00 LT)
  - Ejecuciones planificadas en horarios de bajo uso SAP (6:00 AM, 12:00 PM, 6:00 PM)
  - Alertas de fallo a través de logs y notificación a administrador
- **Recuperación:** 
  - MTRR (Mean Time to Recovery): < 15 minutos
  - Reintentos automáticos incorporados para fallos transitorios
  - Capacidad de re-ejecución manual si falla programación
- **Backups:**
  - Archivos XLS generados: Se mantienen en carpeta compartida con política de rotación (90 días)
  - Código del bot: Versionado en Git con backups automáticos
  - Logs: Rotados diariamente, mantenidos por 30 días

### 3.4 Mantenibilidad
- **Código limpio:** 
  - Seguir PEP-8 para Python
  - Máximo 100 caracteres por línea
  - Type hints en funciones
  - Nombres descriptivos (variable, función, clase)
  - Métodos < 30 líneas de código
- **Documentación:**
  - Docstrings en todas las clases y métodos (formato Google)
  - Comentarios para lógica compleja
  - README.md con instrucciones de setup
  - ARQUITECTURA.md documentando DDD
  - QUICK_START.md para nuevos desarrolladores
- **Versionamiento:**
  - Semantic Versioning (MAJOR.MINOR.PATCH)
  - Versión inicial: 1.0.0
  - Tags en Git para cada release
  - Changelog actualizado en RESUMEN.md

### 3.5 Compatibilidad
- **Versiones Python:** 3.9, 3.10, 3.11
  - Nota: pywin32 solo funciona en Windows
- **Sistemas Operativos:** 
  - Windows 10 Pro/Enterprise (requerido para pywin32)
  - Windows Server 2016+ (servidor RPA)
  - No compatible con Linux (pywin32 es solo Windows)
- **Dependencias:**
  - pywin32==305 (para interacción con SAP GUI)
  - python-dotenv (para variables de entorno)
  - requests (para integraciones futuras)
  - pytest (para testing)
  - Ver completo en [requirements.txt](requirements.txt)

---

## 4. DEPENDENCIAS Y PREREQUISITOS

### 4.1 Dependencias Internas
- Monorepo: `NaturaChile/natura-it-monorepo`
- Carpeta compartida: `Z:\Publico\RPA\Plan Chile\zmm0164` (debe existir)
- Cuenta de servicio SAP: BOTSCL (debe estar creada en cliente 210)
- Acceso a instancia SAP: 1.02 - PRD - Produção/Producción

### 4.2 Dependencias Externas
- **Sistemas:** 
  - SAP ECC 6.0 con transacción ZMM0164 disponible
  - SAP GUI (Frontend) instalado en servidor RPA
  - Sistema de archivos con carpeta compartida en Z:\
- **Bibliotecas:**
  - pywin32 (WIN32 COM interface para SAP GUI interacción)
  - python-dotenv (gestión de variables de entorno)
  - pytest (framework de testing)
- **Configuraciones:**
  - Conexión SAP configurada en saplogon.exe
  - Credenciales en variables de entorno del sistema o GitHub Secrets

### 4.3 Prerequisitos
- [ ] Usuario BOTSCL creado en SAP cliente 210
- [ ] Permisos de lectura en transacción ZMM0164 para usuario BOTSCL
- [ ] SAP GUI instalado en servidor Windows de RPA
- [ ] Python 3.9+ instalado en servidor
- [ ] Carpeta Z:\Publico\RPA\Plan Chile\zmm0164 creada Y accesible
  - **O** ruta UNC `\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164` disponible
- [ ] Variables de entorno configuradas:
  - **SAP:** BOT_ZMM0164_SAP_CLIENT, BOT_ZMM0164_SAP_USER, BOT_ZMM0164_SAP_PASSWORD, BOT_ZMM0164_SAP_LANGUAGE
  - **RED:** BOT_ZMM0164_OUTPUT_NET_DOMAIN, BOT_ZMM0164_OUTPUT_NET_USER, BOT_ZMM0164_OUTPUT_NET_PASSWORD
  - **RUTA:** BOT_ZMM0164_OUTPUT_UNC_PATH, BOT_ZMM0164_OUTPUT_FOLDER
- [ ] Monorepo clonado en servidor RPA
- [ ] Conexión de red a servidor SAP activa
- [ ] Comandos Windows disponibles: `net use`, `taskkill`

---

## 5. CASOS DE USO

### CU-001: Exportar Datos de Material de ZMM0164
```
Actor Principal: Bot RPA / Scheduler (GitHub Actions)
Precondición: 
  - Servidor RPA disponible con Windows y SAP GUI instalado
  - Credenciales de BOTSCL configuradas en variables de entorno
  - Conexión a SAP activa
  - Carpeta de salida existe y tiene permisos

Flujo Principal:
  1. Bot recibe material code (ej: 4100) del scheduler o parámetro
  2. Bot inicia SAPDriver y conecta a SAP GUI
  3. Bot realiza login con credenciales BOTSCL
  4. Bot ejecuta comando /nzmm0164 para navegar a transacción
  5. Bot ingresa código de material en campo de búsqueda
  6. Bot presiona filtrar/buscar
  7. Bot verifica que haya resultados
  8. Bot presiona botón de exportación
  9. Bot selecciona formato XLS
  10. Bot especifica nombre de archivo con timestamp
  11. Bot confirma guardado en carpeta Z:\Publico\RPA\Plan Chile\zmm0164
  12. Bot valida que archivo fue creado
  13. Bot desconecta de SAP
  14. Bot loguea éxito
  15. Sistema retorna código de salida 0

Postcondición: 
  - Archivo XLS disponible en carpeta compartida
  - Log registra ejecución exitosa con timestamp
  - Sesión SAP cerrada limpiamente

Flujos Alternativos:
  A1. En paso 3, si login falla por contraseña inválida:
      1. Bot intenta reintento automático (max 3)
      2. Si falla después de 3 intentos, lanza excepción y aborta
      3. Log registra error crítico
      
  A2. En paso 7, si no se encuentran resultados:
      1. Bot loguea WARNING: Material no encontrado
      2. Bot continúa sin exportar
      3. Sistema retorna código de salida 1 (parcial)
      
Flujos de Error:
  E1. En paso 2, si conexión a SAP falla:
      1. Bot reintenta auto (3 veces, 5 seg entre reintento)
      2. Si persiste, lanza ConnectionError
      3. Sistema retorna código de salida 2 (error)
      4. Alerta a administrador via logging
  
  E2. En paso 10, si no hay espacio en disco:
      1. Excepción OSError detectado
      2. Log registra error crítico
      3. Sistema retorna código de salida 3
  
  E3. En paso 11, si permisos insuficientes en carpeta:
      1. Excepción PermissionError
      2. Log con detalle de permisos
      3. Sistema retorna código de salida 4
```

### CU-002: Ejecutar Bot en Horario Programado vía GitHub Actions
```
Actor Principal: GitHub Actions Scheduler
Precondición:
  - Servidor RPA registrado como GitHub Self-Hosted Runner
  - Workflow YAML configurado en .github/workflows/
  - Secrets configurados en GitHub: BOT_ZMM0164_SAP_CLIENT, BOT_ZMM0164_SAP_USER, BOT_ZMM0164_SAP_PASSWORD

Flujo Principal:
  1. GitHub Actions dispara workflow en horario programado (cron)
  2. Job clona repositorio en servidor RPA
  3. Job instala dependencias: pip install -r requirements.txt
  4. Job ejecuta: python Bot_sap_zmm0164/main.py
  5. Bot ejecuta CU-001 (flujo principal de exportación)
  6. Job captura exit code del bot
  7. Job almacena logs como artifacts
  8. Si exit code != 0, job notifica fallo
  9. GitHub retorna estado (success/failure) al repositorio

Postcondición:
  - Workflow ejecutado exitosamente
  - Logs disponibles en GitHub Actions
  - Archivo XLS generado en carpeta compartida

Flujos Alternativos:
  A1. Si el runner no está disponible:
      1. GitHub Actions reintenta por X minutos
      2. Si no se conecta, falla el job
      3. Notificación de error a administrador
```

---

## 6. DISEÑO ARQUITECTÓNICO (Para SDD)

### 6.1 Componentes Principales
```
┌─────────────────────────────────┐
│  [Nombre Componente A]          │
├─────────────────────────────────┤
│ Responsabilidad: [Descripción]  │
│ Interfaz:                       │
│  - entrada(params) -> resultado │
│  - validar(data) -> bool        │
└─────────────────────────────────┘

┌─────────────────────────────────┐
│  [Nombre Componente B]          │
├─────────────────────────────────┤
│ Responsabilidad: [Descripción]  │
│ Interfaz:                       │
│  - procesar(data) -> output     │
└─────────────────────────────────┘
```

### 6.2 Flujo de Datos

```
1. CONFIG (config.py)
   ├─ SAP_CONFIG[ENVIRONMENT]
   ├─ CREDENTIALS_CONFIG
   └─ EXPORT_SETTINGS[ENVIRONMENT]
            │
            ▼
2. MAIN.PY - Instancia objetos
   ├─ SAP_CONNECTION = SAPConnection(...)
   ├─ CREDENTIALS = SAPCredentials(...)
   ├─ EXPORT_CONFIG = ExportConfig(...)
            │
            ▼
3. USE_CASE - Orquesta flujo
   ├─ use_case.execute()
            │
        ┌───┴───────────────┬──────────────────┐
        │                   │                  │
        ▼                   ▼                  ▼
   _connect()         _login()           _navigate_and_search()
   (SAPDriver)        (SAPDriver)         (SAPDriver)
        │                 │                  │
        └─────────────────┼──────────────────┘
                          ▼
                   _export_data()
                   (SAPDriver +
                    Filesystem)
                          │
                          ▼
                   _cleanup()
                   (SAPDriver)
                          │
                          ▼
             RESULT: archivo .XLS generado
                en Z:\Publico\RPA\Plan Chile\zmm0164
```

### 6.3 Patrones de Diseño
- **Patrón:** Domain-Driven Design (DDD) adaptado para RPA
- **Justificación:** 
  - Separación clara entre lógica de negocio y detalles técnicos
  - Facilita testing (mockear SAPDriver sin SAP real)
  - Reutilizable para otros bots (otros adapters)
  - Escalable: agregar nuevas transacciones sin tocar SAP

- **Patrón:** Adapter Pattern (para SAPDriver)
- **Justificación:**
  - Encapsula complejidad de pywin32 y COM
  - Si SAP cambia, solo modificar adapter
  - Permite mockear para tests

- **Patrón:** Retry with Exponential Backoff
- **Justificación:**
  - Manejar fallos transitorios de red/SAP
  - Evitar carga en sistema durante picos

---

## 7. PLAN DE TESTING (TDD)

### 7.1 Estrategia de Testing
- **Cobertura mínima:** 80% de código (uso de pytest + coverage)
- **Tipos de test:**
  - **Unit Tests (UT):** Probar SAPDriver y UseCase aisladamente (90% de tests)
  - **Integration Tests (IT):** Probar UseCase + MockDriver (8% de tests)
  - **E2E Tests (ET):** Pruebas en ambiente TEST con SAP real (2% de tests, manual)

### 7.2 Test Cases

#### UT-001: SAPDriver.connect() retorna conexión válida
```python
# Arrange
driver = SAPDriver(
    sap_logon_path=r"C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe",
    connection_name="TEST_CONNECTION"
)

# Act (mocked pywin32)
result = driver.connect()

# Assert
assert result is not None
assert driver.is_connected() == True
```

#### UT-002: SAPDriver.login() exitoso con credenciales válidas
```python
# Arrange
driver_mock.connect()  # Ya conectado
credentials = SAPCredentials(
    client="210",
    user="BOTSCL",
    password="valid_pwd",
    language="ES"
)

# Act
result = driver_mock.login(**credentials.__dict__)

# Assert
assert result == True
```

#### UT-003: SAPDriver.login() falla con credenciales inválidas
```python
# Arrange
driver_mock.connect()

# Act & Assert
with pytest.raises(AuthenticationError):
    driver_mock.login(
        client="210",
        user="BOTSCL",
        password="invalid_pwd",
        language="ES"
    )
```

#### UT-004: ExportZMM0164UseCase.execute() flujo completo (mocked)
```python
# Arrange
config = ExportConfig(material_code="4100", output_folder=r"C:\temp")
credentials = SAPCredentials(...)
connection = SAPConnection(...)
driver_mock = MockSAPDriver()  # Mock
use_case = ExportZMM0164UseCase(
    sap_connection=connection,
    credentials=credentials,
    export_config=config,
    driver=driver_mock
)

# Act
result = use_case.execute()

# Assert
assert result["exito"] == True
assert os.path.exists(result["archivo_generado"])
assert driver_mock.connect_called
assert driver_mock.login_called
assert driver_mock.disconnect_called
```

#### UT-005: ExportZMM0164UseCase manejo de error de conexión
```python
# Arrange
driver_mock.connect.side_effect = ConnectionError("SAP not available")
use_case = ExportZMM0164UseCase(..., driver=driver_mock)

# Act & Assert
with pytest.raises(ConnectionError):
    use_case.execute()
```

#### UT-006: Reintento automático después de fallo
```python
# Arrange
driver_mock.connect.side_effect = [
    ConnectionError(),  # Intento 1: falla
    ConnectionError(),  # Intento 2: falla
    MockConnection(),   # Intento 3: éxito
]
use_case = ExportZMM0164UseCase(..., driver=driver_mock, max_retries=3)

# Act
result = use_case.execute()

# Assert
assert result["exito"] == True
assert driver_mock.connect.call_count == 3
```

#### IT-001: Integración UseCase + MockDriver
```python
# Arrange
config = ExportConfig(...)
use_case = ExportZMM0164UseCase(config, ..., driver=MockSAPDriver())

# Act
result = use_case.execute()

# Assert
- Verificar archivo .XLS creado
- Verificar contenido del archivo (encabezados, datos)
- Verificar logs generados
- Verificar exit code == 0
```

#### ET-001: Test End-to-End en ambiente TEST (con SAP real)
```
Precondición:
- SAP TEST disponible
- Material 4100 existe en TEST
- Carpeta Z:\Publico\RPA\Plan Chile\zmm0164_TEST existe

Pasos:
1. Conectar a SAP TEST
2. Navegar a ZMM0164
3. Buscar material 4100
4. Exportar a XLS
5. Guardar en carpeta TEST

Validaciones:
- Archivo generado
- Archivo contiene datos correctos
- Log muestra todo el flujo
- Exit code = 0
```

### 7.3 Datos de Prueba
```python
TEST_DATA = {
    "caso_valido": {
        "material_code": "4100",
        "client": "210",
        "user": "BOTSCL",
        "expected_result": {"exito": True, "registros": > 0}
    },
    "caso_limite": {
        "material_code": "9999",  # Materialísimo que existe
        "expected_result": {"exito": True, "registros": 1}
    },
    "caso_material_no_existe": {
        "material_code": "00000",  # No existe
        "expected_result": {"exito": False, "error": "Material not found"}
    },
    "caso_credenciales_invalidas": {
        "client": "210",
        "user": "BOTSCL",
        "password": "wrong_password",
        "expected_result": {"exito": False, "error": "Authentication failed"}
    },
}
```

### 7.4 Métricas de Calidad
- **Cobertura:**
  - Línea: 80% mínimo
  - Rama: 75% mínimo
  - Ruta: 70% mínimo
  - Medida con: `pytest --cov=src --cov-report=html`
  
- **Mantenibilidad:**
  - Índice de complejidad ciclomatática (M) < 10
  - Métodos < 30 líneas de código
  - Clases < 200 líneas de código
  - Máximo 3 niveles de indentación
  - Medida con: `radon cc -a src/`
  
- **Deuda Técnica:**
  - Máximo 5% (evaluada visualmente + linting)
  - Usar: `pylint src/ --disable=all --enable=line-too-long,too-many-locals`
  - Fix: $ pylint --generate-rcfile > .pylintrc

---

## 8. INTERFACES Y CONTRATOS

### 8.1 API/Métodos Principales

#### Clase: `ExportZMM0164UseCase`
```python
class ExportZMM0164UseCase:
    """Caso de uso para exportación de datos desde ZMM0164."""
    
    def __init__(
        self,
        sap_connection: SAPConnection,
        credentials: SAPCredentials,
        export_config: ExportConfig,
        driver: Optional[SAPDriver] = None
    ):
        """
        Inicializar caso de uso.
        
        Args:
            sap_connection: Parámetros de conexión SAP
            credentials: Credenciales de usuario
            export_config: Configuración de exportación
            driver: SAPDriver (default: crear uno nuevo)
        """
    
    def execute(self) -> Dict[str, Any]:
        """
        Ejecutar flujo completo de exportación.
        
        Returns:
            {
                "exito": bool,
                "archivo_generado": str (ruta del archivo .XLS),
                "registros_exportados": int,
                "tiempo_ejecucion_segundos": float,
                "mensaje": str,
                "codigo_error": str (si aplica)
            }
        
        Raises:
            ConnectionError: Si falla conexión a SAP
            PermissionError: Si sin acceso a carpeta de salida
            OSError: Si problemas con escritura de archivo
            TimeoutError: Si excede timeout máximo
        """
```

#### Clase: `SAPDriver`
```python
class SAPDriver:
    """Adaptador para interactuar con SAP GUI."""
    
    def connect(self) -> bool:
        """Conectar a SAP GUI. Retorna True si exitoso."""
    
    def login(
        self,
        client: str,
        user: str,
        password: str,
        language: str
    ) -> bool:
        """Realizar login en SAP. Retorna True si exitoso."""
    
    def send_command(self, command: str) -> None:
        """Enviar comando (ej: /nzmm0164)."""
    
    def set_field_text(self, field_id: str, text: str) -> None:
        """Establecer texto en campo de GUI."""
    
    def press_button(self, button_id: str) -> None:
        """Presionar botón en GUI."""
    
    def get_field_value(self, field_id: str) -> str:
        """Obtener valor de un campo."""
    
    def wait_for_element(
        self,
        element_id: str,
        timeout_seconds: int = 20
    ) -> bool:
        """Esperar a que elemento esté visible."""
    
    def disconnect(self) -> None:
        """Desconectar de SAP."""
```

### 8.2 Eventos de Logging
- **logger.debug():** Detalles de cada paso (desarrollo)
- **logger.info():** Eventos importantes (inicio, fin, cambios de estado)
- **logger.warning():** Condiciones atípicas (material no encontrado, reintentos)
- **logger.error():** Errores que permiten continuar
- **logger.exception():** Errores que detienen ejecución con stack trace

---

## 9. CONFIGURACIÓN Y VARIABLES DE ENTORNO

Configuración multi-ambiente manejada en [config.py](config.py) y [security/vault_helper.py](security/vault_helper.py):

```python
# config.py - Lee desde Vault centralizado + variables de entorno específicas del bot

# CREDENCIALES SAP (con prefijo BOT_ZMM0164_)
CREDENTIALS = SAPCredentials(
    client=get_secret("BOT_ZMM0164_SAP_CLIENT", "210"),
    user=get_secret("BOT_ZMM0164_SAP_USER", "BOTSCL"),
    password=get_secret("BOT_ZMM0164_SAP_PASSWORD"),  # REQUERIDO
    language=get_secret("BOT_ZMM0164_SAP_LANGUAGE", "ES"),
)

# CREDENCIALES DE RED (SMB/CIFS para montaje con net use)
NET_DOMAIN = get_secret("BOT_ZMM0164_OUTPUT_NET_DOMAIN", "NATURA")
NET_USER = get_secret("BOT_ZMM0164_OUTPUT_NET_USER", "cmancill")
NET_PASSWORD = get_secret("BOT_ZMM0164_OUTPUT_NET_PASSWORD")  # REQUERIDO
NET_UNC_PATH = get_secret("BOT_ZMM0164_OUTPUT_UNC_PATH", r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164")

# MONTAJE SMB y RUTAS DE SALIDA
if mount_smb_windows(NET_UNC_PATH, "Z", NET_USER, NET_PASSWORD, NET_DOMAIN):
    OUTPUT_FOLDER = r"Z:\Publico\RPA\Plan Chile\zmm0164"  # Montaje exitoso
else:
    OUTPUT_FOLDER = NET_UNC_PATH  # Fallback a ruta UNC si no se puede montar

EXPORT_CONFIG = ExportConfig(
    material_code=get_secret("BOT_ZMM0164_MATERIAL_CODE", "4100"),
    output_folder=OUTPUT_FOLDER,
    file_format=get_secret("BOT_ZMM0164_FILE_FORMAT", "XLS"),
)

LOG_SETTINGS = {
    "development": {"level": "DEBUG", "file": None},
    "testing": {"level": "INFO", "file": r"logs\zmm0164_test.log"},
    "production": {"level": "ERROR", "file": r"logs\zmm0164_prod.log"},
}

RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 5,  # segundos
    "timeout_sap_connect": 30,  # segundos
    "timeout_field_wait": 20,  # segundos
    "delay_sap_launch": 5,  # segundos tras lanzar saplogon.exe
    "delay_search_result": 2,  # segundos tras ejecutar F8
    "delay_dialog_confirm": 1,  # segundos tras confirmar
    "delay_sap_logoff": 2,  # segundos tras /nex antes taskkill
}
```

**Variables de Entorno Requeridas (Sistema || GitHub Secrets):**

| Variable | Descripción | Default | Requerido |
|----------|-------------|---------|----------|
| `RPA_ENV` | Ambiente ejecución | development | No |
| `BOT_ZMM0164_SAP_CLIENT` | Cliente SAP | 210 | No |
| `BOT_ZMM0164_SAP_USER` | Usuario SAP | BOTSCL | No |
| `BOT_ZMM0164_SAP_PASSWORD` | Contraseña SAP | - | **SÍ** |
| `BOT_ZMM0164_SAP_LANGUAGE` | Idioma SAP | ES | No |
| `BOT_ZMM0164_OUTPUT_NET_DOMAIN` | Dominio Windows | NATURA | No |
| `BOT_ZMM0164_OUTPUT_NET_USER` | Usuario red SMB | cmancill | No |
| `BOT_ZMM0164_OUTPUT_NET_PASSWORD` | Contraseña SMB | - | No (pero recomendado) |
| `BOT_ZMM0164_OUTPUT_UNC_PATH` | Ruta UNC compartida | `\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164` | No |
| `BOT_ZMM0164_MATERIAL_CODE` | Material a exportar | 4100 | No |
| `BOT_ZMM0164_FILE_FORMAT` | Formato exportación | XLS | No |

**GitHub Secrets (para GitHub Actions CI/CD):**
```yaml
secrets:
  BOT_ZMM0164_SAP_CLIENT: '210'
  BOT_ZMM0164_SAP_USER: 'BOTSCL'
  BOT_ZMM0164_SAP_PASSWORD: <password_vault>
  BOT_ZMM0164_OUTPUT_NET_DOMAIN: 'NATURA'
  BOT_ZMM0164_OUTPUT_NET_USER: 'cmancill'
  BOT_ZMM0164_OUTPUT_NET_PASSWORD: <password_vault>
  BOT_ZMM0164_OUTPUT_UNC_PATH: '\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164'
```

---

## 10. INSTALACIÓN Y CONFIGURACIÓN

### 10.1 Dependencias
```bash
# requirements.txt
pywin32==305
```

**Nota CRÍTICA:** pywin32 requiere instalación post-pip en Windows para registrar COM:
```bash
pip install pywin32
python -m pywin32_postinstall -install  # Ejecutar como Administrador
```

### 10.2 Herramientas Sistema (Requeridas)

**Comandos Windows necesarios:**
- `net use` - Montar compartidas SMB/CIFS (**NATIVO en Windows**, no requiere instalación)
- `taskkill` - Terminar procesos (**NATIVO en Windows**, no requiere instalación)

### 10.3 Setup en Servidor RPA

**Paso 1: Clonar repositorio**
```bash
git clone https://github.com/NaturaChile/natura-it-monorepo.git
cd natura-it-monorepo/rpa_desktop_win/Bot_sap_zmm0164
```

**Paso 2: Instalar dependencias (EJECUTAR COMO ADMIN)**
```bash
pip install -r requirements.txt
python -m pywin32_postinstall -install
```

**Paso 3: Configurar variables de entorno del sistema (Windows)**

Abrir: Control Panel > System > Advanced System Settings > Environment Variables

Agregar variables:
```
RPA_ENV = production
BOT_ZMM0164_SAP_CLIENT = 210
BOT_ZMM0164_SAP_USER = BOTSCL
BOT_ZMM0164_SAP_PASSWORD = <contraseña_segura>
BOT_ZMM0164_OUTPUT_NET_DOMAIN = NATURA
BOT_ZMM0164_OUTPUT_NET_USER = cmancill
BOT_ZMM0164_OUTPUT_NET_PASSWORD = <contraseña_dominio>
BOT_ZMM0164_OUTPUT_UNC_PATH = \\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164
```

**O alternativa: Archivo .env local (SOLO desarrollo)**
```bash
cp .env.example .env
# Editar .env con valores apropiados
```

**Paso 4: Validar configuración**
```bash
python config.py  # Verificar que todas las variables estén correctas
```

**Paso 5: Probar montaje SMB (Opcional)**
```bash
# Verificar que compartida está accesible
net use Z: \\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164 <password> /user:NATURA\cmancill /persistent:yes
dir Z:\  # Confirmar que Z: es accesible
```

**Paso 6: Ejecutar bot**
```bash
python main.py
```

**Salida esperada:**
```
============================================================
[BOT] INICIANDO PROCESO DE EXPORTACIÓN ZMM0164
============================================================
[SMB] Montaje SMB/CIFS en Windows
   UNC Path: \\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164
   Unidad: Z:
   Usuario: NATURA\cmancill
...
[DONE] PROCESO COMPLETADO EXITOSAMENTE
============================================================
```

### 10.4 Configuración en GitHub Actions

**Crear workflow YAML** en `.github/workflows/bot-zmm0164-export.yml`:
```yaml
name: Bot SAP ZMM0164 - Exportación Automatizada

on:
  schedule:
    - cron: '0 6,12,18 * * MON-FRI'  # 6 AM, 12 PM, 6 PM en días laborales
  workflow_dispatch:  # Permitir ejecución manual

jobs:
  export:
    runs-on: [self-hosted, windows]  # Self-hosted runner en servidor RPA Windows
    steps:
      - uses: actions/checkout@v3
      
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r rpa_desktop_win/Bot_sap_zmm0164/requirements.txt
          python -m pywin32_postinstall -install
      
      - name: Run Bot ZMM0164
        working-directory: rpa_desktop_win/Bot_sap_zmm0164
        env:
          RPA_ENV: production
          BOT_ZMM0164_SAP_CLIENT: ${{ secrets.BOT_ZMM0164_SAP_CLIENT }}
          BOT_ZMM0164_SAP_USER: ${{ secrets.BOT_ZMM0164_SAP_USER }}
          BOT_ZMM0164_SAP_PASSWORD: ${{ secrets.BOT_ZMM0164_SAP_PASSWORD }}
          BOT_ZMM0164_OUTPUT_NET_DOMAIN: ${{ secrets.BOT_ZMM0164_OUTPUT_NET_DOMAIN }}
          BOT_ZMM0164_OUTPUT_NET_USER: ${{ secrets.BOT_ZMM0164_OUTPUT_NET_USER }}
          BOT_ZMM0164_OUTPUT_NET_PASSWORD: ${{ secrets.BOT_ZMM0164_OUTPUT_NET_PASSWORD }}
          BOT_ZMM0164_OUTPUT_UNC_PATH: ${{ secrets.BOT_ZMM0164_OUTPUT_UNC_PATH }}
        run: python main.py
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: zmm0164-logs-${{ github.run_id }}
          path: logs/
          retention-days: 30
      
      - name: Notify on failure
        if: failure()
        run: |
          echo "❌ Bot ZMM0164 FALLÓ"
          exit 1
```

**Agregar Secrets en GitHub** (Settings > Secrets and variables > Actions):
```
BOT_ZMM0164_SAP_CLIENT
BOT_ZMM0164_SAP_USER
BOT_ZMM0164_SAP_PASSWORD
BOT_ZMM0164_OUTPUT_NET_DOMAIN
BOT_ZMM0164_OUTPUT_NET_USER
BOT_ZMM0164_OUTPUT_NET_PASSWORD
BOT_ZMM0164_OUTPUT_UNC_PATH
```

**Paso 1: Clonar repositorio**
```bash
git clone https://github.com/NaturaChile/natura-it-monorepo.git
cd natura-it-monorepo/rpa_desktop_win/Bot_sap_zmm0164
```

**Paso 2: Instalar dependencias**
```bash
pip install -r requirements.txt
python -m pywin32_postinstall -install
```

**Paso 3: Configurar credenciales (Option A - Manual)**
```bash
# Windows CMD
set RPA_ENV=production
set SAP_CLIENT=210
set SAP_USER=BOTSCL
set SAP_PASSWORD=tu_contraseña_segura
```

**Paso 4: Configurar credenciales (Option B - Variables de sistema)**
- Control Panel > System > Advanced System Settings > Environment Variables
- Agregar nuevas variables para SAP_CLIENT, SAP_USER, SAP_PASSWORD

**Paso 5: Verificar configuración**
```bash
python config.py
```

**Paso 6: Ejecutar bot**
```bash
python main.py
```

### 10.3 Configuración en GitHub Actions

**Crear workflow YAML** en `.github/workflows/zmm0164-export.yml`:
```yaml
name: Bot SAP ZMM0164 - Exportación

on:
  schedule:
    - cron: '0 6 * * MON-FRI'  # Ejecutar 6 AM cada día lab
  workflow_dispatch:  # Manual trigger

jobs:
  export:
    runs-on: [self-hosted, windows]  # Self-hosted runner en servidor RPA
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r rpa_desktop_win/Bot_sap_zmm0164/requirements.txt
          python -m pywin32_postinstall -install
      
      - name: Run Bot ZMM0164
        working-directory: rpa_desktop_win/Bot_sap_zmm0164
        env:
          RPA_ENV: production
          SAP_CLIENT: ${{ secrets.SAP_CLIENT }}
          SAP_USER: ${{ secrets.SAP_USER }}
          SAP_PASSWORD: ${{ secrets.SAP_PASSWORD }}
        run: python main.py
      
      - name: Upload logs
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: zmm0164-logs
          path: logs/
```

**Agregar Secrets en GitHub** (Settings > Secrets):
- SAP_CLIENT
- SAP_USER
- SAP_PASSWORD

---

## 11. CRITERIOS DE ACEPTACIÓN GLOBAL

- [ ] **RF-001:** Bot conecta a SAP GUI successfully con timeout < 30 seg
- [ ] **RF-002:** navegación a ZMM0164 y búsqueda de material funciona
- [ ] **RF-003:** Archivo XLS generado con datos correctos
- [ ] **RF-004:** Manejo robusto de errores con reintentos automáticos
- [ ] **Cobertura de Tests:** >= 80% (pytest --cov=src)
- [ ] **Código:** Cumple PEP-8 (pylint score > 8.0)
- [ ] **Documentación:** 
  - [ ] Docstrings en todas las clases/métodos
  - [ ] README.md con ejemplos
  - [ ] ARQUITECTURA.md documentada
  - [ ] QUICK_START.md funcional
- [ ] **Compatibilidad:** Funciona en Windows Server 2016+ con Python 3.9+
- [ ] **Performance:** Ejecución completa en < 2 minutos
- [ ] **Seguridad:** 
  - [ ] Credenciales en variables de entorno (no en código)
  - [ ] Contraseñas nunca loguadas
  - [ ] Acceso a carpeta validado
- [ ] **Logging:** Logs detallados en logs/zmm0164_*.log
- [ ] **Integración SAP:** 
  - [ ] Bot validado en ambiente TEST
  - [ ] Datos exportados coinciden con SAP
- [ ] **GitHub Actions:** Workflow YAML funcional y testado
- [ ] **Code Review:** Aprobado por 2 desarrolladores
- [ ] **UAT:** 3 ejecuciones exitosas en producción
- [ ] **Aprobación:** Firmada por Analista, Dev, QA y PM

---

## 12. DETALLES TÉCNICOS SAP ZMM0164

Esta sección documenta los IDs exactos de campos, botones y timeouts utilizados en la interacción con SAP GUI. **CRÍTICO:** Cualquier cambio en versión de SAP o actualización de transacciones puede cambiar estos valores. Validar anualmente o antes de UAT producción.

### 12.1 IDs Exactos de Campos SAP

| Campo | ID SAP | Descripción | Tipo | Requerido |
|-------|--------|------------|------|-----------|
| Material | `wnd[0]/usr/ctxtSP$00006-LOW` | Código de material (4100, 4110, etc) | Text | Sí |
| Ruta de Exportación | `wnd[1]/usr/ctxtDY_PATH` | Ruta UNC o Z: + folder | Text | Sí |
| Nombre Archivo | `wnd[1]/usr/ctxtDY_FILENAME` | zmm0164-YYYY-MM-DD.XLS | Text | Sí |
| Opción XLS | `wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPMSYLE.0110/chk[8,1]` | Checkbox para formato XLS | Checkbox | Sí |
| Sobrescritura | `wnd[2]/tbar[0]/btn[11]` | Botón Confirmar en diálogo de sobrescritura | Button | Condicional |

### 12.2 Números de Botones y Acciones

| Botón | ID/Acción | Ventana | Función | Timeout |
|-------|-----------|---------|---------|---------|
| Export (F4) | `wnd[0]/tbar[1]/btn[30]` | wnd[0] - Main | Abre diálogo de exportación | 2 seg |
| XLS Format | `wnd[0]/tbar[1]/btn[45]` | wnd[0] - Main | Selecciona formato XLS en diálogo | 2 seg |
| Confirm | `wnd[2]/tbar[0]/btn[11]` | wnd[2] - Confirm | Confirma sobrescritura de archivo | 1 seg |
| Search (F8) | `sendVKey(8)` | wnd[0] - Main | Ejecuta búsqueda de material | 2 seg |
| Cancel (/nex) | Text field okcd | wnd[0] - Main | Devuelve a menú principal, luego exit | 5 seg |

### 12.3 Estructura de Ventanas SAP

| Ventana | ID | Propósito | Acciones |
|---------|----|---------|----|
| Main | `wnd[0]` | Transacción ZMM0164 | Input material, press F8, Export, XLS |
| Format+Save | `wnd[1]` | Diálogo de formato + path+filename | Set path, set filename, radio button |
| Confirm | `wnd[2]` | Confirmación de sobrescritura | Botón 11 para confirmar |

### 12.4 Timeouts por Operación

| Operación | Timeout | Motivo | Reintento |
|-----------|---------|--------|-----------|
| Conectar SAP GUI | 30 seg | COM GetObject puede ser lento en primera conexión | Sí (3x) |
| Búsqueda de Material (F8) | 2 seg | SAP procesa búsqueda y retorna resultados | Sí (3x) |
| Diálogo Export | 2 seg | Tiempo para que SAP renderice formato/save dialog | No |
| Confirmación Sobrescritura | 1 seg | Diálogo de confirmación simple | No |
| Cierre/Disconnect | 5 seg | Esperar a que SAP procese `/nex` antes de taskkill | No |

### 12.5 Cierre Seguro (CRÍTICO)

**Problema:** SAP puede quedar "colgado" si se mata el proceso sin aviso. COM objects no se liberan correctamente, causando puerto bloqueado en próxima ejecución.

**Solución Implementada:**
1. **Paso 1:** Enviar comando `/nex` al terminal SAP para volver a menú
2. **Paso 2:** Esperar 5 segundos para que SAP procese y cierre elegantemente
3. **Paso 3:** Si está activo aún, ejecutar `taskkill /F /IM saplogon.exe` para forzar cierre
4. **Finally block:** Asegurar que SO cierre cualquier proceso huérfano

**Código Referencia:**
```python
try:
    # ... todas las operaciones SAP ...
finally:
    self.driver.disconnect()  # Envía /nex + espera + taskkill
```

**Por qué es crítico:** Esto es CRÍTICO porque:
- SAP GUI es proceso monopolo del servidor (solo 1 sesión por usuario)
- Puerto COM 6890 puede quedarse bloqueado sin limpieza adecuada
- Segunda ejecución fallará: "Connection refused" o "Port already in use"
- Única forma de recuperar: restart manual del servidor RPA

---

## 13. RIESGOS Y MITIGACIÓN

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|--------|--------|
| SAP GUI no disponible | Media | Alto | Reintentos automáticos 3x, alertas logging, manual fallback |
| Credenciales inválidas | Baja | Alto | Validación en startup, error explicitomarcando sin reintentos |
| Cambios en estructura SAP | Baja | Muy Alto | Code review SAP, mantener documentación de field IDs, testing e2e anual |
| Permisos insuficientes | Muy Baja | Alto | Validación de carpeta en startup, error explícito |
| Timeout de red | Media | Medio | Configuración de timeouts adaptativo, + información en logs |
| Espacio en disco lleno | Muy Baja | Medio | Validación pre-exportación, archivo temporal si es necesario |
| Cambio de versión pywin32 | Baja | Medio | Pinned version en requirements.txt, testing en upgrades |
| Runner GitHub Actions caía | Baja | Medio | Alertas en logs, admin notificado, re-schedule manual |

**Planes de Contingencia:**
- **SAP no responde >3 intentos:** Enviar alerta, preservar estado, permitir retry manual
- **Credenciales mal configuradas:** Fallar en startup con mensaje claro
- **Cambios SAP GUI:** Mantener branch legacy, migrar en fase

---

## 14. CRONOGRAMA

| Fase | Actividades | Duración | Inicio | Fin | Responsable |
|------|------------|----------|--------|-----|-------------|
| **1. Análisis** | Detalle requisitos, Diseño arquitectura | 2 días | 2026-03-02 | 2026-03-03 | Analista + Senior Dev |
| **2. Setup TDD** | Crear estructura, escribir tests (red) | 3 días | 2026-03-04 | 2026-03-06 | Dev Lead + Dev Junior |
| **3. Desarrollo** | Implementar SAPDriver + UseCase (green) | 5 días | 2026-03-04 | 2026-03-10 | 2x Developers |
| **4. Refactor** | Limpiar código, optimizar, documentar | 2 días | 2026-03-11 | 2026-03-12 | Dev Lead |
| **5. Testing** | Unit tests + E2E en TEST | 3 días | 2026-03-13 | 2026-03-15 | QA + Dev |
| **6. Code Review** | Revisión pría + aprobación | 1 día | 2026-03-16 | 2026-03-16 | 2x Senior Devs |
| **7. UAT Prod** | 3 ejecuciones en producción | 2 días | 2026-03-17 | 2026-03-18 | QA + Negocio |
| **8. Deploy** | Documentación final, handover | 1 día | 2026-03-19 | 2026-03-19 | All team |

**Milestones:**
- ✅ **M1 (2026-03-06):** Estructura TDD 100%, tests escritos
- ✅ **M2 (2026-03-10):** Código funcional (green)
- ✅ **M3 (2026-03-16):** Code Review aprobado
- ✅ **M4 (2026-03-18):** UAT productión 3/3 OK
- ✅ **M5 (2026-03-19):** RELEASE

---

## 15. REFERENCIAS Y DOCUMENTACIóN RELACIONADA

**Documentación del Proyecto:**
- [ARQUITECTURA.md](./ARQUITECTURA.md) - Diagrama de capas DDD
- [README.md](./README.md) - Guía de usuario
- [QUICK_START.md](./QUICK_START.md) - 3 pasos para ejecutar
- [EXTENSIBILIDAD.md](./EXTENSIBILIDAD.md) - Cómo crear otros bots
- [RESUMEN.md](./RESUMEN.md) - Refactorización realizada

**Estándares y Referencias:**
- [PEP 8 - Python Coding Style](https://www.python.org/dev/peps/pep-0008/)
- [pytest Documentation](https://docs.pytest.org/)
- [pywin32 Documentation](https://github.com/pywin32/pywin32)
- [SAP GUI Scripting API](https://help.sap.com/viewer/7a3f1bb62c164900812d8c8ae000de1f/)

**Documentación por Generar (SDD):**
- [SDD_Bot_SAP_ZMM0164.md](./SDD_Bot_SAP_ZMM0164.md) - Especificación de diseño detallado
- [TESTING_REPORT.md](./TESTING_REPORT.md) - Reporte de cobertura y resultados
- [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) - Guía de despliegue en producción

**Monorepo:**
- [NaturaChile/natura-it-monorepo](https://github.com/NaturaChile/natura-it-monorepo)
- [rpa_desktop_win/](../)
- [Bot_sap_zmm0164/](./)

**Contactos:**
- **Analista:** [nombre/email]
- **Tech Lead:** [nombre/email]
- **QA Lead:** [nombre/email]

---

## 16. APROBACIONES

| Rol | Nombre | Email | Fecha | Firma | Observaciones |
|-----|--------|-------|-------|-------|---------------|
| Analista de Negocio | | | | | |
| Desarrollador Lead | | | | | |
| QA Lead | | | | | |
| Architectónica/Platform | | | | | |
| Project Manager | | | | | |

**Notas de Aprobación:**
- Todos los criterios de aceptación deben estar marcados como completados
- Cobertura de tests >= 80% validada
- UAT producción 3/3 exitosas
- Performance validada: < 2 min por ejecución

---

## NOTAS ADICIONALES

- **Template Base:** Este documento fue creado como REQUISITO integral del Bot SAP ZMM0164
- **Siguiente Paso:** Generar SDD (Software Design Document) una vez este requisito sea aprobado
- **Versionamiento:** Cada versión del requisito debe ser trazable en Git
- **Sincronización:** Mantener este documento sincronizado con ARQUITECTURA.md y README.md
- **DDD Implementation:** Estructura rig ue en domain/ → adapters/ → use_cases/
- **Testing First:** Escribir tests ANTES del código (Red → Green → Refactor)
- **Secrets Security:** NUNCA hardcodear credenciales, usar siempre variables de entorno
- **Reusabilidad:** Este diseño permite reutilizar SAPDriver para más transacciones (ZMM0165, etc.)

---

**Historial de Cambios:**

| Versión | Fecha | Autor | Cambios |
|---------|-------|-------|------|
| 1.0 | 2026-03-02 | Equipo RPA NaturaChile | Creación inicial del REQUISITO para Bot ZMM0164 |
| | | | Incluye RF, RNF, casos de uso, testing, arquitectura DDD |
| 1.1 | 2026-03-02 | Equipo RPA NaturaChile | **ACTUALIZACIÓN CRÍTICA:** Agregar detalles técnicos |
| | | | - Montaje SMB con net use y ruta UNC (fallback) |
| | | | - Variables de entorno con prefijo BOT_ZMM0164_* |
| | | | - IDs exactos de campos SAP (ctxtSP$00006-LOW, etc.) |
| | | | - Números exactos de botones (30, 45, 11) |
| | | | - Manejo de múltiples ventanas (wnd[0], [1], [2]) |
| | | | - Timeouts específicos por operación |
| | | | - Cierre forzado con taskkill /F /IM saplogon.exe |
| | | | - Vault centralizado + variables de entorno específicas

---

**Estado del Documento:**
- [ ] Borrador (revisiones pendientes)
- [ ] En Revisión
- [ ] Aprobado
- [ ] En Implementación
- [ ] Completado

**Próximo Paso:** Generar [SDD_Bot_SAP_ZMM0164.md](./SDD_Bot_SAP_ZMM0164.md)

