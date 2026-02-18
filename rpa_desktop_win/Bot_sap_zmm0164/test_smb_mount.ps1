# Script de prueba SMB/CIFS - PowerShell
# Prueba el montaje de la unidad de red con credenciales

Write-Host "`n" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "TEST MONTAJE SMB/CIFS - WINDOWS" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# Parámetros de prueba
$UNC_PATH = "\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164"
$DRIVE_LETTER = "Z"
$DOMAIN = "NATURA"
$USERNAME = "cmancill"
$PASSWORD = "B3l3n-2304!!"

Write-Host "`n📋 PARÁMETROS:" -ForegroundColor Yellow
Write-Host "   UNC Path:    $UNC_PATH"
Write-Host "   Unidad:      $DRIVE_LETTER`:"
Write-Host "   Dominio:     $DOMAIN"
Write-Host "   Usuario:     $USERNAME"
Write-Host "   Contraseña:  $(if ($PASSWORD) { '*' * $PASSWORD.Length } else { '[vacía]' })" -ForegroundColor Red

# TEST 1: Desconectar si ya existe
Write-Host "`n[1/3] Desconectando unidad $DRIVE_LETTER`: si existe..." -ForegroundColor Cyan
try {
    net use "$DRIVE_LETTER`:" /delete /y 2>&1 | Out-Null
    Write-Host "     ✓ Limpieza completada" -ForegroundColor Green
} catch {
    Write-Host "     ℹ️  Sin conexión anterior (primera vez)" -ForegroundColor Gray
}

# TEST 2: Intentar montaje
Write-Host "`n[2/3] Montando unidad SMB con 'net use'..." -ForegroundColor Cyan
Write-Host "     Ejecutando: net use $DRIVE_LETTER`": `"$UNC_PATH`" `"$PASSWORD`" /user:$DOMAIN\$USERNAME /persistent:yes" -ForegroundColor Gray

$output = net use "$DRIVE_LETTER`:" "$UNC_PATH" "$PASSWORD" "/user:$DOMAIN\$USERNAME" /persistent:yes 2>&1
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`n✅ MONTAJE EXITOSO" -ForegroundColor Green
    Write-Host "   $DRIVE_LETTER`: → $UNC_PATH" -ForegroundColor Green
} else {
    Write-Host "`n❌ ERROR EN MONTAJE" -ForegroundColor Red
    Write-Host "   Código de error: $exitCode" -ForegroundColor Red
    Write-Host "   Output:" -ForegroundColor Red
    Write-Host "   $output" -ForegroundColor Red
    
    # Interpretar códigos de error comunes
    $errorMessages = @{
        67 = "Error 67: No se encuentra el nombre de red especificado (verificar IP/servidor)"
        1326 = "Error 1326: Las credenciales son incorrectas"
        5 = "Error 5: Acceso denegado"
        85 = "Error 85: La unidad ya está en uso"
    }
    
    if ($errorMessages.ContainsKey($exitCode)) {
        Write-Host "   Explicación: $($errorMessages[$exitCode])" -ForegroundColor Yellow
    }
}

# TEST 3: Verificar montaje
Write-Host "`n[3/3] Verificando montaje..." -ForegroundColor Cyan

$drivePath = "$DRIVE_LETTER`:"
if (Test-Path $drivePath) {
    Write-Host "✅ Unidad $DRIVE_LETTER`: existe" -ForegroundColor Green
    
    # Intentar listar contenido
    try {
        $items = Get-ChildItem $drivePath -ErrorAction Stop
        Write-Host "✅ Contenido accesible ($($items.Count) items)" -ForegroundColor Green
        
        Write-Host "`n   Primeros items encontrados:" -ForegroundColor Gray
        $items | Select-Object -First 5 | ForEach-Object {
            $icon = if ($_.PSIsContainer) { "📁" } else { "📄" }
            Write-Host "      $icon $($_.Name)" -ForegroundColor Gray
        }
        
        if ($items.Count -gt 5) {
            Write-Host "      ... y $($items.Count - 5) items más" -ForegroundColor Gray
        }
    } catch [UnauthorizedAccessException] {
        Write-Host "⚠️  Unidad mapeada pero sin permisos de lectura" -ForegroundColor Yellow
    } catch {
        Write-Host "⚠️  Error al listar contenido: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "❌ Unidad $DRIVE_LETTER`: no existe o no es accesible" -ForegroundColor Red
}

# RESUMEN
Write-Host "`n" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "📊 RESUMEN" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

if ($exitCode -eq 0 -and (Test-Path $drivePath)) {
    Write-Host ✅ "MONTAJE EXITOSO - Unidad lista para usar" -ForegroundColor Green
} else {
    Write-Host ❌ "MONTAJE FALLÓ - Verifica credenciales, IP, o conectividad" -ForegroundColor Red
}

Write-Host "`n"
