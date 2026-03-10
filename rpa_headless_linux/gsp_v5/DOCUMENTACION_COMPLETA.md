# GSP Bot v5 — Documentación Completa del Proyecto

**Última actualización:** 10 de marzo de 2026  
**Ubicación:** `rpa_headless_linux/gsp_v5/`  
**Estado:** En producción

---

## Índice

1. [Resumen Ejecutivo](#1-resumen-ejecutivo)
2. [Stack Tecnológico](#2-stack-tecnológico)
3. [Arquitectura](#3-arquitectura)
4. [Modelo de Datos](#4-modelo-de-datos)
5. [API REST (Master)](#5-api-rest-master)
6. [Orquestación de Batches](#6-orquestación-de-batches)
7. [Procesamiento Distribuido (Celery)](#7-procesamiento-distribuido-celery)
8. [Automatización del Navegador (Playwright)](#8-automatización-del-navegador-playwright)
9. [Sistema de Notificaciones por Email](#9-sistema-de-notificaciones-por-email)
10. [Herramientas Administrativas](#10-herramientas-administrativas)
11. [Despliegue e Infraestructura](#11-despliegue-e-infraestructura)
12. [Manejo de Errores y Reintentos](#12-manejo-de-errores-y-reintentos)
13. [Logging y Monitoreo](#13-logging-y-monitoreo)
14. [Flujo Completo de Ejecución](#14-flujo-completo-de-ejecución)
15. [Referencia de Archivos](#15-referencia-de-archivos)

---

## 1. Resumen Ejecutivo

**GSP Bot v5** es un sistema de automatización a escala industrial para la carga de pedidos de consultoras en el portal **GSP (Green Sales Portal)** de Natura Chile. Está diseñado para campañas de alto volumen (ej. Día de las Madres), donde se necesita cargar cientos o miles de pedidos en paralelo.

### ¿Qué problema resuelve?

Durante campañas masivas, las líderes y consultoras deben cargar manualmente sus pedidos en el portal GSP. Este proceso manual es lento, propenso a errores y no escala. GSP Bot v5 automatiza completamente este flujo:

1. Se sube un CSV/Excel con los pedidos (consultora + productos + cantidades)
2. El sistema distribuye los pedidos entre múltiples workers
3. Cada worker abre un navegador headless, inicia sesión como supervisor, selecciona la consultora, y carga los productos en el carrito
4. Al finalizar, envía notificaciones por email a consultoras, líderes y gerentes

### Capacidades principales

- **Procesamiento paralelo:** Escala horizontalmente con N workers simultáneos
- **Resiliencia:** Reintentos automáticos (3 intentos con backoff exponencial)
- **Monitoreo en tiempo real:** Dashboard Flower + API REST con estadísticas
- **Notificaciones multinivel:** Emails a consultoras, líderes y gerentes
- **Auditoría completa:** Log paso a paso de cada pedido procesado
- **Control total:** Pausar, cancelar, reintentar batches desde la API

---

## 2. Stack Tecnológico

| Componente | Tecnología | Propósito |
|-----------|-----------|-----------|
| Automatización web | **Playwright** (Chromium headless) | Interacción con el portal GSP |
| Cola de tareas | **Celery** + **Redis** | Distribución paralela de pedidos |
| Base de datos | **PostgreSQL 16** | Estado persistente y auditoría |
| API de control | **FastAPI** | Endpoints REST para gestión |
| Email | **Gmail API** (OAuth2) | Notificaciones a consultoras/líderes/gerentes |
| Logging | **structlog** | Logs estructurados en JSON |
| Contenedores | **Docker Compose** | Orquestación de servicios |
| CI/CD | **GitHub Actions** | Build y deploy automatizado |
| Configuración | **Pydantic Settings** | Variables de entorno tipadas |
| ORM | **SQLAlchemy** | Modelos de datos y queries |

---

## 3. Arquitectura

### 3.1 Topología de Servicios

```
┌──────────────────────────────────────────────────────────────────┐
│                     Docker Compose Stack                         │
│                                                                  │
│  PostgreSQL 16        Redis 7             Flower                 │
│  (Estado + Audit)     (Broker tareas)     (Dashboard)            │
│    :5432               :6379               :5555                 │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │            Master API  (FastAPI :8000)                     │  │
│  │  • Upload/gestión de batches                               │  │
│  │  • Control de órdenes (start/pause/cancel/retry)           │  │
│  │  • Envío de emails                                         │  │
│  │  • Endpoints de monitoreo                                  │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             │ Publica tareas en Redis             │
│              ┌──────────────┼──────────────┐                     │
│              │              │              │                      │
│      ┌───────▼─────┐ ┌─────▼──────┐ ┌─────▼──────┐              │
│      │ Dispatcher  │ │  Worker 1  │ │  Worker N  │   ...        │
│      │ (batches)   │ │ (orders)   │ │ (orders)   │              │
│      │ concur=1    │ │ Playwright │ │ Playwright │              │
│      └─────────────┘ └────────────┘ └────────────┘              │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 Patrón Master-Dispatcher-Workers

| Rol | Queue | Concurrencia | Responsabilidad |
|-----|-------|-------------|----------------|
| **Dispatcher** | `batches` | 1 | Recibe un batch, lee todos sus pedidos pendientes y los publica uno a uno en la cola `orders` (fan-out) |
| **Worker** | `orders` | Configurable | Toma un pedido, abre Playwright, ejecuta el flujo GSP completo, persiste resultados |
| **Default** | `default` | — | Health checks y utilidades |

### 3.3 Modelo de Ejecución

- Cada worker usa **pool=solo** (un proceso, sin fork) para evitar conflictos con Playwright
- Cada tarea crea su propio contexto de navegador (nunca se comparte entre tareas)
- `max-tasks-per-child=10`: el worker se recicla cada 10 tareas para liberar memoria
- `task_acks_late=True`: la tarea se confirma solo al completarse (si el worker muere, se re-encola)
- `worker_prefetch_multiplier=1`: solo una tarea a la vez en buffer

---

## 4. Modelo de Datos

### 4.1 Entidades Principales

#### Batch (lote de pedidos)

| Campo | Tipo | Descripción |
|-------|------|------------|
| `id` | int (PK) | Identificador único |
| `name` | str(255) | Nombre del batch (ej. "Día de las Madres 2026") |
| `description` | text | Descripción opcional |
| `status` | Enum | `PENDING → RUNNING → COMPLETED/FAILED/CANCELLED` |
| `total_orders` | int | Total de pedidos para cálculo de ETA |
| `completed_orders` | int | Contador de pedidos completados |
| `failed_orders` | int | Contador de pedidos fallidos |
| `source_file` | str(500) | Ruta del CSV/Excel original |
| `started_at` | datetime | Inicio de procesamiento |
| `finished_at` | datetime | Fin de procesamiento |

#### Order (pedido individual)

| Campo | Tipo | Descripción |
|-------|------|------------|
| `id` | int (PK) | Identificador único |
| `batch_id` | int (FK) | Batch al que pertenece |
| `consultora_code` | str(50) | Código de la consultora (CB) |
| `consultora_name` | str(255) | Nombre de la consultora |
| `status` | Enum | Estado granular (ver abajo) |
| `current_step` | str | Paso actual para Flower |
| `retry_count` | int | Intentos actuales |
| `max_retries` | int | Máximo de reintentos (default: 3) |
| `celery_task_id` | str | ID de tarea Celery (para revoke) |
| `worker_id` | str | Worker que lo está procesando |
| `error_message` | text | Mensaje de error (si falló) |
| `error_step` | str | En qué paso falló |
| `screenshot_path` | str | Captura de pantalla del error |
| `duration_seconds` | float | Duración total |

**Estados de Order:**
```
PENDING → QUEUED → IN_PROGRESS → LOGIN_OK → CONSULTORA_SELECTED
→ CYCLE_SELECTED → CART_OPEN → PRODUCTS_ADDED → COMPLETED
                                                 ↓ (si falla)
                                              RETRYING → (vuelve a IN_PROGRESS)
                                                 ↓ (max retries)
                                              FAILED
                                              CANCELLED
```

#### OrderProduct (producto dentro de un pedido)

| Campo | Tipo | Descripción |
|-------|------|------------|
| `id` | int (PK) | Identificador único |
| `order_id` | int (FK) | Pedido al que pertenece |
| `product_code` | str(50) | Código del producto |
| `product_name` | str(255) | Nombre (scrapeado del carrito) |
| `quantity` | int | Cantidad solicitada |
| `status` | Enum | `PENDING / ADDED / FAILED / NOT_FOUND / OUT_OF_STOCK` |
| `error_message` | text | Detalle del error |

#### OrderLog (auditoría paso a paso)

| Campo | Tipo | Descripción |
|-------|------|------------|
| `id` | int (PK) | Identificador único |
| `order_id` | int (FK) | Pedido asociado |
| `level` | str | `INFO / WARNING / ERROR / DEBUG` |
| `step` | str | Paso del flujo (ej. "login", "add_product") |
| `message` | text | Mensaje descriptivo |
| `details` | JSON | Datos estructurados adicionales |
| `screenshot_path` | str | Captura de pantalla opcional |
| `timestamp` | datetime | Momento exacto |

---

## 5. API REST (Master)

La API corre en FastAPI (puerto 8000) con documentación Swagger en `/docs`.

### 5.1 Health & Stats

| Método | Endpoint | Descripción |
|--------|----------|------------|
| GET | `/health` | Health check (`{"status": "ok"}`) |
| GET | `/stats` | Estadísticas del sistema (workers activos, pedidos pendientes, etc.) |

### 5.2 Gestión de Batches

| Método | Endpoint | Descripción |
|--------|----------|------------|
| POST | `/batches/upload` | Subir CSV/Excel → crear batch con pedidos |
| POST | `/batches` | Crear batch desde JSON |
| GET | `/batches` | Listar todos los batches |
| GET | `/batches/{id}` | Detalle de un batch (incluye lista de orders) |
| GET | `/batches/{id}/stats` | Estadísticas: progreso %, ETA, desglose por estado |

### 5.3 Acciones sobre Batches

| Método | Endpoint | Descripción |
|--------|----------|------------|
| POST | `/batches/{id}/start` | Iniciar procesamiento (despacha pedidos a workers) |
| POST | `/batches/{id}/pause` | Pausar (revoca tareas pendientes) |
| POST | `/batches/{id}/cancel` | Cancelar todo el batch |
| POST | `/batches/{id}/retry` | Reintentar todos los pedidos fallidos |
| POST | `/batches/{id}/reprocess-missing` | Re-procesar pedidos con productos sin stock o no encontrados |

### 5.4 Órdenes

| Método | Endpoint | Descripción |
|--------|----------|------------|
| GET | `/orders/{id}` | Detalle de un pedido (incluye productos) |
| GET | `/orders/{id}/logs` | Trail de auditoría completo paso a paso |

### 5.5 Emails

| Método | Endpoint | Descripción |
|--------|----------|------------|
| POST | `/batches/{id}/send-emails` | Enviar notificaciones a consultoras, líderes y gerentes |
| POST | `/emails/consultora/upload` | Enviar email "Completo" a consultoras desde CSV |
| POST | `/test-email` | Email de prueba (consultora) |
| POST | `/test-email/lider` | Email de prueba (líder) |
| POST | `/test-email/gerente` | Email de prueba (gerente) |

---

## 6. Orquestación de Batches

### 6.1 Carga de Datos (`master/loader.py`)

```
CSV/Excel → Parse → Normalizar columnas → Agrupar por consultora_code → Crear Batch + Orders + OrderProducts
```

**Columnas requeridas en el CSV:**
- `consultora_code` — Código CB de la consultora
- `consultora_name` — Nombre de la consultora
- `product_code` — Código del producto
- `quantity` — Cantidad

Las filas se agrupan por `consultora_code`: múltiples productos para la misma consultora se consolidan en un solo `Order` con varios `OrderProduct`.

### 6.2 Ciclo de Vida del Batch (`master/orchestrator.py`)

La clase `Orchestrator` gestiona todo el ciclo de vida:

- **`start_batch(id)`** → Cambia estado a RUNNING, publica `process_batch(id)` en cola `batches`
- **`pause_batch(id)`** → Cambia estado a PAUSED, revoca tareas pendientes en Celery, resetea orders a PENDING
- **`cancel_batch(id)`** → Cambia estado a CANCELLED, revoca todas las tareas con `terminate=True`, marca orders como CANCELLED
- **`retry_batch_failures(id)`** → Encola `retry_failed_orders(id)` que busca orders FAILED y los re-despacha
- **`reprocess_orders_with_missing_products(id)`** → Busca orders con productos OUT_OF_STOCK o NOT_FOUND y los re-encola
- **`get_batch_stats(id)`** → Calcula progreso %, ETA basado en duración promedio, desglose por estado

---

## 7. Procesamiento Distribuido (Celery)

### 7.1 Configuración (`worker/celery_app.py`)

| Parámetro | Valor | Propósito |
|-----------|-------|----------|
| `task_serializer` | json | Serialización de tareas |
| `timezone` | America/Santiago | Zona horaria Chile |
| `worker_prefetch_multiplier` | 1 | Una tarea a la vez en buffer |
| `task_acks_late` | True | ACK después de completar (no al recibir) |
| `task_reject_on_worker_lost` | True | Re-encolar si worker muere |
| `task_default_rate_limit` | 10/m | Máximo 10 tareas/min por worker |
| `result_expires` | 86400 | Resultados expiran en 24h |

### 7.2 Tareas Definidas (`worker/tasks.py`)

#### `process_order(order_id)` — Tarea principal

- **Queue:** `orders`
- **Time limit:** 600s (hard kill 10 min), 540s (soft limit 9 min)
- **Max retries:** 3 con backoff exponencial
- **Flujo:**
  1. Cargar order + products de la BD
  2. Instanciar `GSPBot` con Playwright
  3. Ejecutar flujo completo: login → buscar consultora → ciclo → carrito → productos
  4. Persistir resultados (estado de productos, logs, screenshots)
  5. Actualizar contadores del batch
  6. En caso de error transitorio: reintentar con delay
  7. En caso de error permanente: marcar como FAILED

#### `process_batch(batch_id)` — Dispatcher

- **Queue:** `batches`
- **Time limit:** 3600s (1 hora)
- **Flujo:** Lee todos los orders PENDING/RETRYING → Para cada uno publica `process_order(order_id)` en cola `orders`

#### `cleanup_stuck_orders()` — Tarea periódica

- **Frecuencia:** Cada 5 minutos (Celery Beat)
- **Acción:** Detecta orders en IN_PROGRESS por más de 15 minutos y los resetea a RETRYING o FAILED

#### `retry_failed_orders(batch_id)` — Reintento masivo

- Busca todos los orders FAILED en el batch y los re-encola

#### `health_check()` — Verificación de salud

- Retorna `{"status": "ok"}` para confirmar que el worker está vivo

---

## 8. Automatización del Navegador (Playwright)

### 8.1 Clase `GSPBot` (`worker/gsp_bot.py`)

Bot stateful que ejecuta todo el flujo de carga de pedido en el portal GSP usando Playwright (Chromium headless).

**Características del navegador:**
- Anti-detección: oculta flag `navigator.webdriver`, spoofea User-Agent y headers `sec-ch-ua`
- Proxy corporativo: detecta y usa `HTTPS_PROXY` / `HTTP_PROXY` del entorno
- Viewport: 1366×768, locale `es-CL`, timezone `America/Santiago`
- Contexto aislado: cada tarea crea su propio browser context (nunca se comparte)

### 8.2 Flujo de Automatización (9 pasos)

#### Paso 0: Preflight (verificación de red)

Antes de abrir el navegador, verifica conectividad desde el contenedor:
1. **DNS** — Resuelve el hostname del portal GSP
2. **TCP** — Conexión al puerto 443
3. **HTTP** — Request HEAD al portal (respeta proxy)
4. Si falla → lanza `LoginError` sin gastar recursos de Playwright

#### Paso 1: Login

- Navega a la URL de login de GSP (3 intentos con retry)
- Selecciona tipo de autenticación "Código" en el combobox
- Ingresa código de supervisor + contraseña
- Hace clic en botón "ACCESO"
- Espera a que aparezca la opción "Para otra Consultora" (confirmación de login exitoso)

#### Paso 2: Seleccionar "Para otra Consultora"

- Hace clic en el radio button de impersonación (`otherCn`)
- Acepta el diálogo de impersonación
- Espera a que aparezca el campo de búsqueda de consultora

#### Paso 3: Buscar Consultora

- Ingresa el código de consultora en el campo `#naturaCode`
- Hace clic en "Buscar"

#### Paso 4: Confirmar Consultora

- Hace clic en el botón "Confirmar" para seleccionar a la consultora encontrada

#### Paso 5: Seleccionar Ciclo

- Espera a que aparezcan las opciones de ciclo
- Selecciona el primer ciclo disponible (radio button)
- Hace clic en "Aceptar"

#### Paso 6: Abrir Carrito

- Espera a que cargue la grilla de productos
- Hace clic en el ícono de bolsa de compras
- Valida que el carrito se abrió (verifica campo de quick-order)

#### Paso 6b: Limpiar Carrito

- Si hay productos previos en el carrito, los registra en el log de auditoría
- Hace clic en "Vaciar carrito" para eliminar todo
- Registra cuántos items se removieron

#### Paso 7: Agregar Productos (Bulk Upload)

- Genera un archivo Excel temporal (`.xlsx`) con columnas `CÓDIGO` y `QTDE`
- Hace clic en el botón de importación del portal
- Sube el archivo Excel via `input[type="file"]`
- Espera confirmación "¡Archivo cargado con éxito!"

#### Paso 8: Navegación Adaptativa al Carrito

Maneja múltiples diálogos modales que pueden aparecer:
- **Selección de ciclo** — Si reaparece, selecciona el primer ciclo
- **Venta Directa** — Checkbox `label[for="id_1"]` + botón "Aceptar"
- **Botón "LISTO"** — Lo presiona si aparece
- **"Eliminar Pedido"** — Si hay un pedido guardado previo, lo elimina
- **Ícono de carrito** — Click para navegar al carrito

Máximo 10 intentos con esperas de 2.5s entre cada uno.

#### Paso 9: Verificar Contenido del Carrito

- Parsea el DOM del carrito para extraer productos cargados
- Clasifica cada producto como: `ADDED`, `OUT_OF_STOCK`, `FAILED`, `NOT_FOUND`
- Retorna resumen: productos agregados, productos fallidos, si hay sin stock

### 8.3 Resultado de `execute_order()`

```python
{
    "success": True/False,
    "consultora_code": "12345",
    "products_added": [{"product_code": "237617", "name": "...", "quantity": 2}],
    "products_failed": [{"product_code": "999999", "error": "out_of_stock"}],
    "has_out_of_stock": True/False,
    "duration_seconds": 45.2,
    "step_log": [{"step": "login", "message": "Login successful ✓", ...}],
    "error": "...",           # solo si success=False
    "error_step": "...",      # solo si success=False
    "screenshot": "...",      # solo si success=False
}
```

---

## 9. Sistema de Notificaciones por Email

### 9.1 Integración Gmail (`shared/email/gmail_sender.py`)

- Autenticación via **OAuth2** (token almacenado en JSON)
- Token se refresca automáticamente si expira
- Envío via **Gmail API** (no SMTP directo)
- Soporta destinatarios múltiples y CC

### 9.2 Templates HTML (`shared/email/templates.py`)

Tres niveles de notificación con templates HTML diseñados:

#### Email a Consultora (individual)

| Variante | Asunto | Contenido |
|----------|--------|-----------|
| **Completo** | 🎁 ¡Tu carrito del Live Shopping está listo! | Tabla de productos con ✓, botón "Ver carrito" |
| **Parcialmente Completo** | ⚠️ Tu carrito se cargó parcialmente | Tabla con productos ✓ y ❌ sin stock |
| **Fallido** | ❌ Hubo un problema al cargar tu carrito | Mensaje de error, instrucciones de contacto |

#### Email a Líder (agregado por sector)

- Tabla con consultoras de su sector: código, nombre, estado (Completo/Parcial)
- KPIs: total completos, total parciales, tasa de éxito

#### Email a Gerente (agregado por gerencia)

- Tabla con líderes: nombre, sector, completos, parciales
- KPIs: total consultoras, tasa de éxito gerencial

### 9.3 Orquestación de Envío (`shared/email/send_emails.py`)

El endpoint `/batches/{id}/send-emails` ejecuta:

1. **Carga `consultoras_matriz.csv`** — Mapeo CB → email, nombre, líder, sector, gerente, gerencia
2. **Nivel 1 (Consultoras):** Por cada order completado/parcial, busca el email en la matriz y envía
3. **Nivel 2 (Líderes):** Agrupa consultoras por sector, suma completos/parciales, envía resumen al líder
4. **Nivel 3 (Gerentes):** Agrupa líderes por gerencia, envía resumen ejecutivo al gerente

Retorna conteo de enviados/errores por cada nivel.

---

## 10. Herramientas Administrativas

### 10.1 CLI (`cli.py`)

```bash
# Cargar CSV y crear batch
python -m cli load data/sample_orders.csv --name "Día de las Madres 2026"

# Iniciar procesamiento
python -m cli start 1

# Ver estado del batch
python -m cli status 1

# Reintentar pedidos fallidos
python -m cli retry 1

# Reintentar un pedido específico
python -m cli retry-order 42

# Pausar batch
python -m cli pause 1

# Cancelar batch
python -m cli cancel 1
```

### 10.2 Utilidad de Corrección Manual (`tools/mark_order_products_added.py`)

```bash
# Marcar todos los productos de un order como ADDED y completar el order
python -m tools.mark_order_products_added --order 494 --complete

# Marcar productos específicos (dry-run para ver cambios sin aplicar)
python -m tools.mark_order_products_added --order 494 --codes 237617 244486 --dry-run
```

### 10.3 Ejemplo de Uso (`ejemplo.py`)

Script de ejemplo para ejecutar un pedido individual de forma programática.

---

## 11. Despliegue e Infraestructura

### 11.1 Docker Compose (`docker-compose.yml`)

| Servicio | Imagen | Puerto | Propósito |
|----------|--------|--------|-----------|
| **postgres** | postgres:16-alpine | 5432 | Base de datos de estado y auditoría |
| **redis** | redis:7-alpine | 6379 | Broker de tareas Celery + cache |
| **master** | Dockerfile.master | 8000 | API FastAPI (Swagger en /docs) |
| **dispatcher** | Dockerfile.dispatcher | — | Worker Celery para cola `batches` (concurrency=1) |
| **worker-1..N** | Dockerfile.worker | — | Workers Celery para cola `orders` (Playwright) |
| **flower** | mher/flower | 5555 | Dashboard de monitoreo Celery |

**Escalado horizontal:**
```bash
docker-compose up --scale worker=5  # 5 workers en paralelo
```

**Recursos por worker:**
- Memoria: 4GB límite, 2GB shared memory (para Chromium)
- CPU: 2 cores

### 11.2 Dockerfiles

#### Dockerfile.master
- Python 3.11 + FastAPI + uvicorn
- Expone puerto 8000

#### Dockerfile.worker
- Python 3.11 + Celery + Playwright
- Instala dependencias de sistema para Chromium
- Pre-instala Chromium: `playwright install chromium`
- Pool: `solo` (sin fork)
- Recicla cada 10 tareas: `--max-tasks-per-child=10`

#### Dockerfile.dispatcher
- Python 3.11 + Celery
- Solo procesa cola `batches` con concurrency=1
- No necesita Playwright

### 11.3 CI/CD (GitHub Actions)

**Triggers:** Push a main, workflow_dispatch manual

**Pipeline:**
1. Checkout código
2. Detectar configuración de proxy del runner
3. Crear `.env` desde GitHub Secrets
4. Build imágenes Docker (`docker-compose build`)
5. Deploy a servidor remoto via SSH (si `DEPLOY_HOST` está configurado)

**Secrets requeridos:**

| Secret | Descripción |
|--------|------------|
| `GSP_USER_CODE` | Código de supervisor para login en GSP |
| `GSP_PASSWORD` | Contraseña de supervisor |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL |
| `REDIS_PASSWORD` | Contraseña de Redis |
| `GMAIL_TOKEN_JSON` | Token OAuth2 para Gmail (JSON en una línea) |
| `DEPLOY_HOST` | (Opcional) Hostname SSH para deploy remoto |
| `DEPLOY_USER` | (Opcional) Usuario SSH |
| `DEPLOY_SSH_KEY` | (Opcional) Clave privada SSH |

### 11.4 Configuración (`config/settings.py`)

Usa **Pydantic Settings** con override por variables de entorno:

| Categoría | Variables | Defaults |
|-----------|----------|----------|
| **General** | `APP_ENV`, `LOG_LEVEL` | production, INFO |
| **Redis** | `REDIS_HOST`, `REDIS_PORT`, `REDIS_PASSWORD` | localhost, 6379 |
| **PostgreSQL** | `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | localhost, 5432, gsp, -, gsp_bot |
| **Celery** | `CELERY_CONCURRENCY`, `CELERY_MAX_RETRIES`, `CELERY_RETRY_DELAY` | 3, 3, 30s |
| **GSP** | `GSP_USER_CODE`, `GSP_PASSWORD`, `GSP_LOGIN_URL` | — (requeridos) |
| **Playwright** | `PLAYWRIGHT_HEADLESS`, `PLAYWRIGHT_TIMEOUT`, `PLAYWRIGHT_SLOW_MO` | True, 60000ms, 100ms |
| **Screenshots** | `SCREENSHOT_ON_ERROR`, `SCREENSHOT_DIR` | True, screenshots/ |

Secretos se obtienen vía `Vault.get_secret()` de `core_shared` (con fallback a `os.getenv()`).

---

## 12. Manejo de Errores y Reintentos

### 12.1 Jerarquía de Excepciones (`shared/exceptions.py`)

```
GSPBotError (base)
├── LoginError              → Fallo en autenticación
├── ConsultoraSearchError   → No se encontró la consultora
├── CycleSelectionError     → Fallo en selección de ciclo
├── CartError               → Error en operaciones del carrito
├── ProductAddError         → Error al agregar producto individual
├── NavigationError         → Timeout en navegación de página
├── SessionExpiredError     → Sesión expirada durante el flujo
└── OutOfStockError         → Producto sin stock
```

### 12.2 Estrategia de Reintentos

| Nivel | Mecanismo | Configuración |
|-------|-----------|---------------|
| **Tarea Celery** | `self.retry()` con countdown | 3 reintentos, delay = 30s × retry_count |
| **Pedido (Order)** | Campo `retry_count` / `max_retries` | Máximo 3 intentos, backoff exponencial |
| **Batch** | Endpoints manuales | `/retry` re-encola FAILED, `/reprocess-missing` re-encola OUT_OF_STOCK |

**Errores transitorios** (se reintentan): timeout de red, sesión expirada, error de navegación.  
**Errores permanentes** (no se reintentan): producto sin stock, producto no encontrado.

### 12.3 Protecciones

- **Preflight check:** Verifica DNS + TCP + HTTP antes de abrir Playwright
- **Cleanup periódico:** Tarea cada 5 min detecta orders "stuck" (>15 min en IN_PROGRESS)
- **Screenshots on error:** Captura automática del estado del navegador al fallar
- **Timeout guard:** `signal.alarm(30)` para evitar que `sync_playwright()` cuelgue indefinidamente

---

## 13. Logging y Monitoreo

### 13.1 Logging Estructurado

- Framework: **structlog** con integración stdlib
- Formato: JSON en producción, consola coloreada en desarrollo
- Cada entrada incluye: timestamp, level, logger, message, + campos contextuales (order_id, worker_id, consultora)

### 13.2 Monitoreo

| Herramienta | URL | Propósito |
|-------------|-----|-----------|
| **Flower** | http://localhost:5555 | Dashboard Celery: tareas en tiempo real, estado de workers, historial |
| **FastAPI Swagger** | http://localhost:8000/docs | Documentación interactiva de la API, prueba de endpoints |
| **`/stats`** | http://localhost:8000/stats | Workers activos, batches activos, conteo de orders por estado |
| **`/orders/{id}/logs`** | API | Audit trail paso a paso de cada pedido |

### 13.3 Healthchecks

- **PostgreSQL:** `pg_isready`
- **Redis:** `redis-cli ping`
- **Master API:** `GET /health`
- **Workers:** `health_check()` task vía Celery

---

## 14. Flujo Completo de Ejecución

```
                         ┌────────────────────┐
                         │   CSV con pedidos   │
                         │  (consultora +      │
                         │   productos + qty)  │
                         └─────────┬──────────┘
                                   │
                                   ▼
                      POST /batches/upload
                                   │
                                   ▼
                ┌──────────────────────────────────┐
                │  Parse CSV → Agrupar por CB →    │
                │  Crear Batch + Orders + Products  │
                │  → Guardar en PostgreSQL          │
                └─────────────────┬────────────────┘
                                  │
                                  ▼
                      POST /batches/{id}/start
                                  │
                                  ▼
          ┌───────────────────────────────────────────┐
          │  Batch.status = RUNNING                    │
          │  Publica process_batch(id) → cola "batches"│
          └────────────────────┬──────────────────────┘
                               │
                               ▼
          ┌───────────────────────────────────────────┐
          │            DISPATCHER                      │
          │  Lee orders PENDING/RETRYING               │
          │  Para cada order:                          │
          │    order.status = QUEUED                   │
          │    Publica process_order(id) → "orders"    │
          └────────────────────┬──────────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌──────────┐┌──────────┐┌──────────┐
              │ Worker 1 ││ Worker 2 ││ Worker N │
              │          ││          ││          │
              │ Playwright││Playwright││Playwright│
              │ Login    ││ Login    ││ Login    │
              │ Buscar CB││ Buscar CB││ Buscar CB│
              │ Ciclo    ││ Ciclo    ││ Ciclo    │
              │ Carrito  ││ Carrito  ││ Carrito  │
              │ Productos││ Productos││ Productos│
              │ Verificar││ Verificar││ Verificar│
              └─────┬────┘└─────┬────┘└─────┬────┘
                    │          │          │
                    └──────────┼──────────┘
                               │
                               ▼
          ┌───────────────────────────────────────────┐
          │  Actualizar OrderProduct.status             │
          │  Actualizar Order.status = COMPLETED/FAILED │
          │  Actualizar Batch contadores                │
          │  Registrar logs de auditoría                │
          └────────────────────┬──────────────────────┘
                               │
                               ▼
                 GET /batches/{id}/stats
                    Progreso %, ETA
                               │
                               ▼
               POST /batches/{id}/send-emails
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
              ┌──────────┐┌──────────┐┌──────────┐
              │Consultora││  Líder   ││ Gerente  │
              │ (indiv.) ││ (sector) ││(gerencia)│
              │ 🎁/⚠️/❌  ││ Resumen  ││ Ejecutivo│
              └──────────┘└──────────┘└──────────┘
```

---

## 15. Referencia de Archivos

| Archivo | Propósito |
|---------|-----------|
| `config/settings.py` | Configuración centralizada (Pydantic Settings) |
| `shared/models.py` | Modelos SQLAlchemy: Batch, Order, OrderProduct, OrderLog |
| `shared/schemas.py` | Schemas Pydantic para la API: BatchOut, OrderOut, BatchStats |
| `shared/database.py` | Engine PostgreSQL, session factory, `init_db()` |
| `shared/exceptions.py` | Jerarquía de excepciones custom |
| `shared/logging_config.py` | Setup de structlog (JSON/consola) |
| `shared/email/gmail_sender.py` | Envío de emails via Gmail OAuth2 API |
| `shared/email/templates.py` | Templates HTML (consultora, líder, gerente) |
| `shared/email/send_emails.py` | Orquestación de envío por niveles |
| `master/api.py` | Endpoints FastAPI (upload, start, pause, retry, emails) |
| `master/orchestrator.py` | Lógica de ciclo de vida de batches |
| `master/loader.py` | Parser de CSV/Excel → Batch + Orders |
| `worker/celery_app.py` | Configuración Celery (queues, rates, signals) |
| `worker/tasks.py` | Definición de tareas: process_order, process_batch, cleanup |
| `worker/gsp_bot.py` | Bot Playwright: flujo completo de automatización GSP |
| `cli.py` | Interfaz de línea de comandos |
| `ejemplo.py` | Script de ejemplo de uso |
| `docker-compose.yml` | Orquestación de todos los servicios |
| `Dockerfile.master` | Imagen Docker para la API |
| `Dockerfile.worker` | Imagen Docker para workers (con Playwright) |
| `Dockerfile.dispatcher` | Imagen Docker para el dispatcher |
| `requirements.txt` | Dependencias Python del proyecto |
| `data/consultoras_matriz.csv` | Matriz de consultoras → emails, líderes, gerentes |
| `data/sample_orders.csv` | Archivo de ejemplo para carga de pedidos |
| `tools/mark_order_products_added.py` | Utilidad para corrección manual de estados |
| `README.md` | Documentación original del proyecto |
| `CASO_USO_CONSULTORA.md` | Caso de uso detallado de consultora |

---

*Documento generado el 10 de marzo de 2026.*
