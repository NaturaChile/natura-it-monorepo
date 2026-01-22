"""Logica de transaccion MB52 - Stock de almacen."""
import time
from datetime import datetime


def ejecutar_mb52(session, centro: str = "4100", almacen: str = "4161", variante: str = "BOTMB52", ruta_destino: str = r"Y:\Publico\RPA\Retail\Stock - Base Tiendas"):
    """
    Ejecuta la transaccion MB52 y exporta el resultado a Excel.
    
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
        
        # 5. Exportar a Excel
        print("[MB52] Paso 5: Iniciando exportacion...")
        session.findById("wnd[0]/tbar[1]/btn[45]").press()
        time.sleep(1)
        
        # 6. Seleccionar formato de exportacion (Excel)
        print("[MB52] Paso 6: Seleccionando formato Excel...")
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]").select()
        session.findById("wnd[1]/usr/subSUBSCREEN_STEPLOOP:SAPLSPO5:0150/sub:SAPLSPO5:0150/radSPOPLI-SELFLAG[1,0]").setFocus()
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        time.sleep(1)
        
        # 7. Definir ruta y nombre de archivo
        print("[MB52] Paso 7: Configurando ruta de destino...")
        session.findById("wnd[1]/usr/ctxtDY_PATH").text = ruta_destino
        session.findById("wnd[1]/usr/ctxtDY_FILENAME").text = nombre_archivo
        time.sleep(0.3)
        
        # 8. Confirmar guardado
        print("[MB52] Paso 8: Guardando archivo...")
        session.findById("wnd[1]/tbar[0]/btn[0]").press()
        
        # 9. Esperar descarga - 1 minuto inicial luego verificar
        print("[MB52] Paso 9: Esperando descarga (1 minuto inicial)...")
        time.sleep(60)  # Esperar 1 minuto inicial
        
        # Verificar si ya termino la descarga
        max_intentos = 5  # Maximo 5 intentos adicionales (6 minutos total)
        descarga_completa = False
        
        for intento in range(1, max_intentos + 1):
            try:
                statusbar_text = session.findById("wnd[0]/sbar/pane[0]").text
                print(f"[MB52] Intento {intento}: Status = '{statusbar_text}'")
                
                if "1160" in statusbar_text:
                    print("[MB52] [SUCCESS] Descarga completada - code page 1160 detectado")
                    descarga_completa = True
                    break
                else:
                    if intento < max_intentos:
                        print(f"[MB52] Descarga en progreso, esperando 1 minuto mas...")
                        time.sleep(60)  # Esperar otro minuto
                    
            except Exception as e:
                print(f"[MB52] Intento {intento}: Error leyendo barra de estado: {str(e)}")
                if intento < max_intentos:
                    time.sleep(60)
        
        if not descarga_completa:
            print("[MB52] [WARN] No se detecto confirmacion de descarga despues de 6 minutos")
            print("[MB52] [WARN] Verificar archivo manualmente")
        
        
        ruta_completa = f"{ruta_destino}\\{nombre_archivo}"
        print(f"[MB52] [SUCCESS] Archivo exportado: {ruta_completa}")
        
        return ruta_completa
        
    except Exception as e:
        print(f"[MB52] [ERROR] Error durante ejecucion: {str(e)}")
        raise
