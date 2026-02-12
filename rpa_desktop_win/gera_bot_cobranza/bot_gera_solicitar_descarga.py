import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError

load_dotenv()

URL_SGI = os.getenv("URL_SGI")
USUARIO = os.getenv("USUARIO")
CONTRASENA = os.getenv("CONTRASENA")

RANGOS = [{"inicio": "15", "fin": "180"}, {"inicio": "181", "fin": "9000"}]

async def solicitar_reportes():
    print("[START] Iniciando Bot Solicitador...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        page = await browser.new_page()
        
        try:
            print(f"[CONNECT] Conectando a {URL_SGI}...")
            await page.goto(URL_SGI, timeout=60000)
            
            # Login
            await page.fill("input#txtUsuario_T2", USUARIO)
            await page.fill("input#txtSenha_T2", CONTRASENA)
            await page.click("a#btnLogin_btn")
            await page.wait_for_load_state("networkidle")
            print("[OK] Sesion iniciada.")

            for rango in RANGOS:
                print(f"\n[RANGO] Procesando rango {rango['inicio']} a {rango['fin']}...")
                
                # Navegación
                await page.click('a:has-text("Recibir")')
                await page.wait_for_timeout(2000)
                await page.click('a.accordionLink:has-text("Control Títulos")')
                await page.wait_for_timeout(2000)
                await page.click('span:has-text("Administrar Deudas")', force=True)
                
                # Filtros de días de atraso
                await page.wait_for_selector("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoInicio_T2")
                await page.fill("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoInicio_T2", rango['inicio'])
                await page.fill("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoFim_T2", rango['fin'])
                
                # Mantener selección de deudas pendientes (si existe el selector)
                pending_selectors = [
                    "input#ContentPlaceHolder1_ControleBuscaTitulo_rbnPendentes",
                    "input#ContentPlaceHolder1_ControleBuscaTitulo_chkPendentes_T2",
                ]
                for sel in pending_selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=1500)
                        await page.click(sel, force=True)
                        print("[OK] Seleccion 'Pendientes' aplicada.")
                        break
                    except:
                        pass  # seguir intentos con otros selectores o continuar si no existe

                print("[SEARCH] Consultando...")
                await page.click("a#ContentPlaceHolder1_ControleBuscaTitulo_btnBuscar_btn")
                
                # Esperar boton Exportar visible
                selector_exportar = "a#ContentPlaceHolder1_ControleBuscaTitulo_btnExportar_btn"
                print("[WAIT] Esperando que el servidor habilite el boton de Exportar...")
                await page.wait_for_selector(selector_exportar, state="visible", timeout=600000)
                
                # Clic en Exportar
                await page.click(selector_exportar)
                print("[EXPORT] Abriendo configuracion de agenda...")

                # Esperar popup/agendamiento
                selector_radio_async = "input#agendamentoExportacao_rbnExcelAssincrono"
                await page.wait_for_selector(selector_radio_async, state="visible", timeout=30000)
                await page.click(selector_radio_async, force=True)

                print("[SCHEDULE] Seleccionando opciones de agendamiento...")

                # Seleccionar ejecución agendada (usar el ID que indicaste)
                selector_exec_agendar = "input#agendamentoExportacao_rbnExecucaoExcelAgendar"
                await page.wait_for_selector(selector_exec_agendar, state="visible", timeout=15000)
                await page.click(selector_exec_agendar, force=True)

                # Calcular fecha de mañana
                fecha_mañana = (datetime.now() + timedelta(days=1)).strftime("%d%m%Y")
                selector_fecha = "input#agendamentoExportacao_dataAgendamentoExcelAssincrono_T2"
                selector_hora = "input#agendamentoExportacao_horarioAgendamentoExcelAssincrono_T2"

                # Rellenar fecha y LA NUEVA HORA DINÁMICA
                await page.fill(selector_fecha, fecha_mañana)
                await page.fill(selector_hora, hora_agendada) # <--- Aquí usa 04:00 o 04:05

                await page.wait_for_timeout(500)  # pequeña espera para asegurar inputs
                print(f"[SCHEDULED] Agendado para {fecha_mañana} a las 04:00")

                # Confirmar agendamiento
                await page.click("a#agendamentoExportacao_okButton_btn")
                
                # Confirmación final
                try:
                    await page.wait_for_selector("a#popupOkButton", state="visible", timeout=15000)
                    await page.click("a#popupOkButton", force=True)
                    print(f"[OK] Rango {rango['inicio']}-{rango['fin']} solicitado.")
                except:
                    print("[WARN] No aparecio el boton OK final, pero se asume exito.")
                
                # Volver a Home
                await page.goto(URL_SGI)
                await page.wait_for_load_state("networkidle")

            print("\n🎉 Proceso terminado. Los archivos aparecerán escalonados mañana.")

        except Exception as e:
            print(f"[ERROR] Error durante la solicitud: {e}")
        finally:
            print("[END] Finalizando...")
            await browser.close()

if __name__ == "__main__":
    asyncio.run(solicitar_reportes())
