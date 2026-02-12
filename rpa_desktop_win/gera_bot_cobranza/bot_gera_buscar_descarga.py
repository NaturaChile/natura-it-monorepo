import os
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
RUTA_DESTINO = Path(os.getenv("RUTA_DESTINO"))

async def descargar_reportes_dia_presente():
    fecha_hoy = datetime.now().strftime("%d-%m-%Y")
    archivos_descargados = 0
    ids_descargados = set() # Aquí guardaremos los IDs para no repetir
    
    print(f"🚀 Iniciando Descargador...")
    print(f"📅 Buscando los 2 reportes más recientes de hoy: {fecha_hoy}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 1. Login
        await page.goto(os.getenv("URL_SGI"))
        await page.fill("input#txtUsuario_T2", os.getenv("USUARIO"))
        await page.fill("input#txtSenha_T2", os.getenv("CONTRASENA"))
        await page.click("a#btnLogin_btn")
        
        # 2. Navegar a Descargas
        print("📩 Accediendo a la bandeja de descargas...")
        await page.wait_for_selector('a[href*="8013"].ico_down')
        await page.click('a[href*="8013"].ico_down')
        
        while archivos_descargados < 2:
            await page.wait_for_load_state("networkidle")
            
            # Escaneamos las filas (i=0 es la primera, i=1 es la segunda)
            for i in range(5): 
                fila_selector = f"#ContentPlaceHolder1_exportacoesGrid tr:nth-child({i+2})"
                celdas = await page.query_selector_all(f"{fila_selector} td.grid_celula")
                
                if not celdas: continue

                es_de_hoy = False
                for celda in celdas:
                    texto_celda = (await celda.inner_text()).strip()
                    if texto_celda.startswith(fecha_hoy):
                        es_de_hoy = True
                        break
                
                if es_de_hoy:
                    id_boton = f"ContentPlaceHolder1_exportacoesGrid_baixarButton_{i}_btn_{i}"
                    
                    # VALIDACIÓN CRÍTICA: ¿Ya descargamos este ID antes?
                    if id_boton in ids_descargados:
                        continue # Si ya lo bajamos, pasamos a la siguiente fila

                    botón_bajar = await page.query_selector(f"a#{id_boton}")
                    
                    if botón_bajar:
                        print(f"✅ Nuevo reporte detectado en fila {i+1} (ID: {id_boton}). Bajando...")
                        
                        async with page.expect_download() as download_info:
                            await botón_bajar.click()
                        
                        download = await download_info.value
                        nombre_final = f"{fecha_hoy.replace('-', '')}_Fila{i+1}_{download.suggested_filename}"
                        
                        await download.save_as(RUTA_DESTINO / nombre_final)
                        print(f"💾 Guardado: {nombre_final}")
                        
                        # Marcamos como descargado
                        ids_descargados.add(id_boton)
                        archivos_descargados += 1
                        
                        if archivos_descargados >= 2: break
                    else:
                        print(f"⏳ Archivo en fila {i+1} encontrado, pero el botón 'Bajar' aún no está listo...")

            if archivos_descargados < 2:
                print(f"🔄 Llevamos {archivos_descargados}/2 archivos. Refrescando en 30 segundos...")
                await asyncio.sleep(30)
                # Intentamos usar el botón actualizar del SGI si existe, o recargar página
                try:
                    await page.click("a#ContentPlaceHolder1_atualizarButton_btn", timeout=5000)
                except:
                    await page.reload()
            
        await browser.close()
        print(f"🏁 Finalizado. Se descargaron {archivos_descargados} archivos únicos.")

if __name__ == "__main__":
    asyncio.run(descargar_reportes_dia_presente())
