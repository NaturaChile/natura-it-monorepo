# Limpieza de Archivos Obsoletos - Post Migración

## ❌ Archivos a ELIMINAR (ya no se usan)

### 1. SFTP Client
```
src/adapters/sftp_client.py
```
**Razón**: Reemplazado por `local_file_client.py`

### 2. Pipeline SFTP Multi-Fuente
```
src/use_cases/multi_source_pipeline.py
```
**Razón**: Reemplazado por `multi_source_local_pipeline.py`

### 3. Pipeline Legacy Single-Source
```
src/use_cases/ingest_pipeline.py
```
**Razón**: Versión antigua de single-source, reemplazada por multi-source local

### 4. Explorador WaveConfirm
```
explore_waveconfirm.py
```
**Razón**: Script de análisis inicial, ya no necesario (WaveConfirm integrado en producción)

## ✅ Archivos ACTIVOS (en uso)

### Adapters
- ✅ `src/adapters/local_file_client.py` - Cliente para carpetas locales
- ✅ `src/adapters/sql_repository.py` - Conexión SQL Server
- ✅ `src/adapters/state_manager.py` - Gestión de state.json

### Domain
- ✅ `src/domain/file_parser.py` - Parsers (Cartoning, WaveConfirm, OutboundDelivery)

### Use Cases
- ✅ `src/use_cases/multi_source_local_pipeline.py` - Pipeline principal multi-fuente local

### Main
- ✅ `main.py` - Entry point configurado para 3 fuentes locales

### SQL
- ✅ `sql/setup_database.sql` - Tablas Cartoning + WaveConfirm
- ✅ `sql/setup_outbound_delivery.sql` - Tablas Outbound Delivery
- ✅ `sql/update_waveconfirm_versionado.sql` - SP WaveConfirm con versionado

## 🔧 Variables de Entorno OBSOLETAS

Pueden eliminarse del workflow y secrets de GitHub:
- ❌ `EWM_SFTP_HOST`
- ❌ `EWM_SFTP_USER`
- ❌ `EWM_SFTP_PASS`
- ❌ `EWM_REMOTE_PATH`

## ✅ Variables NECESARIAS

Solo estas:
- ✅ `SQL_HOST`
- ✅ `SQL_DB_NAME`
- ✅ `SQL_USER`
- ✅ `SQL_PASS`

## 📦 Dependencias Python OBSOLETAS

En `requirements.txt`, pueden eliminarse si solo se usaban para SFTP:
- `paramiko` (usado solo por sftp_client.py)

**NOTA**: Verificar antes de eliminar si otros proyectos del monorepo usan paramiko.

## 🎯 Limpieza Recomendada

### Opción 1: Mover a carpeta Archive
```powershell
# Crear carpeta de archivo
mkdir archive_pre_local_migration

# Mover archivos obsoletos
Move-Item src/adapters/sftp_client.py archive_pre_local_migration/
Move-Item src/use_cases/multi_source_pipeline.py archive_pre_local_migration/
Move-Item src/use_cases/ingest_pipeline.py archive_pre_local_migration/
Move-Item explore_waveconfirm.py archive_pre_local_migration/
```

### Opción 2: Eliminar directamente
```powershell
Remove-Item src/adapters/sftp_client.py
Remove-Item src/use_cases/multi_source_pipeline.py
Remove-Item src/use_cases/ingest_pipeline.py
Remove-Item explore_waveconfirm.py
```

## ⚠️ Validación Post-Limpieza

Ejecutar para verificar que no hay imports rotos:
```powershell
cd data_pipelines_linux/ops_ped_ingest_cartoning_sftp
python -m py_compile main.py
python -m py_compile src/use_cases/multi_source_local_pipeline.py
python -m py_compile src/adapters/local_file_client.py
python -m py_compile src/domain/file_parser.py
```

Si todo compila sin errores, la limpieza fue exitosa.
