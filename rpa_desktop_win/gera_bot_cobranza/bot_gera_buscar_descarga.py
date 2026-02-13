import os
import asyncio
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

load_dotenv()
RUTA_DESTINO = Path(__file__).resolve().parent / "descargas"
RUTA_DESTINO.mkdir(exist_ok=True)

DOWNLOAD_TIMEOUT = 60_000        # ms para esperar el evento download
MAX_REINTENTOS_DESCARGA = 3      # reintentos por archivo


async def _intentar_descarga(page, id_boton, intento=1):
    """Intenta hacer click en el botón y esperar el evento download.
    Retorna el objeto download o None si falla."""
    # Re-buscar el botón en el DOM actual (puede haber cambiado tras postback)
    boton = await page.query_selector(f"a#{id_boton}")
    if not boton:
        print(f"   ⚠️  Botón {id_boton} no encontrado en intento {intento}.")
        return None
    try:
        async with page.expect_download(timeout=DOWNLOAD_TIMEOUT) as download_info:
            await boton.click()
        return await download_info.value
    except PlaywrightTimeout:
        print(f"   ⚠️  Timeout descarga en intento {intento}/{MAX_REINTENTOS_DESCARGA}.")
        return None


async def descargar_reportes_dia_presente():
    fecha_hoy = datetime.now().strftime("%d-%m-%Y")
    archivos_descargados = 0
    ids_descargados = set()  # Aquí guardaremos los IDs para no repetir

    print(f"🚀 Iniciando Descargador...")
    print(f"📅 Buscando los 2 reportes más recientes de hoy: {fecha_hoy}")

    async with async_playwright() as p:
        # Lanzamos el navegador
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(accept_downloads=True)
        page = await context.new_page()

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
            await asyncio.sleep(2)  # Dejar que el grid se estabilice

            # Escaneamos las filas (i=0 es la primera, i=1 es la segunda)
            for i in range(5):
                fila_selector = f"#ContentPlaceHolder1_exportacoesGrid tr:nth-child({i+2})"
                celdas = await page.query_selector_all(f"{fila_selector} td.grid_celula")

                if not celdas:
                    continue

                # Validar fecha
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
                        continue  # Si ya lo bajamos, pasamos a la siguiente fila

                    print(f"✅ Nuevo reporte detectado en fila {i+1} (ID: {id_boton}). Bajando...")

                    download = None
                    for intento in range(1, MAX_REINTENTOS_DESCARGA + 1):
                        download = await _intentar_descarga(page, id_boton, intento)
                        if download:
                            break
                        # Esperar y estabilizar la página antes de reintentar
                        await asyncio.sleep(5)
                        await page.wait_for_load_state("networkidle")

                    if download:
                        nombre_final = f"{fecha_hoy.replace('-', '')}_Fila{i+1}_{download.suggested_filename}"
                        await download.save_as(RUTA_DESTINO / nombre_final)
                        print(f"💾 Guardado: {nombre_final}")

                        # Marcamos como descargado
                        ids_descargados.add(id_boton)
                        archivos_descargados += 1

                        # Esperar a que la página se estabilice después de la descarga
                        await asyncio.sleep(3)
                        await page.wait_for_load_state("networkidle")

                        if archivos_descargados >= 2:
                            break
                    else:
                        print(f"❌ No se pudo descargar fila {i+1} tras {MAX_REINTENTOS_DESCARGA} intentos.")
                else:
                    continue

            # Si aún no tenemos los 2 archivos, esperamos y refrescamos
            if archivos_descargados < 2:
                print(f"🔄 Progreso: {archivos_descargados}/2. Esperando 30s para refrescar...")
                await asyncio.sleep(30)
                try:
                    await page.click("a#ContentPlaceHolder1_atualizarButton_btn", timeout=5000)
                except Exception:
                    await page.reload()

        await browser.close()
        print(f"🏁 Proceso Finalizado. Se descargaron {archivos_descargados} archivos.")

if __name__ == "__main__":
    asyncio.run(descargar_reportes_dia_presente())
