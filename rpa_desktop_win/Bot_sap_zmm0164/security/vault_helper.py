"""Helper para leer secretos desde variables de entorno.

Sigue el patrón de seguridad centralizado del proyecto.
Las credenciales se leen desde variables de entorno (ej: desde GitHub SAP_Jorge).
"""
import os
import subprocess
from core_shared.security.vault import Vault


def get_secret(key: str, default: str = None) -> str:
    """Obtiene un secreto desde variables de entorno.
    
    Args:
        key: Nombre de la variable de entorno
        default: Valor por defecto si no se encuentra
        
    Returns:
        Valor del secreto o default
    """
    # Primero intenta obtener del Vault centralizado
    val = Vault.get_secret(key, default=None)
    if val:
        return val
    # Si no, intenta obtener del entorno directamente
    val = os.getenv(key)
    if val:
        return val
    # Si no encuentra, retorna el default o cadena vacía
    if default is not None:
        return default
    return ""


def mount_smb_windows(unc_path: str, drive_letter: str, username: str, password: str, 
                     domain: str = "NATURA", persistent: bool = True) -> bool:
    """Monta una compartida SMB en Windows usando net use.
    
    Lee credenciales desde variables de entorno (SAP_Jorge en GitHub).
    
    Args:
        unc_path: Ruta UNC (ej: \\10.156.145.28\Publico\RPA\Plan Chile\zmm0164)
        drive_letter: Letra de unidad (ej: "Z")
        username: Usuario Windows (de variable de entorno)
        password: Contraseña (de variable de entorno como secret)
        domain: Dominio (default: NATURA)
        persistent: Si True, mantiene el mapeo tras reiniciar
        
    Returns:
        True si se monta correctamente, False en caso contrario
    """
    try:
        print(f"\n📦 Montaje SMB/CIFS en Windows")
        print(f"   UNC Path: {unc_path}")
        print(f"   Unidad: {drive_letter}:")
        print(f"   Usuario: {domain}\\{username}")
        
        # Desconectar si ya existe la unidad
        print(f"\n[1/2] Desconectando unidad {drive_letter}: si existe...")
        try:
            subprocess.run(
                ["net", "use", f"{drive_letter}:", "/delete", "/y"],
                capture_output=True,
                check=False,
                timeout=10
            )
            print(f"     ✓ Limpieza completada")
        except Exception:
            print(f"     ℹ️  Sin conexión anterior (primera vez)")
        
        # Mapear unidad SMB con credenciales desde variables de entorno
        print(f"\n[2/2] Montando unidad SMB con 'net use'...")
        
        mount_cmd = [
            "net", "use", f"{drive_letter}:",
            unc_path,
            password,
            f"/user:{domain}\\{username}"
        ]
        
        if persistent:
            mount_cmd.append("/persistent:yes")
        else:
            mount_cmd.append("/persistent:no")
        
        result = subprocess.run(
            mount_cmd,
            capture_output=True,
            text=True,
            check=False,
            timeout=30
        )
        
        if result.returncode == 0:
            print(f"\n✅ MONTAJE EXITOSO")
            print(f"   {drive_letter}: → {unc_path}")
            print(f"   Persistente: {persistent}")
            return True
        else:
            print(f"\n❌ ERROR EN MONTAJE SMB")
            print(f"   Código de error: {result.returncode}")
            print(f"   Mensaje: {result.stderr.strip()}")
            
            # Códigos de error comunes en Windows
            error_codes = {
                67: "Error 67: No se encuentra el nombre de red especificado (verificar IP/servidor)",
                1326: "Error 1326: La credencial de usuario y contraseña es incorrecta",
                5: "Error 5: Acceso denegado",
                85: "Error 85: La unidad ya está en uso",
            }
            
            if result.returncode in error_codes:
                print(f"   Explicación: {error_codes[result.returncode]}")
            
            return False
            
    except subprocess.TimeoutExpired:
        print(f"❌ Timeout: El comando tardó más de 30 segundos")
        return False
    except Exception as e:
        print(f"❌ Excepción durante montaje: {e}")
        return False
