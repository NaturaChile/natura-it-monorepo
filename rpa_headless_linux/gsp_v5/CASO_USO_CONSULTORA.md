# Caso de Uso: Consultora María — Carrito Parcialmente Completo

> Documento que explica el flujo end-to-end del sistema GSP Bot v5,
> desde la carga de un CSV hasta la notificación por correo,
> usando un caso real simulado.

---

## 📋 Escenario

**Consultora:** María Heroina Saez Rosas  
**CB (código):** 958  
**Email:** gokupardo123@gmail.com  
**Líder:** Camila Andrea Silva Muñoz — camilasilvamunoz9@gmail.com  
**Sector:** Amancay  
**Gerente (GN):** Karina Alejandra Yermani Zuñiga — karinayermani@natura.net  
**Gerencia:** Gerencia Araucaria  
**Evento:** Preventa del Día de las Madres  

### Productos solicitados

| # | Código | Producto | Stock |
|---|--------|----------|-------|
| 1 | 88934 | Luna Absoluta Perfume de Mujer | ✅ Disponible |
| 2 | 76543 | Tododia Crema Corporal Frambuesa | ❌ Sin stock |

**Resultado esperado:** Carrito **parcialmente completo** — 1 producto cargado, 1 fallido.

---

## 🏗️ Arquitectura del Sistema

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Docker Compose Stack                          │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ PostgreSQL│  │  Redis   │  │  Flower  │  │  Master  │            │
│  │  :5432    │  │  :6379   │  │  :5555   │  │  :8000   │            │
│  │  BD       │  │  Cola    │  │  Monitor │  │  API     │            │
│  └────┬─────┘  └────┬─────┘  └──────────┘  └────┬─────┘            │
│       │              │                            │                  │
│       │         ┌────┴────────────────────────────┘                  │
│       │         │                                                    │
│  ┌────┴─────────┴─────┐  ┌─────────────┐  ┌─────────────┐          │
│  │    Dispatcher      │  │  Worker-1   │  │  Worker-2   │          │
│  │    (Orquestador)   │  │ (Playwright)│  │ (Playwright)│  ...     │
│  └────────────────────┘  └─────────────┘  └─────────────┘          │
└──────────────────────────────────────────────────────────────────────┘
```

### ¿Qué hace cada servicio?

| Servicio | Puerto | Función |
|----------|--------|---------|
| **PostgreSQL** | 5432 | Base de datos. Guarda batches, órdenes, productos y logs de auditoría |
| **Redis** | 6379 | Broker de mensajes para Celery. Enqueue de tareas y almacenamiento de resultados |
| **Master (FastAPI)** | 8000 | API REST. Recibe el CSV, crea el batch, expone endpoints de control y monitoreo |
| **Dispatcher (Celery)** | — | Toma un batch y lo divide en tareas individuales por orden. Orquesta el flujo |
| **Worker-1..N (Celery + Playwright)** | — | Cada worker abre un navegador Chromium y automatiza la carga del carrito en GSP |
| **Flower** | 5555 | Dashboard web para monitorear en tiempo real las tareas de Celery |

---

## 🔄 Flujo Completo — Paso a Paso

### Fase 1: Carga del CSV

El operador sube un archivo CSV con los pedidos al endpoint de la API.

```
POST http://localhost:8000/batches/upload
```

**Contenido del CSV (simplificado):**
```csv
consultora_code;consultora_name;product_code;product_name;quantity
958;Maria Heroina Saez Rosas;88934;Luna Absoluta Perfume de Mujer;1
958;Maria Heroina Saez Rosas;76543;Tododia Crema Corporal Frambuesa;1
```

**¿Qué pasa internamente?**

```
                   CSV Upload
                      │
                      ▼
              ┌───────────────┐
              │   Master API  │
              │   (FastAPI)   │
              └───────┬───────┘
                      │ Parsea CSV, agrupa por consultora
                      ▼
              ┌───────────────┐
              │  PostgreSQL   │
              │               │
              │  Batch #42    │  ← status: PENDING
              │    │          │
              │    └─ Order   │  ← consultora_code: "958"
              │        │      │     status: PENDING
              │        ├─ P1  │  ← product_code: "88934", status: PENDING
              │        └─ P2  │  ← product_code: "76543", status: PENDING
              └───────────────┘
```

Se crea:
- **1 Batch** (lote) con ID #42, estado `PENDING`
- **1 Order** (pedido) para CB 958 con 2 productos
- **2 OrderProduct** con estado `PENDING`

---

### Fase 2: Inicio del Batch

El operador inicia el procesamiento:

```
POST http://localhost:8000/batches/42/start
```

**¿Qué pasa internamente?**

```
   Master API                    Redis                    Dispatcher
      │                            │                          │
      │  "Iniciar batch 42"        │                          │
      ├──────────────────────────► │  Cola: process_batch(42) │
      │                            ├─────────────────────────►│
      │                            │                          │
      │                            │     El Dispatcher lee    │
      │                            │     las órdenes del      │
      │                            │     batch y crea UNA     │
      │                            │     tarea por cada       │
      │                            │     orden pendiente      │
      │                            │                          │
      │                            │  Cola: process_order(1)  │
      │                            │◄─────────────────────────┤
```

1. La API publica la tarea `process_batch(42)` en Redis
2. El **Dispatcher** la toma y consulta la BD: "¿Cuántas órdenes pendientes tiene el batch 42?"
3. Por cada orden, publica una tarea `process_order(order_id)` en Redis
4. El batch cambia a estado `RUNNING`

---

### Fase 3: Worker Procesa la Orden de María

Un **Worker** disponible toma la tarea `process_order(1)` de Redis.

```
  Worker-1 (Celery + Playwright)
      │
      │  1. PREFLIGHT — Verifica que GSP esté online
      │     └─ DNS ✓ → TCP :443 ✓ → HTTP 200 ✓
      │
      │  2. BROWSER LAUNCH — Chromium headless + anti-detección
      │     └─ User-Agent personalizado, WebDriver flag desactivado
      │
      │  3. LOGIN — Ingresa con credenciales de supervisor
      │     └─ URL: natura-auth.prd.naturacloud.com
      │     └─ Usuario/Password: desde variables de entorno (secretos)
      │     └─ OrderLog: ✅ LOGIN_OK
      │
      │  4. BUSCAR CONSULTORA — Ingresa CB "958"
      │     └─ Busca a María Heroina Saez Rosas en el sistema
      │     └─ OrderLog: ✅ CONSULTORA_SELECTED
      │
      │  5. SELECCIONAR CICLO — Elige el ciclo activo
      │     └─ OrderLog: ✅ CYCLE_SELECTED
      │
      │  6. ABRIR CARRITO — Limpia carrito previo si existe
      │     └─ OrderLog: ✅ CART_OPEN
      │
      │  7. AGREGAR PRODUCTOS — Uno por uno:
      │     │
      │     ├─ Producto 88934 (Luna Absoluta)
      │     │  └─ ✅ Agregado al carrito → OrderProduct.status = ADDED
      │     │
      │     └─ Producto 76543 (Tododia Crema)
      │        └─ ❌ Sin stock → OrderProduct.status = OUT_OF_STOCK
      │        └─ error_message: "Sin stock"
      │
      │  8. VERIFICAR CARRITO — Bot parsea el DOM del navegador
      │     └─ Confirma: 1 producto en carrito, 1 fallido
      │     └─ OrderLog: ⚠️ PRODUCTS_ADDED (parcial)
      │
      │  9. ACTUALIZAR BD
      │     └─ Order.status = COMPLETED (parcial, pero se completó el proceso)
      │     └─ Batch.completed_orders += 1
      │
      └─ 10. CERRAR NAVEGADOR — Libera recursos
```

**Estado de la BD después del procesamiento:**

```
Batch #42     → status: COMPLETED
  └─ Order #1  → status: COMPLETED (CB: 958)
       ├─ OrderProduct: 88934 → status: ADDED        ✅
       └─ OrderProduct: 76543 → status: OUT_OF_STOCK ❌ "Sin stock"
```

**¿Es parcial?**  
Sí → hay al menos 1 producto `ADDED` y al menos 1 `FAILED/OUT_OF_STOCK`.

---

### Fase 4: Notificaciones por Correo (3 Niveles)

Una vez que el batch se completa, se disparan los envíos de correo.

```
POST http://localhost:8000/batches/42/send-emails
```

El sistema ejecuta `send_batch_notifications(batch_id=42)`:

#### Paso 1: Cruce con consultoras_matriz.csv

El sistema carga el CSV maestro que contiene la jerarquía organizacional:

```
consultoras_matriz.csv
─────────────────────────────────────────────────────────────────────────────────
Nombre Gerencia         ; Nombre GN              ; Mail GN              ; Nombre Setor ; ...
Gerencia Araucaria     ; Karina Yermani Zuñiga  ; karinayermani@...    ; Amancay      ; ...

... ; Nombre Lider                ; Mail lider                     ; CB  ; Nombre                    ; MAIL CB
... ; Camila Andrea Silva Muñoz  ; camilasilvamunoz9@gmail.com    ; 958 ; Maria Heroina Saez Rosas  ; gokupardo123@gmail.com
```

Con el `CB = 958` de la orden, el sistema busca en el CSV y obtiene:
- **Email de María** → para el correo de consultora
- **Líder + sector** → para agregar el correo de líder
- **GN + gerencia** → para agregar el correo de gerente

#### Paso 2: ✉️ Correo Nivel 1 — Consultora

```
Para:    gokupardo123@gmail.com (María)
CC:      emersonsuarez@natura.net, jorgemorandin@natura.net,
         franciscaramirez@natura.net, paulafarias@natura.net
Asunto:  ⚠️ Tu carrito del Live Shopping se cargó parcialmente - CB 958
```

**Contenido del correo:**
- Header visual "Día de las Madres" (imágenes del diseño de Comunicaciones)
- Nombre personalizado: "Hola María Heroina"
- Mensaje: "Tu carrito se cargó parcialmente"
- Lista de productos que no pudieron ser agregados:
  - `76543 - Tododia Crema Corporal Frambuesa`
- Instrucción: "Comunícate con tu líder Camila Andrea Silva Muñoz"
- Footer con redes sociales y app links

#### Paso 3: ✉️ Correo Nivel 2 — Líder

El sistema agrupa todas las consultoras del sector **Amancay** que pertenecen a la líder **Camila Andrea Silva Muñoz**, y envía UN solo correo resumen.

```
Para:    camilasilvamunoz9@gmail.com (Camila - Líder)
CC:      emersonsuarez@natura.net, jorgemorandin@natura.net,
         franciscaramirez@natura.net, paulafarias@natura.net
Asunto:  🌸 Resultados Live Shopping - Sector Amancay (X completos, Y parciales)
```

**Contenido del correo:**

| CB | Consultora | Estado |
|----|-----------|--------|
| 958 | María Heroina Saez Rosas | ⚠️ Parcialmente Completo |
| 2250 | Sonia Alicia Ruiz Cardenas | ✅ Completo |
| 10052 | Betty Burgos Hernandez | ✅ Completo |
| ... | ... | ... |

#### Paso 4: ✉️ Correo Nivel 3 — Gerente

Agrupa todos los sectores/líderes de la **Gerencia Araucaria** y envía UN solo correo resumen a la GN **Karina Yermani Zuñiga**.

```
Para:    karinayermani@natura.net (Karina - GN)
CC:      emersonsuarez@natura.net, jorgemorandin@natura.net,
         franciscaramirez@natura.net, paulafarias@natura.net
Asunto:  📈 Reporte Live Shopping - Gerencia Araucaria (X completos, Y parciales)
```

**Contenido del correo:**

| Líder | Sector | Completos | Parciales |
|-------|--------|-----------|-----------|
| Camila Andrea Silva Muñoz | Amancay | 12 | 3 |
| Claudia Marcela Cea Riquelme | Amancay | 8 | 1 |
| ... | ... | ... | ... |

---

## 🔁 Resumen Visual del Flujo Completo

```
 ┌─────────────┐     ┌──────────┐     ┌───────────┐     ┌────────────┐
 │  Operador   │────►│  Master  │────►│   Redis   │────►│ Dispatcher │
 │  sube CSV   │     │  (API)   │     │  (Cola)   │     │ (Celery)   │
 └─────────────┘     └────┬─────┘     └───────────┘     └─────┬──────┘
                          │                                     │
                     Crea Batch +                         Divide batch
                     Orders en BD                         en N tareas
                          │                                     │
                     ┌────▼─────┐                        ┌──────▼──────┐
                     │PostgreSQL│◄───────────────────────│  Workers    │
                     │          │  Actualiza estado      │ (Playwright)│
                     └────┬─────┘  de cada producto      └─────────────┘
                          │                                     │
                          │                              Automatizan GSP:
                          │                              login → buscar →
                          │                              agregar productos
                          │
                     ┌────▼─────────────────┐
                     │  send_batch_notifications()       │
                     │                                   │
                     │  1. Lee órdenes del batch         │
                     │  2. Cruza con CSV de consultoras   │
                     │  3. Envía correos en 3 niveles    │
                     │     ├─ Consultora (individual)    │
                     │     ├─ Líder (sector agrupado)    │
                     │     └─ Gerente (gerencia agrupada)│
                     │                                   │
                     │  Gmail API (OAuth2)               │
                     └───────────────────────────────────┘
```

---

## 🔧 Para Probar (sin afectar a nadie real)

### Opción 1: Datos simulados — un solo tipo de correo

```bash
# Correo consultora completo
curl -X POST "http://localhost:8000/test-email?to=ignaciosolar.experis@natura.net"

# Correo consultora parcial (con productos fallidos)
curl -X POST "http://localhost:8000/test-email?to=ignaciosolar.experis@natura.net&is_partial=true"

# Correo líder (tabla de consultoras)
curl -X POST "http://localhost:8000/test-email/lider?to=ignaciosolar.experis@natura.net"

# Correo gerente (tabla de líderes)
curl -X POST "http://localhost:8000/test-email/gerente?to=ignaciosolar.experis@natura.net"
```

### Opción 2: Datos reales de un batch — todo redirigido

```bash
# Usa batch real #42, pero TODO va a tu correo (sin CC)
curl -X POST "http://localhost:8000/test-email/batch/42?to=ignaciosolar.experis@natura.net"
```

Esto ejecuta el flujo real (lee BD + CSV de consultoras + genera correos reales) pero redirige los 3 niveles al correo indicado, sin enviar CC.

---

## 📊 Monitoreo en Tiempo Real

| Herramienta | URL | Uso |
|-------------|-----|-----|
| **API - Panel** | `http://localhost:8000/docs` | Swagger UI con todos los endpoints |
| **Flower** | `http://localhost:5555` | Dashboard Celery: ver tareas activas, workers, colas |
| **Logs del batch** | `GET /batches/42/stats` | Progreso %, órdenes completadas, ETA |
| **Logs de una orden** | `GET /orders/1/logs` | Auditoría paso a paso con timestamps |

---

## 🔐 Seguridad

- **Credenciales GSP:** Variables de entorno (`GSP_USER_CODE`, `GSP_PASSWORD`), nunca hardcodeadas
- **Token Gmail:** Inyectado vía `GMAIL_TOKEN_JSON` como GitHub Secret, auto-creado en el container
- **Proxy corporativo:** Soportado nativamente via `HTTP_PROXY`/`HTTPS_PROXY`
- **Secretos en CI/CD:** GitHub Environment `Machine_Learning_10.224.6.16`

---

## ❓ Preguntas Frecuentes

**¿Qué pasa si un producto no tiene stock?**  
→ Se marca como `OUT_OF_STOCK`. Si otros productos sí se agregaron, María recibe un correo "parcialmente completo" con la lista de lo que falló. Su líder puede ayudarla.

**¿Qué pasa si toda la orden falla (error de sistema, no stock)?**  
→ La orden queda como `FAILED`. No se envía correo. Se puede reintentar manualmente con `POST /orders/{id}/retry`. Máximo 3 reintentos con backoff (30s, 60s, 90s).

**¿Cuántos carritos se procesan a la vez?**  
→ Depende del número de Workers. Cada Worker maneja 1 navegador a la vez. Con 3 Workers = 3 carritos simultáneos. Se puede escalar agregando workers en `docker-compose.yml`.

**¿De dónde salen los emails de cada consultora?**  
→ Del archivo `data/consultoras_matriz.csv`. Se cruza por columna `CB` (código de consultora). El mismo CSV tiene los datos de líder, sector, GN y gerencia.

**¿Cómo sé si un batch terminó?**  
→ `GET /batches/42/stats` devuelve progreso en tiempo real. También se puede ver en Flower (puerto 5555).
