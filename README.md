# natura-it-monorepo
Estructura unificada para bots Windows y Linux

Este documento está diseñado para ser la "fuente de la verdad" de tu equipo, explicando la arquitectura híbrida y las reglas estrictas de nomenclatura basadas en el organigrama de Natura.

---

# 🌿 Natura IT Monorepo - Arquitectura RPA Híbrida

Este repositorio centraliza el ecosistema de automatización e ingeniería de datos de Natura Chile. Implementa una **Arquitectura Híbrida** que permite la convivencia y despliegue orquestado de bots de distinta naturaleza bajo estándares unificados de desarrollo y seguridad.

## 🏗 Arquitectura del Proyecto

El repositorio sigue un patrón de **Monorepo** dividido por entornos de ejecución:

| Directorio | Entorno de Ejecución | Descripción | Tecnologías |
| --- | --- | --- | --- |
| **`rpa_desktop_win/`** | **Windows Server** | Automatizaciones que requieren GUI (Interfaz Gráfica) o drivers legacy. | SAP GUI Scripting, PyWin32, Excel Macros. |
| **`rpa_headless_linux/`** | **Linux (Docker)** | Bots web de alta velocidad, sin interfaz visual, APIs y microservicios. | Playwright (Headless), Requests, APIs. |
| **`data_pipelines_linux/`** | **Linux (Docker)** | Procesos ETL masivos y movimiento de datos "Heavy-Duty". | Pandas, SQLAlchemy, Databricks Connector. |
| **`core_shared/`** | **Agnóstico** | Librería común de seguridad, logs y utilidades compartida por todos los bots. | Vault, OAuth2, Loggers, Config Loaders. |

---

## 📏 Estándar de Nomenclatura (Naming Convention)

Para garantizar el orden, la mantenibilidad y el enrutamiento correcto en los pipelines de CI/CD, **todo archivo principal de bot debe seguir estrictamente la siguiente fórmula**:

> **Fórmula:** `[DOMINIO]_[AREA]_[VERBO]_[OBJETO]_[SISTEMA].py`

### 1. Tablas de Dominios y Áreas (Organizacionales)

Basado en el Organigrama Oficial de Natura Chile.

#### 🏭 OPS - Operaciones y Logística

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`ped`** | Ciclo de Pedido | Gestión de pedidos, picking, venta online. |
| **`tpt`** | Transporte | Última milla, fletes, seguimiento. |
| **`pln`** | Planning | Planificación de demanda y abastecimiento. |
| **`com`** | Comex | Comercio exterior, aduanas, importaciones. |
| **`cal`** | Calidad | Liberación de lotes, bloqueos, seguridad. |
| **`cmp`** | Compras | Supply chain, gestión de proveedores. |
| **`fac`** | Facilities | Servicios generales, espacios. |

#### 💰 FIN - Finanzas

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`pln`** | Planeamiento Fin. | Presupuestos, proyecciones financieras. |
| **`acc`** | Contabilidad | Cierres, asientos, balances, activos fijos. |
| **`tax`** | Impuestos | Cumplimiento tributario, F29, SII. |
| **`cyc`** | Crédito y Cobranza | Evaluación de riesgo, gestión de morosidad. |
| **`ret`** | Finanzas Retail | Cuadraturas de tiendas, gestión de caja. |

#### 🚀 GRW - Growth (Crecimiento)

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`sin`** | Sell In | Metas de venta a consultoras. |
| **`sou`** | Sell Out | Rotación de producto, venta final. |
| **`ret`** | Retención | Reactivación de consultoras, churn. |
| **`cxp`** | Customer Experience | NPS, encuestas, satisfacción. |

#### 📢 MKT - Marketing & Sustentabilidad

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`prd`** | Producto | Catálogo, precios, lanzamiento de categorías. |
| **`sus`** | Sustentabilidad | Huella de carbono, reportes de impacto. |
| **`com`** | Comunicación | Redes sociales, branding, medios. |

#### 💼 COM - Comercial

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`rel`** | Relacionamiento | Gestión de líderes y gerentes de negocio. |
| **`rce`** | Eventos | Reconocimiento, premios, convenciones. |
| **`vts`** | Ventas | Gestión de zonas geográficas. |

#### 🏪 RET - Retail

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`std`** | Store Design | Diseño y mantenimiento de tiendas. |
| **`fv`** | Fuerza de Ventas | Gestión de equipos en tienda. |
| **`mkt`** | Retail Marketing | Material POP, visual merchandising. |

#### 💻 TEC - Tecnología

| Código Área | Nombre del Área | Responsabilidad |
| --- | --- | --- |
| **`dat`** | Datos | Ingesta, ETLs técnicos, Data Quality. |
| **`inf`** | Infraestructura | Servidores, redes, monitoreo. |
| **`sec`** | Seguridad | Accesos, gestión de identidad. |

---

### 2. Tabla de Verbos (Acciones)

Usar siempre en inglés y en infinitivo.

| Verbo | Uso Correcto | Ejemplo |
| --- | --- | --- |
| **`get`** | Obtener datos (lectura simple). | `get_exchange_rate` |
| **`download`** | Descargar un archivo físico. | `download_invoice_pdf` |
| **`process`** | Lógica de negocio compleja. | `process_monthly_payroll` |
| **`update`** | Modificar un registro existente. | `update_stock_level` |
| **`create`** | Crear un registro nuevo. | `create_purchase_order` |
| **`delete`** | Eliminar registros o archivos. | `delete_temp_files` |
| **`ingest`** | Mover datos masivos (ETL). | `ingest_sales_history` |
| **`send`** | Enviar comunicaciones. | `send_welcome_email` |
| **`validate`** | Chequeos de calidad/reglas. | `validate_tax_id` |
| **`reconcile`** | Cruzar dos fuentes de datos. | `reconcile_bank_statement` |

---

### 3. Tabla de Objetos (Entidades)

La entidad principal sobre la que actúa el bot.

| Objeto | Significado |
| --- | --- |
| **`invoice`** | Factura (Proveedores o Clientes). |
| **`order`** | Pedido de venta. |
| **`po`** | Orden de Compra (Purchase Order). |
| **`stock`** | Inventario / Existencias. |
| **`report`** | Reportes genéricos. |
| **`client`** | Cliente final o Consultora. |
| **`lead`** | Prospecto comercial. |
| **`employee`** | Empleado / Colaborador. |
| **`contract`** | Contrato legal. |
| **`ticket`** | Caso de soporte / Reclamo. |

---

### 4. Tabla de Sistemas (Plataformas)

Indica dónde ocurre la acción principal.

| Código | Sistema / Plataforma |
| --- | --- |
| **`sap`** | SAP ERP (GUI o Netweaver). |
| **`sii`** | Servicio de Impuestos Internos. |
| **`dbr`** | Databricks / Data Lake. |
| **`sf`** | Salesforce. |
| **`sql`** | SQL Server / Base de Datos. |
| **`excel`** | Archivos Excel locales o Sharepoint. |
| **`mail`** | Outlook / Gmail / SMTP. |
| **`web`** | Portales web genéricos. |
| **`api`** | Integraciones vía API REST/SOAP. |

---

## 📝 Ejemplos de Uso

**Caso 1: Bot de Finanzas (Windows)**

> *El equipo de Contabilidad necesita liberar facturas en SAP GUI.*
> * **Dominio:** `fin`
> * **Área:** `acc` (Accounting)
> * **Verbo:** `release`
> * **Objeto:** `invoices`
> * **Sistema:** `sap`
> 
> 
> **Nombre Final:** `fin_acc_release_invoices_sap.py`

**Caso 2: Bot de Operaciones (Linux)**

> *El equipo de Transporte necesita descargar el estado de los despachos desde una web.*
> * **Dominio:** `ops`
> * **Área:** `tpt` (Transporte)
> * **Verbo:** `track` (o `get`)
> * **Objeto:** `delivery`
> * **Sistema:** `web`
> 
> 
> **Nombre Final:** `ops_tpt_track_delivery_web.py`

**Caso 3: Pipeline de Datos (Linux)**

> *Ingeniería de datos necesita cargar las ventas diarias a Databricks.*
> * **Dominio:** `tec`
> * **Área:** `dat` (Datos)
> * **Verbo:** `ingest`
> * **Objeto:** `sales`
> * **Sistema:** `dbr` (Databricks)
> 
> 
> **Nombre Final:** `tec_dat_ingest_sales_dbr.py`
