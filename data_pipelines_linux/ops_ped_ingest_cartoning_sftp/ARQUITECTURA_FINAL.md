# ✅ Arquitectura Final - Procesamiento Directo Sin Copia

## Cambios Implementados

### ❌ ELIMINADO: Copia Redundante
**Antes**: 
```
Rclone (E:\Datalake\...) 
    ↓ COPIA ↓
Landing Local (data_lake/bronze/)
    ↓
SQL Server
```

**Ahora**:
```
Rclone (E:\Datalake\...)
    ↓ LECTURA DIRECTA ↓
SQL Server
```

### Ventajas:
- ✅ **Ahorro de espacio**: No duplicamos archivos
- ✅ **Más rápido**: Sin I/O de copia
- ✅ **Más simple**: Menos carpetas que administrar
- ✅ **Único origen de verdad**: Los archivos en Rclone

## Flujo de Procesamiento

### 1. Detección (state.json)
```json
{
  "Cartoning:file1.txt": {
    "mtime": 1705251234.5,
    "size": 5000,
    "sql_ok": true
  },
  "WaveConfirm:file2.txt": {
    "mtime": 1705251235.2,
    "size": 3000,
    "sql_ok": true
  },
  "OutboundDelivery:file3.txt": {
    "mtime": 1705251236.8,
    "size": 8000,
    "sql_ok": false  // Pendiente de procesar
  }
}
```

**Lógica**:
- Compara `mtime` y `size` de archivos en Rclone vs state.json
- Si es nuevo o modificado → procesar
- Si ya está con `sql_ok=true` → ignorar

### 2. Procesamiento Directo

```python
# LocalFileClient.list_files() retorna:
FileInfo(
    filename="file.txt",
    full_path="E:\\Datalake\\Archivos\\EWM\\cartoning\\02_Old\\file.txt",  # ← Ruta completa
    mtime=1705251234.5,
    size=5000
)

# Parser lee directamente de full_path:
df = FileParser.parse_cartoning_to_dataframe(file_info.full_path)

# Se inserta en SQL:
sql_repo.bulk_insert(df, "Staging_EWM_Cartoning")

# SP procesa:
sql_repo.execute_sp("sp_Procesar_Cartoning_EWM", {"ArchivoActual": "file.txt"})

# Se marca como procesado:
state_manager.mark_as_processed_in_sql("Cartoning:file.txt")
```

### 3. BitacoraArchivos

Cada fuente registra en `BitacoraArchivos` al ejecutar el SP:

```sql
INSERT INTO BitacoraArchivos (NombreArchivo, Estado, Mensaje)
VALUES (
    'file.txt',
    'Procesado',
    'Headers: 5 | Items: 20 | Version: 123'
);
```

**Verificación multi-fuente**:
```sql
SELECT 
    NombreArchivo,
    Estado,
    Mensaje,
    FechaEvento,
    CASE 
        WHEN Mensaje LIKE '%Headers:%' THEN 'OutboundDelivery'
        WHEN Mensaje LIKE '%WaveConfirm:%' THEN 'WaveConfirm'
        ELSE 'Cartoning'
    END AS Fuente
FROM BitacoraArchivos
ORDER BY FechaEvento DESC;
```

## Estructura de state.json

### Ejemplo Completo:

```json
{
  "Cartoning:EWM_20260114_001.txt": {
    "mtime": 1705251234.5,
    "size": 5000,
    "sql_ok": true
  },
  "Cartoning:EWM_20260114_002.txt": {
    "mtime": 1705251235.0,
    "size": 5100,
    "sql_ok": true
  },
  "WaveConfirm:WC_20260114_001.txt": {
    "mtime": 1705251235.2,
    "size": 3000,
    "sql_ok": true
  },
  "WaveConfirm:WC_20260114_002.txt": {
    "mtime": 1705251236.0,
    "size": 3200,
    "sql_ok": false
  },
  "OutboundDelivery:OBDLV_20260114_001.txt": {
    "mtime": 1705251236.8,
    "size": 8000,
    "sql_ok": true
  },
  "OutboundDelivery:OBDLV_20260114_002.txt": {
    "mtime": 1705251237.5,
    "size": 8500,
    "sql_ok": false
  }
}
```

### Prefijos por Fuente:
- `Cartoning:` - Archivos de cartoning
- `WaveConfirm:` - Archivos de waveconfirm  
- `OutboundDelivery:` - Archivos de IDocs SAP

**Garantiza**:
- ✅ No hay colisiones entre fuentes (mismo nombre de archivo)
- ✅ Cada fuente trackea independientemente
- ✅ Fácil depuración (grep por prefijo)

## Código Clave

### LocalFileClient (actualizado)

```python
@dataclass
class FileInfo:
    filename: str
    full_path: str  # ← NUEVO: Ruta completa para lectura directa
    mtime: float
    size: int

class LocalFileClient:
    def list_files(self) -> List[FileInfo]:
        files = []
        for filename in os.listdir(self.source_path):
            if filename.endswith('.partial'):  # Ignorar rclone descargando
                continue
            
            full_path = os.path.join(self.source_path, filename)
            
            if os.path.isfile(full_path):
                stat = os.stat(full_path)
                files.append(FileInfo(
                    filename=filename,
                    full_path=full_path,  # ← Ruta completa
                    mtime=stat.st_mtime,
                    size=stat.st_size
                ))
        return files
```

### Pipeline (simplificado)

```python
def _detect_new_files(self, source: DataSource):
    all_files = source.file_client.list_files()
    pending = []
    
    for file_info in all_files:
        state_key = f"{source.name}:{file_info.filename}"
        
        if self.state.is_new_or_modified(state_key, file_info.mtime, file_info.size):
            pending.append(file_info)
    
    return pending

def _process_batch(self, source: DataSource, file_list):
    for file_info in file_list:
        # Leer directamente desde full_path
        df = source.parser_func(file_info.full_path)
        
        # Insertar en SQL
        self.sql.bulk_insert(df, source.staging_table)
        
        # Ejecutar SP
        self.sql.execute_sp(source.sp_name, {"ArchivoActual": file_info.filename})
        
        # Marcar como procesado
        state_key = f"{source.name}:{file_info.filename}"
        self.state.register_download(state_key, file_info.mtime, file_info.size)
        self.state.mark_as_processed_in_sql(state_key)
```

## Verificación Multi-Fuente

### 1. Verificar state.json

```powershell
# Ver archivos pendientes
Get-Content state_store.json | ConvertFrom-Json | 
    ConvertTo-Json -Depth 10 | 
    Select-String '"sql_ok": false'

# Contar por fuente
$state = Get-Content state_store.json | ConvertFrom-Json
$state.PSObject.Properties | Group-Object { $_.Name.Split(':')[0] }
```

### 2. Verificar BitacoraArchivos

```sql
-- Total procesados por fuente (aproximado por mensaje)
SELECT 
    CASE 
        WHEN Mensaje LIKE '%Headers:%' THEN 'OutboundDelivery'
        WHEN Mensaje LIKE '%WaveConfirm:%' THEN 'WaveConfirm'
        ELSE 'Cartoning'
    END AS Fuente,
    COUNT(*) AS Total,
    SUM(CASE WHEN Estado = 'Procesado' THEN 1 ELSE 0 END) AS Exitosos,
    SUM(CASE WHEN Estado = 'ERROR' THEN 1 ELSE 0 END) AS Errores
FROM BitacoraArchivos
WHERE FechaEvento >= DATEADD(DAY, -1, GETDATE())
GROUP BY 
    CASE 
        WHEN Mensaje LIKE '%Headers:%' THEN 'OutboundDelivery'
        WHEN Mensaje LIKE '%WaveConfirm:%' THEN 'WaveConfirm'
        ELSE 'Cartoning'
    END
ORDER BY Fuente;
```

### 3. Verificar versionado

```sql
-- Últimas versiones por fuente
SELECT 'Cartoning' AS Fuente, MAX(NumeroVersion) AS UltimaVersion FROM EWM_Cartoning
UNION ALL
SELECT 'WaveConfirm', MAX(NumeroVersion) FROM EWM_WaveConfirm
UNION ALL
SELECT 'OutboundDelivery', MAX(NumeroVersion) FROM EWM_OutboundDelivery_Header;
```

## Seguridad SQL Multi-Fuente

### ✅ Sin Deadlocks

**Garantizado por**:
1. **Tablas separadas**: Cada fuente tiene sus propias staging y finales
2. **SPs secuenciales**: Loop `for` sin threads en procesamiento SQL
3. **Única tabla compartida**: `BitacoraArchivos` - INSERTs rápidos sin locks prolongados

### Configuración Óptima

```python
config = {
    'threads': 3  # Solo para detección de archivos (no SQL)
}
```

### Orden de Ejecución

```
CICLO 1:
  Cartoning: detectar → procesar SQL (secuencial)
  WaveConfirm: detectar → procesar SQL (secuencial)
  OutboundDelivery: detectar → procesar SQL (secuencial)

CICLO 2: (5 minutos después)
  ...
```

## Resumen

| Aspecto | Implementación |
|---------|---------------|
| **Archivos origen** | E:\Datalake\Archivos\EWM\... (Rclone) |
| **Copia local** | ❌ ELIMINADA |
| **Lectura** | Directa desde origen |
| **State tracking** | state.json con prefijos por fuente |
| **Auditoría** | BitacoraArchivos en SQL |
| **Versionado** | Automático en tablas finales |
| **Threads** | 3 (detección) |
| **SQL** | Secuencial (sin deadlocks) |
| **Reintentos** | Automático (archivos con sql_ok=false) |

✅ **Sistema completamente funcional y optimizado para 3 fuentes simultáneas**
