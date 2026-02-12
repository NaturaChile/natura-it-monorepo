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
    ids_descargados = set() # Memoria para no descargar el mismo archivo dos veces
    
    print(f"🚀 Iniciando Descargador...")
    print(f"📅 Buscando los 2 reportes más recientes de hoy: {fecha_hoy}")
    
    async with async_playwright() as p:
        # Lanzamos el navegador
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        # 1. Login
        try:
            print("🔑 Iniciando sesión...")
            await page.goto(os.getenv("URL_SGI"), timeout=60000)
            await page.fill("input#txtUsuario_T2", os.getenv("USUARIO"))
            await page.fill("input#txtSenha_T2", os.getenv("CONTRASENA"))
            await page.click("a#btnLogin_btn")
        except Exception as e:
            print(f"❌ Error en Login: {e}")
            await browser.close()
            return

        # 2. Navegar a Descargas
        print("📩 Accediendo a la bandeja de descargas...")
        try:
            await page.wait_for_selector('a[href*="8013"].ico_down', timeout=30000)
            await page.click('a[href*="8013"].ico_down')
        except Exception:
            print("⚠️ No se encontró el icono de descargas o tardó mucho.")
        
        # Bucle principal de búsqueda
        while archivos_descargados < 2:
            try:
                await page.wait_for_load_state("networkidle")
            except:
                pass # Continuar si networkidle da timeout
            
            # Escaneamos las primeras 5 filas (i=0 a i=4)
            for i in range(5): 
                fila_selector = f"#ContentPlaceHolder1_exportacoesGrid tr:nth-child({i+2})"
                celdas = await page.query_selector_all(f"{fila_selector} td.grid_celula")
                
                if not celdas: continue

                # Validar fecha
                es_de_hoy = False
                for celda in celdas:
                    texto_celda = (await celda.inner_text()).strip()
                    if texto_celda.startswith(fecha_hoy):
                        es_de_hoy = True
                        break
                
                if es_de_hoy:
                    id_boton = f"ContentPlaceHolder1_exportacoesGrid_baixarButton_{i}_btn_{i}"
                    
                    # VALIDACIÓN CRÍTICA: Si ya lo bajamos, saltamos
                    if id_boton in ids_descargados:
                        continue 

                    botón_bajar = await page.query_selector(f"a#{id_boton}")
                    
                    if botón_bajar:
                        print(f"✅ Nuevo reporte detectado en fila {i+1}. Intentando descargar...")
                        
                        # --- CORRECCIÓN TIMEOUT ---
                        try:
                            # Aumentamos timeout a 120000ms (2 minutos)
                            async with page.expect_download(timeout=120000) as download_info:
                                # Usamos force=True para asegurar el clic
                                await botón_bajar.click(force=True)
                            
                            download = await download_info.value
                            
                            # Construimos nombre único
                            nombre_final = f"{fecha_hoy.replace('-', '')}_Fila{i+1}_{download.suggested_filename}"
                            
                            # Asegurar que la carpeta existe
                            RUTA_DESTINO.mkdir(parents=True, exist_ok=True)

                            await download.save_as(RUTA_DESTINO / nombre_final)
                            print(f"💾 EXITO: Guardado como {nombre_final}")
                            
                            # Marcamos como descargado
                            ids_descargados.add(id_boton)
                            archivos_descargados += 1
                            
                            if archivos_descargados >= 2: break
                        
                        except Exception as e:
                            print(f"⚠️ Error descargando fila {i+1} (Posible timeout del servidor): {e}")
                            # No lo agregamos a 'ids_descargados' para reintentarlo en la siguiente vuelta
                            
                    else:
                        print(f"⏳ Fila {i+1} es de hoy, pero el botón 'Bajar' aún no aparece.")

            # Si aún no tenemos los 2 archivos, esperamos y refrescamos
            if archivos_descargados < 2:
                print(f"🔄 Progreso: {archivos_descargados}/2. Esperando 30s para refrescar...")
                await asyncio.sleep(30)
                try:
                    # Intentar botón de refrescar del SGI o recargar página
                    if await page.query_selector("a#ContentPlaceHolder1_atualizarButton_btn"):
                        await page.click("a#ContentPlaceHolder1_atualizarButton_btn")
                    else:
                        await page.reload()
                except:
                    await page.reload()
            
        await browser.close()
        print(f"🏁 Proceso Finalizado. Se descargaron {archivos_descargados} archivos.")

if __name__ == "__main__":
    asyncio.run(descargar_reportes_dia_presente())
