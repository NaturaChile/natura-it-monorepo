import os
import sys
import pandas as pd

# Setup de rutas para Monorepo
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(current_dir, "../..")))

from core_shared.security.vault import Vault
from src.adapters.sftp_client import SftpClient, SftpConfig

def explore_waveconfirm_folder():
    """Script de exploración para analizar archivos de Wave Confirm"""
    
    print("="*70)
    print(" EXPLORADOR DE ARCHIVOS - WAVE CONFIRM")
    print("="*70)
    
    # Configuración con las mismas credenciales pero ruta diferente
    sftp_cfg = SftpConfig(
        host=Vault.get_secret("EWM_SFTP_HOST"),
        user=Vault.get_secret("EWM_SFTP_USER"),
        password=Vault.get_secret("EWM_SFTP_PASS"),
        remote_path="/EWM/ewm_to_gera/waveconfirm/02_old"  # NUEVA RUTA
    )
    
    sftp_client = SftpClient(sftp_cfg)
    
    # Directorio temporal para muestras
    sample_dir = os.path.join(current_dir, "samples_waveconfirm")
    if not os.path.exists(sample_dir):
        os.makedirs(sample_dir)
    
    print(f"\n1. Listando archivos en: {sftp_cfg.remote_path}")
    print("-"*70)
    
    try:
        files = sftp_client.list_files()
        
        if not files:
            print("No se encontraron archivos en la carpeta.")
            return
        
        print(f"Total archivos encontrados: {len(files)}")
        print("\nPrimeros 10 archivos:")
        for i, f in enumerate(files[:10], 1):
            size_kb = f.st_size / 1024
            print(f"  {i}. {f.filename} ({size_kb:.2f} KB)")
        
        # Descargar primeros 3 archivos como muestra
        print(f"\n2. Descargando primeros 3 archivos de muestra...")
        print("-"*70)
        
        samples_to_download = min(3, len(files))
        downloaded = []
        
        for i in range(samples_to_download):
            file_attr = files[i]
            filename = file_attr.filename
            
            print(f"  Descargando: {filename}...", end=" ")
            if sftp_client.download_file(filename, sample_dir):
                print("OK")
                downloaded.append(os.path.join(sample_dir, filename))
            else:
                print("FALLO")
        
        # Analizar estructura de los archivos descargados
        print(f"\n3. Analizando estructura de archivos...")
        print("-"*70)
        
        for filepath in downloaded:
            print(f"\n--- Archivo: {os.path.basename(filepath)} ---")
            analyze_file_structure(filepath)
        
        print(f"\n{'='*70}")
        print(f"Archivos de muestra guardados en: {sample_dir}")
        print("Revisa los archivos y comparte la estructura para crear el pipeline.")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

def analyze_file_structure(filepath):
    """Analiza la estructura de un archivo"""
    try:
        # Intentar leer como CSV con diferentes delimitadores
        delimiters = ['\t', ';', ',', '|']
        
        for delim in delimiters:
            try:
                df = pd.read_csv(filepath, sep=delim, nrows=5, encoding='utf-8')
                if len(df.columns) > 1:
                    print(f"  Delimitador detectado: '{delim}'")
                    print(f"  Columnas ({len(df.columns)}): {list(df.columns)}")
                    print(f"  Primeras filas:")
                    print(df.head(2).to_string(index=False))
                    return
            except:
                continue
        
        # Si no funcionó como CSV, mostrar las primeras líneas raw
        print("  No se pudo parsear como CSV. Primeras líneas raw:")
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for i, line in enumerate(f):
                if i >= 5:
                    break
                print(f"    Línea {i+1}: {line.strip()[:100]}")
    
    except Exception as e:
        print(f"  Error analizando: {e}")

if __name__ == "__main__":
    explore_waveconfirm_folder()
