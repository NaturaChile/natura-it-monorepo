import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from playwright.async_api import async_playwright, TimeoutError

# 1. Cargar configuración desde .env
load_dotenv()

URL_SGI = os.getenv("URL_SGI")
USUARIO = os.getenv("USUARIO")
CONTRASENA = os.getenv("CONTRASENA")

# Definición de los dos rangos solicitados
RANGOS = [{"inicio": "15", "fin": "180"}, {"inicio": "181", "fin": "9000"}]

async def solicitar_reportes():
    print("🚀 Iniciando Bot Solicitador (Corrección de formato de hora)...")
    async with async_playwright() as p:
        # slow_mo ayuda a que el sistema procese cada tecla enviada
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        page = await browser.new_page()
        
        try:
            print(f"🔗 Conectando a {URL_SGI}...")
            await page.goto(URL_SGI, timeout=60000)
            
            # Proceso de Login
            await page.fill("input#txtUsuario_T2", USUARIO)
            await page.fill("input#txtSenha_T2", CONTRASENA)
            await page.click("a#btnLogin_btn")
            await page.wait_for_load_state("networkidle")
            print("✅ Sesión iniciada.")

            # --- LÓGICA DE HORA ESCALONADA ---
            hora_base = datetime.strptime("04:00", "%H:%M")

            for index, rango in enumerate(RANGOS):
                # Generamos los 4 caracteres exactos: "0400" o "0405"
                hora_objeto = hora_base + timedelta(minutes=5 * index)
                hora_agendada_input = hora_objeto.strftime("%H%M") 
                
                print(f"\n📂 Procesando rango {rango['inicio']} a {rango['fin']}...")
                print(f"⏰ Horario objetivo: {hora_objeto.strftime('%H:%M')}")
                
                # Navegación
                await page.click('a:has-text("Recibir")')
                await asyncio.sleep(2)
                await page.click('a.accordionLink:has-text("Control Títulos")')
                await asyncio.sleep(2)
                await page.click('span:has-text("Administrar Deudas")', force=True)
                
                # Filtros
                await page.wait_for_selector("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoInicio_T2")
                await page.fill("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoInicio_T2", rango['inicio'])
                await page.fill("input#ContentPlaceHolder1_ControleBuscaTitulo_txtDiasAtrasoFim_T2", rango['fin'])
                
                try:
                    await page.select_option("select#ContentPlaceHolder1_ControleBuscaTitulo_ddlSituacaoPagamento_d1", "1")
                except:
                    pass

                await page.click("a#ContentPlaceHolder1_ControleBuscaTitulo_btnBuscar_btn")
                
                # Esperar Exportar
                selector_exportar = "a#ContentPlaceHolder1_ControleBuscaTitulo_btnExportar_btn"
                await page.wait_for_selector(selector_exportar, state="visible", timeout=600000)
                await page.click(selector_exportar)
                
                # Configuración de Agendamiento
                selector_radio_async = "input#agendamentoExportacao_rbnExcelAssincrono"
                await page.wait_for_selector(selector_radio_async, state="visible")
                await page.click(selector_radio_async, force=True)

                selector_exec_agendar = "input#agendamentoExportacao_rbnExecucaoExcelAgendar"
                await page.wait_for_selector(selector_exec_agendar, state="visible")
                await page.click(selector_exec_agendar, force=True)

                # --- CORRECCIÓN DEFINITIVA DE HORA (4 CARACTERES) ---
                fecha_mañana = (datetime.now() + timedelta(days=1)).strftime("%d%m%Y")
                selector_fecha = "input#agendamentoExportacao_dataAgendamentoExcelAssincrono_T2"
                selector_hora = "input#agendamentoExportacao_horarioAgendamentoExcelAssincrono_T2"

                # Llenar fecha normalmente
                await page.fill(selector_fecha, fecha_mañana)

                # Para la hora: Enfocar, limpiar y escribir carácter por carácter
                print(f"✍️ Escribiendo hora: {hora_agendada_input}")
                await page.click(selector_hora)
                # Borrar contenido previo por si acaso
                await page.keyboard.press("Control+A")
                await page.keyboard.press("Backspace")
                # Escribir los 4 dígitos uno a uno
                await page.type(selector_hora, hora_agendada_input, delay=100)

                await page.wait_for_timeout(500)
                
                # Confirmar
                await page.click("a#agendamentoExportacao_okButton_btn")
                
                try:
                    await page.wait_for_selector("a#popupOkButton", state="visible", timeout=15000)
                    await page.click("a#popupOkButton", force=True)
                    print(f"✔️ Programado correctamente para las {hora_agendada_input}")
                except:
                    print("⚠️ No apareció el botón OK final.")
                
                await page.goto(URL_SGI)
                await page.wait_for_load_state("networkidle")

            print("\n🎉 Proceso terminado con éxito.")

        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(solicitar_reportes())
