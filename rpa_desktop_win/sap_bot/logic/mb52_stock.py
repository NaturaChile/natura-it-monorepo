"""Logica de transaccion MB52 - Stock de almacen."""
import time
import os
from datetime import datetime
import pandas as pd


def ejecutar_mb52(session, centro: str = "4100", almacen: str = "4161", variante: str = "BOTMB52", ruta_destino: str = r"\\10.156.145.28\Publico\RPA\Retail\Stock - Base Tiendas"):
    """
    Ejecuta la transaccion MB52 y exporta el resultado a Excel via portapapeles.
    
    Args:
        session: Sesion SAP activa
        centro: Centro logistico (default: 4100)
        almacen: Almacen (default: 4161)
        variante: Variante de reporte (default: BOTMB52)
        ruta_destino: Ruta UNC donde guardar el archivo Excel (usar \\\\servidor\\... no letras de unidad)
    
    Returns:
        str: Ruta completa del archivo generado
    """
    # Generar nombre de archivo con fecha
    fecha_actual = datetime.now().strftime("%Y.%m.%d")
    nombre_archivo = f"Base Stock Tiendas {fecha_actual}.xlsx"
    
    print(f"[MB52] Centro: {centro}")
    print(f"[MB52] Almacen: {almacen}")
    print(f"[MB52] Variante: {variante}")
    print(f"[MB52] Archivo destino: {ruta_destino}\\{nombre_archivo}")
    
    try:
        # 1. Limpiar pantalla inicial
        print("[MB52] Paso 1: Preparando pantalla...")
        session.findById("wnd[0]/tbar[0]/okcd").text = "MB52"
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(0.5)
        
        # 2. Llenar campos de seleccion
        print("[MB52] Paso 2: Llenando campos de seleccion...")
        session.findById("wnd[0]/usr/ctxtWERKS-LOW").text = centro
        session.findById("wnd[0]/usr/ctxtLGORT-HIGH").text = "4195"
        session.findById("wnd[0]/usr/ctxtLGORT-LOW").text = almacen
        session.findById("wnd[0]/usr/ctxtP_VARI").text = variante
        session.findById("wnd[0]/usr/ctxtP_VARI").setFocus()
        session.findById("wnd[0]/usr/ctxtP_VARI").caretPosition = len(variante)
        time.sleep(0.3)
        
        # 3. Ejecutar con Enter
        print("[MB52] Paso 3: Ejecutando variante...")
        session.findById("wnd[0]").sendVKey(0)
        time.sleep(1)
        
        # 4. Ejecutar reporte (F8)
        print("[MB52] Paso 4: Ejecutando reporte (F8)...")
        session.findById("wnd[0]/tbar[1]/btn[8]").press()
        time.sleep(3)  # Esperar a que cargue el reporte
        
        # 5. Exportar menu
        print("[MB52] Paso 5: Iniciando exportacion...")
        session.findById("wnd[0]/tbar[1]/btn[45]").press()
        time.sleep(1)
        
        # 6. Seleccionar formato de exportacion (Portapapeles)
        print("[MB52] Paso 6: Seleccionando formato Portapapeles...")
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[4,0]").select()
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[4,0]").setFocus()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        time.sleep(2)
        
        # 7. Leer portapapeles y procesar datos
        print("[MB52] Paso 7: Leyendo datos del portapapeles...")
        import win32clipboard
        
        win32clipboard.OpenClipboard()
        try:
            clipboard_data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        finally:
            win32clipboard.CloseClipboard()
        
        print(f"[MB52] Datos recibidos del portapapeles: {len(clipboard_data)} caracteres")
        
        # 8. Procesar datos y crear DataFrame
        print("[MB52] Paso 8: Procesando y limpiando datos...")
        lines = clipboard_data.strip().split('\n')
        print(f"[MB52] Total lineas en portapapeles: {len(lines)}")
        
        # Estructura del portapapeles SAP:
        # Linea 0: ---- separador de guiones
        # Linea 1: | Col1 | Col2 | ... | (headers)
        # Linea 2: ---- separador de guiones
        # Linea 3+: | dato1 | dato2 | ... | (datos)
        
        # Separar lineas de datos de lineas de guiones
        header_line = None
        data_lines = []
        
        for line in lines:
            stripped = line.strip()
            # Ignorar lineas vacias o que sean solo guiones
            if not stripped or stripped.replace('-', '').replace('|', '').strip() == '':
                continue
            # Si contiene | y no es solo guiones, es una linea de datos
            if '|' in stripped:
                if header_line is None:
                    header_line = stripped
                else:
                    data_lines.append(stripped)
        
        if header_line is None:
            raise ValueError("No se encontro linea de encabezados en el portapapeles")
        
        # Extraer headers (separar por | y limpiar)
        headers = [col.strip() for col in header_line.split('|')]
        # Eliminar elementos vacios al inicio y final
        headers = [h for h in headers if h]
        print(f"[MB52] Columnas detectadas ({len(headers)}): {headers[:5]}...")
        
        # Procesar filas de datos
        data_rows = []
        for line in data_lines:
            # Separar por | y limpiar espacios
            row = [col.strip() for col in line.split('|')]
            # Eliminar elementos vacios al inicio y final
            row = [r for r in row if r != '']
            
            if len(row) == len(headers):
                data_rows.append(row)
            elif len(row) > 0:
                print(f"[MB52] [WARN] Fila con {len(row)} cols (esperadas {len(headers)}), ajustando...")
                # Ajustar fila si es necesario
                if len(row) > len(headers):
                    data_rows.append(row[:len(headers)])
                else:
                    # Rellenar con vacios
                    row.extend([''] * (len(headers) - len(row)))
                    data_rows.append(row)
        
        print(f"[MB52] Filas de datos procesadas: {len(data_rows)}")
        
        # Crear DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # 9. Guardar como Excel
        print("[MB52] Paso 9: Guardando archivo Excel...")

        def resolve_drive_to_unc(path):
            """Si path comienza con una letra de unidad mapeada (X:\\...), intenta resolverla usando `net use` y devuelve ruta UNC."""
            try:
                if len(path) >= 2 and path[1] == ':':
                    drive = path[0].upper() + ':'
                    # Ejecutar `net use` y buscar mapping
                    import subprocess
                    result = subprocess.run(['net', 'use'], capture_output=True, text=True, shell=True)
                    out = result.stdout
                    for line in out.splitlines():
                        if drive in line:
                            parts = line.split()
                            for p in parts:
                                if p.startswith('\\\\') or p.startswith('\\'):
                                    unc = p.rstrip('\\')
                                    remainder = path[2:].lstrip('\\/')
                                    # Construir camino UNC
                                    return os.path.join(unc, remainder)
                return path
            except Exception as e:
                print(f"[MB52] [WARN] No se pudo resolver unidad a UNC: {str(e)}")
                return path

        ruta_destino_original = ruta_destino
        ruta_destino = resolve_drive_to_unc(ruta_destino_original)
        print(f"[MB52] Ruta destino original: {ruta_destino_original}")
        print(f"[MB52] Ruta destino usada: {ruta_destino}")

        ruta_completa = os.path.join(ruta_destino, nombre_archivo)

        # Verificar que la carpeta de red es accesible
        print(f"[MB52] Verificando acceso a: {ruta_destino}")
        if not os.path.exists(ruta_destino):
            print(f"[MB52] Carpeta no existe, intentando crear...")
            os.makedirs(ruta_destino, exist_ok=True)

        df.to_excel(ruta_completa, index=False, engine='openpyxl')

        # 10. Verificar que el archivo se guardo correctamente
        print("[MB52] Paso 10: Verificando archivo guardado...")
        time.sleep(2)  # Dar tiempo a que se escriba el archivo

        if os.path.exists(ruta_completa):
            file_size = os.path.getsize(ruta_completa)
            print(f"[MB52] [SUCCESS] Archivo verificado: {ruta_completa}")
            print(f"[MB52] [SUCCESS] Tamano archivo: {file_size:,} bytes")
            print(f"[MB52] [SUCCESS] Total filas: {len(df)}, Total columnas: {len(df.columns)}")
        else:
            raise Exception(f"El archivo no se encontro despues de guardar: {ruta_completa}")

        return ruta_completa
        
    except Exception as e:
        print(f"[MB52] [ERROR] Error durante ejecucion: {str(e)}")
        raise
