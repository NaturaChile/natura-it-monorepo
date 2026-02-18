#!/usr/bin/env python
r"""
Script de prueba para el montaje SMB/CIFS en Windows.

Uso:
    python test_smb_mount.py

O con variables de entorno:
    $env:BOT_ZMM0164_OUTPUT_UNC_PATH = "\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164"
    $env:BOT_ZMM0164_OUTPUT_NET_DOMAIN = "NATURA"
    $env:BOT_ZMM0164_OUTPUT_NET_USER = "cmancill"
    $env:BOT_ZMM0164_OUTPUT_NET_PASSWORD = "B3l3n-2304!!"
    python test_smb_mount.py
"""

import sys
import os
from pathlib import Path

# Asegurar que el módulo src está disponible
sys.path.insert(0, str(__file__.rsplit("\\", 1)[0]))

from security.vault_helper import get_secret, mount_smb_windows


def test_mount_smb():
    """Prueba la función de montaje SMB leyendo desde variables de entorno."""
    
    print("\n" + "="*70)
    print("TEST DE MONTAJE SMB/CIFS EN WINDOWS")
    print("="*70)
    
    # Leer parámetros desde variables de entorno (como lo haría main.py)
    UNC_PATH = get_secret("BOT_ZMM0164_OUTPUT_UNC_PATH", r"\\10.156.145.28\Areas\Publico\RPA\Plan Chile\zmm0164")
    DRIVE_LETTER = "Z"
    DOMAIN = get_secret("BOT_ZMM0164_OUTPUT_NET_DOMAIN", "NATURA")
    USERNAME = get_secret("BOT_ZMM0164_OUTPUT_NET_USER", "cmancill")
    PASSWORD = get_secret("BOT_ZMM0164_OUTPUT_NET_PASSWORD", "B3l3n-2304!!")
    
    print("\n📋 PARÁMETROS (desde variables de entorno):")
    print(f"   UNC Path:      {UNC_PATH}")
    print(f"   Unidad:        {DRIVE_LETTER}:")
    print(f"   Dominio:       {DOMAIN}")
    print(f"   Usuario:       {USERNAME}")
    print(f"   Contraseña:    {'*' * len(PASSWORD) if PASSWORD else '[vacía]'}")
    
    # Validar que tenemos credenciales
    if not PASSWORD:
        print("\n❌ ERROR: Falta BOT_ZMM0164_OUTPUT_NET_PASSWORD")
        print("   Establece la variable de entorno:")
        print("   $env:BOT_ZMM0164_OUTPUT_NET_PASSWORD = 'B3l3n-2304!!'")
        return False
    
    # Ejecutar montaje
    print("\n" + "-"*70)
    success = mount_smb_windows(
        unc_path=UNC_PATH,
        drive_letter=DRIVE_LETTER,
        username=USERNAME,
        password=PASSWORD,
        domain=DOMAIN,
        persistent=True
    )
    print("-"*70)
    
    # Verificar montaje
    print("\n🔍 VERIFICACIÓN:")
    drive_path = Path(f"{DRIVE_LETTER}:")
    
    if drive_path.exists():
        print(f"✅ Unidad {DRIVE_LETTER}: existe")
        
        # Intentar listar contenido
        try:
            items = list(drive_path.iterdir())
            print(f"✅ Contenido accesible ({len(items)} items)")
            
            print("\n   Primeros items encontrados:")
            for item in items[:5]:
                item_type = "📁" if item.is_dir() else "📄"
                print(f"      {item_type} {item.name}")
            
            if len(items) > 5:
                print(f"      ... y {len(items) - 5} items más")
        except PermissionError:
            print(f"⚠️  Unidad mapeada pero sin permisos de lectura")
        except Exception as e:
            print(f"⚠️  Error al listar contenido: {e}")
    else:
        print(f"❌ Unidad {DRIVE_LETTER}: no existe")
    
    # Resumen
    print("\n" + "="*70)
    print("📊 RESUMEN")
    print("="*70)
    if success:
        print("✅ MONTAJE EXITOSO")
        print(f"   La unidad {DRIVE_LETTER}: está lista para usar")
    else:
        print("❌ MONTAJE FALLÓ")
        print(f"   Verifica: credenciales, IP del servidor, conectividad de red")
    
    print("\n" + "="*70 + "\n")
    
    return success


if __name__ == "__main__":
    success = test_mount_smb()
    sys.exit(0 if success else 1)
