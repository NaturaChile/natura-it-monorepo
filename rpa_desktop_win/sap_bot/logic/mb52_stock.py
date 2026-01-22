"""Logica de transaccion MB52 - Stock de almacen."""
import time
import os
from datetime import datetime
import pandas as pd


def ejecutar_mb52(session, centro: str = "4100", almacen: str = "4161", variante: str = "BOTMB52", ruta_destino: str = r"Y:\Publico\RPA\Retail\Stock - Base Tiendas"):
    """
    Ejecuta la transaccion MB52 y exporta el resultado a Excel via portapapeles.
    
    Args:
        session: Sesion SAP activa
        centro: Centro logistico (default: 4100)
        almacen: Almacen (default: 4161)
        variante: Variante de reporte (default: BOTMB52)
        ruta_destino: Ruta donde guardar el archivo Excel
    
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
        
        # Filtrar lineas de guiones (separadores visuales)
        lines = [line for line in lines if not line.strip().startswith('---')]
        
        if len(lines) < 2:
            raise ValueError("Datos insuficientes en el portapapeles")
        
        # Primera linea es el encabezado (separado por |)
        header_line = lines[0]
        headers = [col.strip() for col in header_line.split('|') if col.strip()]
        print(f"[MB52] Columnas detectadas: {len(headers)} - {headers}")
        
        # Resto son datos
        data_rows = []
        for line in lines[1:]:
            if line.strip() and '|' in line:
                # Separar por | y limpiar espacios
                row = [col.strip() for col in line.split('|') if col.strip() != '']
                # Solo agregar si tiene el numero correcto de columnas
                if len(row) == len(headers):
                    data_rows.append(row)
                elif len(row) > 0:
                    # Intentar ajustar si hay columnas de mas/menos
                    print(f"[MB52] [WARN] Fila con {len(row)} columnas (esperadas {len(headers)}): {row[:3]}...")
        
        print(f"[MB52] Filas de datos procesadas: {len(data_rows)}")
        
        # Crear DataFrame
        df = pd.DataFrame(data_rows, columns=headers)
        
        # 9. Guardar como Excel
        print("[MB52] Paso 9: Guardando archivo Excel...")
        ruta_completa = os.path.join(ruta_destino, nombre_archivo)
        
        # Crear directorio si no existe
        os.makedirs(ruta_destino, exist_ok=True)
        
        df.to_excel(ruta_completa, index=False, engine='openpyxl')
        
        print(f"[MB52] [SUCCESS] Archivo exportado: {ruta_completa}")
        print(f"[MB52] [SUCCESS] Total filas: {len(df)}, Total columnas: {len(df.columns)}")
        
        return ruta_completa
        
    except Exception as e:
        print(f"[MB52] [ERROR] Error durante ejecucion: {str(e)}")
        raise
