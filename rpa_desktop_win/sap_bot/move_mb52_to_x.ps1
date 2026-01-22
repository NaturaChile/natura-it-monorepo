# Script para mover el archivo MB52 desde Downloads a la unidad X:
$fechaHoy = Get-Date -Format "yyyy.MM.dd"

$nombreArchivo = "Base Stock Tiendas $fechaHoy.xlsx"

$rutaOrigen  = "C:\Users\robotch_fin\Downloads\$nombreArchivo"
$rutaDestino = "X:\Publico\RPA\Retail\Stock - Base Tiendas"

if (Test-Path $rutaOrigen) {
    try {
        Move-Item -Path $rutaOrigen -Destination $rutaDestino -Force -ErrorAction Stop
        Write-Host "ÉXITO: Archivo movido correctamente a la unidad X:" -ForegroundColor Green
    } catch {
        Write-Error "ERROR MOVIENDO ARCHIVO: $($_.Exception.Message)"
        exit 2
    }
} else {
    Write-Warning "ERROR: No se encontró el archivo de hoy: $rutaOrigen"
    exit 1
}
