# GSP Bot v5 — Sistema de Carga Masiva de Pedidos Natura

Sistema industrial de automatización para cargar pedidos de consultoras en la plataforma GSP de Natura Chile, diseñado para el **Día de las Madres** y otras campañas masivas.

## Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                    Docker Compose                            │
│                                                              │
│  ┌──────────┐   ┌───────────┐   ┌─────────────────────────┐│
│  │ PostgreSQL│   │   Redis   │   │    Flower Dashboard     ││
│  │  (State)  │   │  (Broker) │   │    :5555                ││
│  └─────┬─────┘   └─────┬─────┘   └─────────────────────────┘│
│        │               │                                     │
│  ┌─────┴───────────────┴───────────────────┐                │
│  │         Master API (FastAPI :8000)       │                │
│  │  - Control: start/pause/cancel/retry    │                │
│  │  - Upload CSV/Excel                      │                │
│  │  - Monitoring & Stats                    │                │
│  │  - Audit Logs                            │                │
│  └─────────────────┬───────────────────────┘                │
│                    │ Celery Tasks                            │
│          ┌─────────┼─────────┐                              │
│   ┌──────┴──┐  ┌───┴────┐  ┌┴───────┐                      │
│   │Worker 1 │  │Worker 2│  │Worker 3│  ← Escalable          │
│   │Playwright│  │Playwright│ │Playwright│                     │
│   └─────────┘  └────────┘  └────────┘                      │
└─────────────────────────────────────────────────────────────┘
```

## Stack Tecnológico

| Componente | Tecnología | Propósito |
|---|---|---|
| Automatización | **Playwright** | Control del navegador Chromium |
| Cola de tareas | **Celery + Redis** | Distribución paralela con reintentos |
| Base de datos | **PostgreSQL** | Estado persistente, auditoría |
| API de control | **FastAPI** | REST API para monitoreo/control |
| Dashboard | **Flower** | Monitor visual de workers Celery |
| Logging | **structlog** | Logs estructurados JSON |
| Contenedores | **Docker + Compose** | Orquestación de servicios |

## Inicio Rápido

### 1. Configurar credenciales

```bash
cp .env.example .env
# Editar .env con las credenciales reales:
#   GSP_USER_CODE=tu_codigo_supervisor
#   GSP_PASSWORD=tu_password
#   POSTGRES_PASSWORD=password_seguro
```

### 2. Levantar todo con Docker

```bash
# Construir y levantar todos los servicios
docker-compose up -d --build

# Verificar que todo está corriendo
docker-compose ps

# Ver logs en tiempo real
docker-compose logs -f worker-1
```

### 3. Escalar workers según necesidad

```bash
# Agregar más workers (ej: 5 workers paralelos)
docker-compose up -d --scale worker-1=5
```

## Uso

### Opción A: Via API (recomendado para producción)

```bash
# Subir CSV con pedidos
curl -X POST http://localhost:8000/batches/upload \
  -F "file=@data/sample_orders.csv" \
  -F "name=Dia de las Madres 2026"

# Iniciar el procesamiento
curl -X POST http://localhost:8000/batches/1/start

# Ver progreso
curl http://localhost:8000/batches/1/stats

# Ver órdenes fallidas
curl http://localhost:8000/batches/1/orders?status=failed

# Ver log detallado de una orden
curl http://localhost:8000/orders/42/logs

# Reintentar las fallidas
curl -X POST http://localhost:8000/batches/1/retry

# Reintentar una orden específica
curl -X POST http://localhost:8000/orders/42/retry

# Pausar un batch
curl -X POST http://localhost:8000/batches/1/pause

# Cancelar un batch
curl -X POST http://localhost:8000/batches/1/cancel
```

### Opción B: Via CLI

```bash
# Cargar CSV
python -m cli load data/sample_orders.csv --name "Dia de las Madres 2026"

# Iniciar procesamiento
python -m cli start 1

# Ver estado
python -m cli status 1

# Reintentar fallidas
python -m cli retry 1

# Pausar
python -m cli pause 1
```

### Opción C: Via JSON directo

```bash
curl -X POST http://localhost:8000/batches \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pedido urgente",
    "orders": [
      {
        "consultora_code": "12345678",
        "consultora_name": "María González",
        "products": [
          {"product_code": "80901", "quantity": 2},
          {"product_code": "81502", "quantity": 1}
        ]
      }
    ]
  }'
```

## Formato del CSV

```csv
consultora_code,consultora_name,product_code,quantity
12345678,María González,80901,2
12345678,María González,81502,1
98765432,Ana López,80901,1
```

- **consultora_code** (obligatorio): Código de la consultora
- **consultora_name** (opcional): Nombre de la consultora
- **product_code** (obligatorio): Código del producto
- **quantity** (obligatorio): Cantidad

Múltiples filas con el mismo `consultora_code` se agrupan automáticamente en una sola orden.

## Monitoreo

### Dashboards

- **API FastAPI**: http://localhost:8000/docs (Swagger UI interactivo)
- **Flower Celery**: http://localhost:5555 (user: admin, pass: changeme)

### Endpoints principales

| Endpoint | Descripción |
|---|---|
| `GET /health` | Health check |
| `GET /stats` | Estadísticas globales del sistema |
| `GET /batches` | Lista todos los batches |
| `GET /batches/{id}/stats` | Progreso detallado de un batch |
| `GET /batches/{id}/orders?status=failed` | Órdenes filtradas por estado |
| `GET /orders/{id}` | Detalle de una orden con productos |
| `GET /orders/{id}/logs` | Audit trail completo paso a paso |

## Estados del Flujo

### Orden (Order)

```
pending → queued → in_progress → login_ok → consultora_selected 
    → cycle_selected → cart_open → products_added → completed
                                                  ↓
                                              failed → retrying → (reinicia)
```

### Batch

```
pending → running → completed
                  → failed (si hay órdenes fallidas)
         → paused → running (al reanudar)
         → cancelled
```

## Manejo de Errores

El sistema implementa múltiples capas de resiliencia:

1. **Reintentos automáticos**: Cada orden se reintenta hasta 3 veces (configurable)
2. **Screenshots en error**: Se captura una imagen de la pantalla al fallar
3. **Audit trail completo**: Cada paso queda registrado en `order_logs`
4. **Reintento manual**: Via API o CLI, se puede reintentar órdenes específicas
5. **Worker crash recovery**: Si un worker muere, la tarea se re-encola (`acks_late=True`)
6. **Max tasks per child**: Los workers se reciclan cada 10 tareas para evitar memory leaks

### Diagnóstico de fallos

```bash
# 1. Ver qué órdenes fallaron
curl http://localhost:8000/batches/1/orders?status=failed

# 2. Ver el log paso a paso de la orden fallida
curl http://localhost:8000/orders/42/logs

# 3. Ver el screenshot del error (si existe)
curl http://localhost:8000/screenshots/error_login_42_20260213_143522.png

# 4. Reintentar la orden
curl -X POST http://localhost:8000/orders/42/retry
```

## Configuración Avanzada

### Variables de entorno críticas

| Variable | Default | Descripción |
|---|---|---|
| `CELERY_CONCURRENCY` | 3 | Browsers simultáneos por worker |
| `CELERY_MAX_RETRIES` | 3 | Reintentos antes de marcar como fallido |
| `PLAYWRIGHT_HEADLESS` | true | false para debug visual |
| `PLAYWRIGHT_TIMEOUT` | 60000 | Timeout general de Playwright (ms) |
| `PLAYWRIGHT_SLOW_MO` | 100 | Delay entre acciones (ms) |

### Para debug local (sin Docker)

```bash
# Terminal 1: Redis
docker run -d -p 6379:6379 redis:7-alpine

# Terminal 2: PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_DB=gsp_bot -e POSTGRES_USER=gsp -e POSTGRES_PASSWORD=dev postgres:16-alpine

# Terminal 3: Worker
celery -A worker.celery_app:app worker --loglevel=info --queues=orders,default --concurrency=1

# Terminal 4: Dispatcher
celery -A worker.celery_app:app worker --loglevel=info --queues=batches --concurrency=1

# Terminal 5: API
uvicorn master.api:app --reload --port 8000

# Terminal 6: Flower
celery -A worker.celery_app:app flower --port=5555
```

## Estructura del Proyecto

```
gsp_v5/
├── docker-compose.yml          # Orquestación de servicios
├── Dockerfile.master            # API FastAPI
├── Dockerfile.worker            # Workers con Playwright
├── Dockerfile.dispatcher        # Dispatcher de batches
├── requirements.txt
├── .env.example
├── cli.py                       # CLI para uso rápido
│
├── config/
│   └── settings.py              # Configuración centralizada
│
├── shared/
│   ├── models.py                # Modelos SQLAlchemy (Batch, Order, Product, Log)
│   ├── schemas.py               # Schemas Pydantic (API request/response)
│   ├── database.py              # Engine y sesiones de DB
│   ├── logging_config.py        # Logging estructurado
│   └── exceptions.py            # Excepciones custom por paso
│
├── master/
│   ├── api.py                   # FastAPI endpoints
│   ├── orchestrator.py          # Lógica de control de batches
│   └── loader.py                # Carga de CSV/Excel
│
├── worker/
│   ├── celery_app.py            # Configuración de Celery
│   ├── tasks.py                 # Tareas Celery (process_order, process_batch)
│   └── gsp_bot.py               # Playwright automation (el bot)
│
└── data/
    └── sample_orders.csv        # Ejemplo de CSV
```
