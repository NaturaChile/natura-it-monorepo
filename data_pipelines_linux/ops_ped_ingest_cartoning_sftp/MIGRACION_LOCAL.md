# Migración a Arquitectura Local (Rclone)

## Cambios Implementados

### 1. Nueva Fuente de Datos: Outbound Delivery (SAP IDoc)
- Parser jerárquico que convierte IDocs en 2 tablas relacionadas:
  - **CABECERA**: Delivery_ID, Peso, Volumen, Destinatario, Dirección, Transportista, Fecha
  - **ITEMS**: Delivery_ID_FK, Item_Number, Material_SKU, Descripción, Cantidad, Peso_Neto

### 2. Arquitectura Local (Sin SFTP)
- **Antes**: Descarga desde servidor SFTP (10.212.6.90)
- **Ahora**: Lee de carpetas locales donde Rclone ya descargó los archivos
- **Ventaja**: Elimina problemas de conexión SSH y bloqueos de IP

### 3. Filtrado de Archivos .partial
- Ignora automáticamente archivos `.partial` (Rclone descargando)
- Solo procesa archivos completamente descargados

## Rutas de Origen (Rclone)

```
E:\Datalake\Archivos\EWM\ewm_to_gera\cartoning\02_Old\         → Cartoning
E:\Datalake\Archivos\EWM\ewm_to_gera\waveconfirm\02_Old\       → WaveConfirm
E:\Datalake\Archivos\EWM\gera_to_ewm_outbounddelivery\         → Outbound Delivery
```

## Rutas de Landing (Workspace)

```
ops_ped_ingest_cartoning_sftp/data_lake/bronze/cartoning/
ops_ped_ingest_cartoning_sftp/data_lake/bronze/waveconfirm/
ops_ped_ingest_cartoning_sftp/data_lake/bronze/outbound_delivery/
```

## SQL - Instalación

```sql
-- Ejecutar en OPS_OrquestaFact
USE OPS_OrquestaFact;
GO

-- Script completo
:r E:\path\to\sql\setup_outbound_delivery.sql
```

## Estructura de Datos

### Outbound Delivery - CABECERA
| Campo | Tipo | Origen IDoc |
|-------|------|-------------|
| Delivery_ID | NVARCHAR(50) | E1BPOBDLVHDR Col 1 (PK) |
| Peso_Bruto | DECIMAL(18,3) | E1BPOBDLVHDR Col 6 |
| Volumen | DECIMAL(18,3) | E1BPOBDLVHDR Col 10 |
| Destinatario | NVARCHAR(255) | E1BPADR1 Col 3 |
| Direccion | NVARCHAR(500) | E1BPADR1 Col 16 + Col 8 |
| Region | NVARCHAR(100) | E1BPADR1 Col 28 |
| Transportista | NVARCHAR(255) | E1BPEXTC (ZCARRIER_NAME) |
| Fecha_Entrega | DATE | E1BPEXTC (ZDELV_DATE) |
| NumeroVersion | INT | Auto-incrementado |

### Outbound Delivery - ITEMS
| Campo | Tipo | Origen IDoc |
|-------|------|-------------|
| Delivery_ID_FK | NVARCHAR(50) | E1BPOBDLVITEM Col 1 (FK) |
| Item_Number | NVARCHAR(50) | E1BPOBDLVITEM Col 2 |
| Material_SKU | NVARCHAR(100) | E1BPOBDLVITEM Col 3 |
| Descripcion | NVARCHAR(500) | E1BPOBDLVITEM Col 5 |
| Cantidad | DECIMAL(18,3) | E1BPOBDLVITEM Col 8 |
| Unidad_Medida | NVARCHAR(10) | E1BPOBDLVITEM Col 9 |
| Peso_Neto_Item | DECIMAL(18,3) | E1BPOBDLVITEM Col 15 |
| NumeroVersion | INT | Auto-incrementado |

## Configuración

### main.py
```python
config = {
    'threads': 3,           # Procesamiento paralelo (sin restricciones SSH)
    'sleep_seconds': 300    # 5 minutos entre ciclos
}
```

### Variables de Entorno
```bash
# Ya NO se necesitan:
# - EWM_SFTP_HOST
# - EWM_SFTP_USER
# - EWM_SFTP_PASS

# Solo SQL:
SQL_HOST=10.156.16.45\SQL2019
SQL_DB_NAME=OPS_OrquestaFact
SQL_USER=...
SQL_PASS=...
```

## Ejecución

### Local (Desarrollo)
```powershell
cd data_pipelines_linux/ops_ped_ingest_cartoning_sftp
python main.py
```

### GitHub Actions
El workflow existente funcionará sin cambios (ya lee de carpetas locales del runner).

## Verificación

### 1. Revisar logs en consola
```
===== Iniciando Pipeline Multi-Fuente (LOCAL) =====
Fuentes: ['Cartoning', 'WaveConfirm', 'OutboundDelivery']
Threads compartidos: 3

--- PASO 1: DESCARGA DE ARCHIVOS ---
[Cartoning] Archivos remotos: 45
[WaveConfirm] Archivos remotos: 23
[OutboundDelivery] Archivos remotos: 12

Descargados exitosamente: 8 archivos

--- PROCESANDO: OutboundDelivery (3 archivos) ---
[OutboundDelivery] OK: file1.txt
[OutboundDelivery] Resultado: 3 OK | 0 Errores
```

### 2. Verificar tablas SQL
```sql
-- Ver últimas versiones procesadas
SELECT TOP 10 * 
FROM EWM_OutboundDelivery_Header 
ORDER BY NumeroVersion DESC;

SELECT TOP 10 * 
FROM EWM_OutboundDelivery_Items 
ORDER BY NumeroVersion DESC;

-- Verificar bitácora
SELECT * FROM BitacoraArchivos 
WHERE NombreArchivo LIKE '%outbound%'
ORDER BY FechaProceso DESC;
```

### 3. Revisar state.json
```json
{
  "Cartoning:file1.txt": {"mtime": 123456, "size": 5000, "sql_ok": true},
  "WaveConfirm:file2.txt": {"mtime": 123457, "size": 3000, "sql_ok": true},
  "OutboundDelivery:file3.txt": {"mtime": 123458, "size": 8000, "sql_ok": true}
}
```

## Troubleshooting

### Archivos no se procesan
1. Verificar que Rclone terminó la descarga (no hay .partial)
2. Revisar que las rutas `E:\Datalake\...` existan
3. Verificar permisos de lectura en carpetas

### Error de parsing
1. Revisar formato del archivo (delimitador `;`)
2. Ver logs específicos del parser
3. Validar estructura IDoc si es Outbound Delivery

### Error SQL
1. Verificar que ejecutaste `setup_outbound_delivery.sql`
2. Revisar permisos en tablas `Staging_EWM_OutboundDelivery_*`
3. Ver errores en SP `sp_Procesar_OutboundDelivery_EWM`
