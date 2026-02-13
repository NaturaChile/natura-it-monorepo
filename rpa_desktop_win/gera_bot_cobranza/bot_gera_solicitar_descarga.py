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
    print("🚀 Iniciando Bot Solicitador con Horarios Escalonados...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        page = await browser.new_page()
        
        try:
            print(f"🔗 Conectando a {URL_SGI}...")
            await page.goto(URL_SGI, timeout=60000)
            
            # Login
            await page.fill("input#txtUsuario_T2", USUARIO)
            await page.fill("input#txtSenha_T2", CONTRASENA)
            await page.click("a#btnLogin_btn")
            await page.wait_for_load_state("networkidle")
            print("✅ Sesión iniciada.")

            # --- LÓGICA DE HORA ESCALONADA ---
            # Empezamos a las 04:00
            hora_base = datetime.strptime("04:00", "%H:%M")

            for index, rango in enumerate(RANGOS):
                # Calculamos la hora para este rango: el primero 04:00, el segundo 04:05
                hora_agendada = (hora_base + timedelta(minutes=5 * index)).strftime("%H:%M")
                
                print(f"\n📂 Procesando rango {rango['inicio']} a {rango['fin']}...")
                print(f"⏰ Horario asignado para este reporte: {hora_agendada}")
                
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
                
                # Selección 'Pendientes'
                try:
                    # Usando el selector select_option que definimos anteriormente para Situación de Pago
                    await page.select_option("select#ContentPlaceHolder1_ControleBuscaTitulo_ddlSituacaoPagamento_d1", "1")
                    print("🔔 Selección 'Pendientes' aplicada.")
                except:
                    pass

                print("🔎 Consultando...")
                await page.click("a#ContentPlaceHolder1_ControleBuscaTitulo_btnBuscar_btn")
                
                # Esperar botón Exportar visible
                selector_exportar = "a#ContentPlaceHolder1_ControleBuscaTitulo_btnExportar_btn"
                print("⏳ Esperando que el servidor habilite el botón de Exportar...")
                await page.wait_for_selector(selector_exportar, state="visible", timeout=600000)
                
                # Clic en Exportar
                await page.click(selector_exportar)
                print("⚙️ Abriendo configuración de agenda...")

                # Esperar popup/agendamiento
                selector_radio_async = "input#agendamentoExportacao_rbnExcelAssincrono"
                await page.wait_for_selector(selector_radio_async, state="visible", timeout=30000)
                await page.click(selector_radio_async, force=True)

                # Seleccionar ejecución agendada
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

                await page.wait_for_timeout(500)
                print(f"📅 Agendado para {fecha_mañana} a las {hora_agendada}")

                # Confirmar agendamiento
                await page.click("a#agendamentoExportacao_okButton_btn")
                
                # Confirmación final
                try:
                    await page.wait_for_selector("a#popupOkButton", state="visible", timeout=15000)
                    await page.click("a#popupOkButton", force=True)
                    print(f"✔️ Solicitud exitosa para las {hora_agendada}.")
                except:
                    print("⚠️ No apareció el botón OK final.")
                
                # Volver a Home
                await page.goto(URL_SGI)
                await page.wait_for_load_state("networkidle")

            print("\n🎉 Proceso terminado. Los archivos aparecerán escalonados mañana.")

        except Exception as e:
            print(f"❌ Error durante la solicitud: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(solicitar_reportes())
