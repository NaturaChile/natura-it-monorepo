import os
import sys
import subprocess
import shutil
from pathlib import Path

"""
Script temporal de diagnóstico (NO mantener en producción).

Acciones:
- Mapea el share usando `net use` con credenciales embebidas (solo para pruebas).
- Lista las primeras carpetas del subpath objetivo.
- Crea un archivo de prueba en Descargas y lo mueve al share.

ADVERTENCIA: Este archivo contiene credenciales en texto plano. Elimina/ignora después
de las pruebas.
"""

# --- CREDENCIALES (ejemplo provisto) ---
# Usar las credenciales/host proporcionadas en el ejemplo
SERVER = "10.156.145.28"
SHARE = "areas"
SUB_RUTA = r"Publico\RPA\Retail\Stock - Base Tiendas"

DOMAIN = "NATURA"
USER = "robotch_fin"
PASS = "Natura@bot2025/"


def unc_root():
    return fr"\\{SERVER}\{SHARE}"


def unc_full():
    return str(Path(unc_root()) / Path(SUB_RUTA))


def net_use_map(root, password, domain, user):
    # Construir comando con comillas para manejar espacios
    user_full = f"{domain}\\{user}" if domain else user
    cmd = f'net use "{root}" "{password}" /user:"{user_full}" /persistent:no'
    print(f"[DIAG] Ejecutando: {cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(f"[DIAG] returncode={result.returncode}")
    if result.stdout:
        print("[DIAG] stdout:\n" + result.stdout)
    if result.stderr:
        print("[DIAG] stderr:\n" + result.stderr)
    return result.returncode == 0


def list_first_folders(path, limit=10):
    p = Path(path)
    if not p.exists():
        print(f"[DIAG] Ruta no existe o inaccesible: {path}")
        return []
    try:
        dirs = [x.name for x in p.iterdir() if x.is_dir()]
        print(f"[DIAG] Primeras {min(limit,len(dirs))} carpetas en {path}:")
        for d in dirs[:limit]:
            print(" - " + d)
        return dirs
    except PermissionError:
        print("[DIAG] PermissionError al listar carpetas. Credenciales o permisos insuficientes.")
        return []
    except Exception as e:
        print(f"[DIAG] Error listando carpetas: {e}")
        return []


def create_test_file(path: Path):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write('prueba de movimiento desde bot\n')
        print(f"[DIAG] Archivo de prueba creado: {path}")
        return True
    except Exception as e:
        print(f"[DIAG] No se pudo crear archivo de prueba: {e}")
        return False


def move_file(src: Path, dst: Path):
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"[DIAG] Archivo movido a: {dst}")
        return True
    except Exception as e:
        import traceback
        print(f"[DIAG] Error moviendo archivo: {e}")
        traceback.print_exc()
        return False


def main():
    print("[DIAG] Inicio diagnóstico de acceso SMB usando credenciales embebidas")
    root = unc_root()
    full = unc_full()

    print(f"[DIAG] Intentando mapear {root} con usuario {DOMAIN}\\{USER}")
    ok_map = net_use_map(root, PASS, DOMAIN, USER)
    if not ok_map:
        print("[DIAG] net use devolvió error. Continuaremos para intentar diagnosticar más detalles.")

    # 2) Listar primeras carpetas en target
    print(f"[DIAG] Comprobando existencia de ruta UNC completa: {full}")
    dirs = list_first_folders(full, limit=10)

    # Si no pudimos listar carpetas, salir con error para abortar el workflow
    if not dirs:
        print("[DIAG] No se pudo listar carpetas en el share. Abortando con código 1.")
        # Imprimir estado de net use adicional
        try:
            r = subprocess.run('net use', shell=True, capture_output=True, text=True)
            print('[DIAG] Salida `net use`:\n' + r.stdout)
            if r.stderr:
                print('[DIAG] `net use` stderr:\n' + r.stderr)
        except Exception as e:
            print(f"[DIAG] No se pudo ejecutar 'net use' para debug: {e}")
        return 1

    # 3) Crear archivo de prueba en el directorio actual y moverlo
    cwd = Path.cwd()
    test_file = cwd / 'prueba.txt'
    print(f"[DIAG] Creando archivo de prueba en: {test_file}")
    if not create_test_file(test_file):
        print('[DIAG] No se pudo crear archivo de prueba; abortando movimiento')
        return 2

    dest = Path(full) / test_file.name
    print(f"[DIAG] Intentando mover {test_file} -> {dest}")
    moved = move_file(test_file, dest)
    if not moved:
        print('[DIAG] Movimiento falló. Revisa permisos o conectividad. Saldremos con código 3')
        return 3
    else:
        print('[DIAG] Movimiento completado correctamente')
        return 0


if __name__ == '__main__':
    code = main()
    sys.exit(code)
