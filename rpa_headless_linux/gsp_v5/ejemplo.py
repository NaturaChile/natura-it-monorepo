 # --- MOTOR DE DECISIONES ADAPTATIVO (VERSIÓN JS PURO) ---
        max_attempts = 10
        for attempt in range(max_attempts):
            print(f"\nCiclo de decisión #{attempt + 1}...")
            await page.wait_for_timeout(2500) 

            if "/cart" in page.url:
                print(" Objetivo alcanzado: En el carrito.")
                break

            # 1. CICLO (SELECCIONAR EL PRIMER RADIO VISIBLE)
            try:
                cycle_radios = page.locator('input[data-testid="cycle-radio-button"]')
                count = await cycle_radios.count()
                if count > 0:
                    selected = None
                    for i in range(count):
                        try:
                            loc = cycle_radios.nth(i)
                            if await loc.is_visible(timeout=500):
                                selected = loc
                                break
                        except Exception:
                            continue

                    if selected is not None:
                        val = await selected.get_attribute('value')
                        id_attr = await selected.get_attribute('id')
                        print("Pop-up de CICLO detectado.")
                        print(f"Seleccionando el primer ciclo visible (value={val})...")
                        # Preferimos click en la etiqueta asociada si existe
                        try:
                            if id_attr:
                                lbl = page.locator(f'label[for="{id_attr}"]')
                                if await lbl.count() > 0:
                                    await lbl.first.evaluate('el => el.click()')
                                else:
                                    await selected.evaluate('el => el.click()')
                            else:
                                await selected.evaluate('el => el.click()')
                        except Exception:
                            await selected.evaluate('el => el.click()')

                        await page.wait_for_timeout(500)
                        # Intentar aceptar el ciclo
                        try:
                            await page.locator('[data-testid="cycle-accept-button"]').evaluate('el => el.click()')
                        except Exception:
                            try:
                                await page.get_by_role('button', name='Aceptar').first.evaluate('el => el.click()')
                            except Exception:
                                print('No se pudo presionar el botón de aceptar ciclo (intentos fallidos)')

                        print('Ciclo confirmado con JS.')
                        continue
            except Exception as e:
                print(f'Error al detectar/seleccionar ciclo: {e}')

            # 2. VENTA DIRECTA OPCIONAL
            try:
                if await page.locator('label[for="id_1"]').is_visible(timeout=1000):
                     print("Pop-up Venta Directa detectado.")
                     await page.locator('label[for="id_1"]').evaluate("el => el.click()")
                     await page.wait_for_timeout(500)
                     await page.get_by_role("button", name="Aceptar").first.evaluate("el => el.click()")
                     continue
            except Exception: pass
            
            # 3. POP-UPS GENÉRICOS (LISTO)
            try:
                listo_btn = page.locator('button:has-text("LISTO")')
                if await listo_btn.count() > 0 and await listo_btn.first.is_visible(timeout=1000):
                    print("Botón 'LISTO' detectado. Presionando con JS...")
                    await listo_btn.first.evaluate("el => el.click()")
                    continue
            except Exception: pass

            # 4. ELIMINAR PEDIDO
            try:
                 if await page.get_by_text("Este pedido esta guardado").is_visible(timeout=1000):
                     print("Pop-up 'Recuperar Pedido' detectado.")
                     await page.get_by_role("button", name="Eliminar Pedido").evaluate("el => el.click()")
                     print("Clic JS en 'Eliminar Pedido' realizado.")
                     continue
            except Exception: pass

            # 5. IR AL CARRITO
            try:
                carrito_btn = None
                # Priorizar icono bolsa con data-testid
                if await page.locator('button[data-testid="icon-bag"]').count() > 0 and await page.locator('button[data-testid="icon-bag"]').first.is_visible(timeout=1000):
                    carrito_btn = page.locator('button[data-testid="icon-bag"]').first
                # Fallback por texto visible
                elif await page.locator('button:has-text("Mi Carrito")').count() > 0 and await page.locator('button:has-text("Mi Carrito")').first.is_visible(timeout=1000):
                    carrito_btn = page.locator('button:has-text("Mi Carrito")').first
                # Otro fallback por rol/label
                elif await page.get_by_role('button', name='Mi Carrito').count() > 0:
                    carrito_btn = page.get_by_role('button', name='Mi Carrito').first

                if carrito_btn is not None:
                     print("Botón 'Mi Carrito' detectado. Navegando con JS...")
                     await carrito_btn.evaluate("el => el.click()")
                     continue
            except Exception: pass
            
            if attempt == 5: 
                 print(" Estado desconocido. Recargando página...")
                 await page.reload()
                 await page.wait_for_load_state("networkidle")

        else:
            raise Exception("No se pudo llegar al carrito tras múltiples intentos.")
        
        # --- SUBIDA DE ARCHIVO ---
        print("Esperando campo de subida...")
        file_input = page.locator('input[type="file"]')
        await file_input.wait_for(state="attached", timeout=60000)
        await file_input.set_input_files(order_file_path)
        print(" Archivo entregado.")
        
        await page.wait_for_timeout(20000)
        status = "Subido (Pendiente Validación)"

        # --- GESTIÓN FINAL ---
        try:
            if await page.get_by_text("No podemos encontrar los Códigos").is_visible(timeout=5000):
                 msg_el = page.locator("div.modal-body")
                 error_message = (await msg_el.inner_text()).replace("\n", " ")
                 print(f"Info: Productos no encontrados detectados.")
                 await page.get_by_role("button", name="LISTO").evaluate("el => el.click()")
            else:
                 error_message = "N/A"
        except Exception: error_message = "Error al leer mensaje"

        try:
            if await page.get_by_text("hemos detectado inconsistencias").is_visible(timeout=5000):
                print("Aviso de inconsistencias final detectado. Cerrando con JS...")
                await page.locator('button:has-text("LISTO")').evaluate("el => el.click()")
        except Exception: pass
        
        status = "Procesado Correctamente"

