import os
import asyncio
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

try:
    from dotenv import load_dotenv
    load_dotenv()  # Carga .env local si existe (desarrollo), en servidor usa env vars del sistema
except ImportError:
    pass  # En producción no se requiere python-dotenv

RUTA_DESTINO = Path(os.getenv("RUTA_DESTINO", str(Path(__file__).resolve().parent / "Descarga")))
RUTA_DESTINO.mkdir(parents=True, exist_ok=True)

async def descargar_reportes_listos():
    # Obtenemos la fecha de hoy en formato DD-MM-YYYY (coincidiendo con tu celda)
    fecha_hoy = datetime.now().strftime("%d-%m-%Y")
    
    print(f"🚀 Iniciando Descargador...")
    print(f"🔍 Buscando archivos que comiencen con la fecha: {fecha_hoy}")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 1. Login
        await page.goto(os.getenv("URL_SGI"))
        await page.fill("input#txtUsuario_T2", os.getenv("USUARIO"))
        await page.fill("input#txtSenha_T2", os.getenv("CONTRASENA"))
        await page.click("a#btnLogin_btn")
        
        # 2. Ir a sección de descargas
        print("📩 Yendo a la sección de descargas...")
        await page.wait_for_selector('a[href*="8013"].ico_down')
        await page.click('a[href*="8013"].ico_down')
        await page.wait_for_load_state("networkidle")

        # 3. Validar y Descargar
        # Revisamos las filas de la tabla (SGI usa tablas estándar de ASP.NET)
        for i in range(10): # Aumentamos rango para asegurar
            try:
                # Localizamos la fila i (sumamos 2 por el encabezado y el índice 1)
                fila_selector = f"#ContentPlaceHolder1_exportacoesGrid tr:nth-child({i+2})"
                
                # Buscamos la celda de fecha con la clase 'grid_celula' y alineación 'right'
                # Según tu HTML, buscaremos el texto directamente en las celdas de esa fila
                celdas = await page.query_selector_all(f"{fila_selector} td.grid_celula")
                
                if not celdas:
                    continue

                # Usualmente la fecha es la última o penúltima celda con esa clase
                # Vamos a recorrer las celdas de la fila para encontrar la que tiene la fecha
                encontrado_hoy = False
                for celda in celdas:
                    texto_celda = (await celda.inner_text()).strip()
                    
                    # Validamos si la celda comienza con DD-MM-YYYY
                    if texto_celda.startswith(fecha_hoy):
                        encontrado_hoy = True
                        print(f"✅ Fila {i+1} coincide: {texto_celda}")
                        break
                
                if encontrado_hoy:
                    selector_bajar = f"a#ContentPlaceHolder1_exportacoesGrid_baixarButton_{i}_btn_{i}"
                    
                    if await page.query_selector(selector_bajar):
                        print(f"📥 Descargando reporte de hoy...")
                        async with page.expect_download() as download_info:
                            await page.click(selector_bajar)
                        
                        download = await download_info.value
                        path_final = RUTA_DESTINO / f"{fecha_hoy.replace('-', '')}_{download.suggested_filename}"
                        await download.save_as(path_final)
                        print(f"💾 Guardado: {path_final}")
                    else:
                        print(f"⏳ El archivo existe pero el botón 'Bajar' no está visible aún.")
                
            except Exception as e:
                # Si falla al buscar una fila, es que llegamos al final de la lista
                break

        await browser.close()
        print("🏁 Proceso de descarga finalizado.")

if __name__ == "__main__":
    asyncio.run(descargar_reportes_listos())