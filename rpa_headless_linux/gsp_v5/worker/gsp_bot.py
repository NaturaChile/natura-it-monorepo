# ──────────────────────────────────────────────
# GSP Playwright Bot  –  Browser Automation Core
# ──────────────────────────────────────────────
#
# Each method corresponds to one logical step in the GSP flow.
# The bot is designed to be instantiated per-task so that browser
# contexts are never shared between concurrent workers.
# ──────────────────────────────────────────────
from __future__ import annotations

import os
import time
import urllib.request
import ssl
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, TimeoutError as PWTimeout

from config.settings import get_settings
from shared.logging_config import get_logger
from shared.exceptions import (
    LoginError,
    ConsultoraSearchError,
    CycleSelectionError,
    CartError,
    ProductAddError,
    NavigationError,
    SessionExpiredError,
)

    # ── STEP 6: Open cart ─────────────────────

    def open_cart(self) -> None:
        """Wait for the dashboard to load fully and click the shopping bag."""
        step = "open_cart"
        self._log_step(step, "Waiting for main page (Dashboard) to load")

        # 1. ESPERA DE CARGA (Vital para evitar overlays)
        # Esperamos a que aparezca el botón de "Productos de ciclo".
        # Esto confirma que el login/selección terminó y el dashboard es interactuable.
        try:
            dashboard_signal = '[data-testid="category-shortcut-NATURA"]'
            self.page.wait_for_selector(dashboard_signal, state="visible", timeout=60000)
            self._log_step(step, "Dashboard loaded (Shortcut button visible)")
        except PWTimeout:
            self._log_step(step, "Warning: Dashboard shortcut did not appear, trying bag anyway...", level="WARNING")
        
        # Pausa de seguridad para animaciones finales
        self.page.wait_for_timeout(2000)

        # 2. Clic en la Bolsa
        try:
            self.page.wait_for_selector('[data-testid="icon-bag"]', state="visible", timeout=30000)
            self.page.click('[data-testid="icon-bag"]')
        except PWTimeout:
            ss = self._take_screenshot("cart_wait")
            raise CartError("Shopping bag icon not found", step=step, details=f"screenshot={ss}")

        # 3. Esperar Input del Carrito
        try:
            self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=30000)
        except PWTimeout:
            ss = self._take_screenshot("cart_input_wait")
            raise CartError("Cart input did not appear after clicking bag", step=step, details=f"screenshot={ss}")

        self._log_step(step, "Cart opened ✓")

    # ── STEP 6b: Clear cart ─────────────────────

    def clear_cart(self) -> int:
        """Remove all products checking for the confirmation toast."""
        step = "clear_cart"
        self._log_step(step, "Checking for existing products in cart")

        # Helper para esperar que se vayan los overlays de carga
        def wait_for_loading_gone():
            try:
                # Damos un momento para que aparezca si es que va a aparecer
                self.page.wait_for_timeout(500)
                if self.page.is_visible('div[class*="overlayContainer"]'):
                    self.page.wait_for_selector('div[class*="overlayContainer"]', state="hidden", timeout=10000)
            except Exception:
                pass

        delete_buttons = self.page.query_selector_all('a[data-testid^="remove-product-"]')

        if not delete_buttons:
            self._log_step(step, "Cart is empty, nothing to clear")
            return 0

        removed_count = 0
        removed_codes: list[str] = []

        # Recopilar códigos para el log
        for btn in delete_buttons:
            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"
            removed_codes.append(product_code)

        self._log_step(
            step,
            f"Found {len(delete_buttons)} product(s) in cart to remove: {removed_codes}",
            details={"products_in_cart": removed_codes},
        )

        while True:
            wait_for_loading_gone() # Asegurar pantalla limpia
            btn = self.page.query_selector('a[data-testid^="remove-product-"]')
            if not btn:
                break

            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"

            try:
                btn.click()
                
                # Esperar Toast de confirmación
                try:
                    self.page.wait_for_selector("text=¡Producto eliminado con éxito!", state="visible", timeout=5000)
                    self._log_step(step, f"Confirmed removal toast for {product_code}")
                    # Esperar a que desaparezca para no estorbar
                    self.page.wait_for_selector("text=¡Producto eliminado con éxito!", state="hidden", timeout=3000)
                except PWTimeout:
                    self._log_step(step, f"Warning: Removal toast not detected for {product_code}", level="WARNING")

                removed_count += 1
            except Exception as e:
                self._log_step(step, f"Failed to remove {product_code}: {e}", level="WARNING")
                break

        self._log_step(step, f"Cart cleared: {removed_count} items removed ✓")
        return removed_count

    # ── STEP 7: Add product to cart ───────────

    def add_product(self, product_code: str, quantity: int) -> None:
        """Enter product/qty using Tab for validation and wait for success Toast."""
        step = "add_product"
        self._log_step(step, f"Adding product {product_code} x{quantity}")

        # Helper mejorado para detectar y esperar overlays
        def wait_for_loading_gone():
            try:
                # Breve pausa para dar tiempo a que el JS active el overlay
                self.page.wait_for_timeout(300)
                # Si aparece, esperamos hasta que se oculte
                if self.page.is_visible('div[class*="overlayContainer"]'):
                    self.page.wait_for_selector('div[class*="overlayContainer"]', state="hidden", timeout=15000)
            except Exception:
                pass

        # 1. Ingresar Código y Validar con TAB
        try:
            wait_for_loading_gone()
            code_input = self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=15000)
            code_input.click()
            code_input.fill("")
            code_input.fill(product_code)
            
            # TAB para validar el código
            self.page.keyboard.press("Tab")
            
            # Esperar a que el sistema procese (y quite el overlay si aparece)
            wait_for_loading_gone()
            
        except PWTimeout:
            ss = self._take_screenshot(f"product_code_{product_code}")
            raise ProductAddError(f"Product input not found/interactable", step=step, details=f"screenshot={ss}")

        # 2. Ingresar Cantidad
        qty_input = None
        qty_selectors = ['#code-and-quantity-quantity', 'input[inputmode="numeric"]', '[data-testid="quantity-input"]']
        
        # Búsqueda rápida
        for sel in qty_selectors:
            if self.page.is_visible(sel):
                qty_input = self.page.query_selector(sel)
                break
        
        if not qty_input:
             # Búsqueda con espera si no apareció inmediato
             try:
                 qty_input = self.page.wait_for_selector('input[inputmode="numeric"]', state="visible", timeout=5000)
             except PWTimeout:
                 ss = self._take_screenshot(f"product_qty_{product_code}")
                 raise ProductAddError(f"Quantity input not found (blocked by overlay?)", step=step, details=f"screenshot={ss}")

        try:
            qty_input.click(click_count=3)
            qty_input.fill(str(quantity))
            
            # TAB para validar cantidad y habilitar botón Añadir
            self.page.keyboard.press("Tab")
            wait_for_loading_gone()
            
        except Exception as e:
             raise ProductAddError(f"Error entering quantity: {e}", step=step)

        # 3. Clic en Añadir
        self._log_step(step, f"Clicking Añadir for {product_code}")
        try:
            btn_sel = '[data-testid="button-add-to-basket"]'
            # Esperar que esté habilitado
            self.page.wait_for_selector(f'{btn_sel}:not([disabled])', state="visible", timeout=5000)
            
            wait_for_loading_gone() # Último chequeo de limpieza
            self.page.click(btn_sel)
            
        except PWTimeout:
            ss = self._take_screenshot(f"add_btn_error_{product_code}")
            raise ProductAddError(f"Añadir button never enabled", step=step, details=f"screenshot={ss}")

        # 4. Confirmación con Toast
        try:
            self.page.wait_for_selector("text=¡Producto agregado con éxito!", state="visible", timeout=8000)
            self._log_step(step, f"Success detected: Toast appeared")
            
            # Esperar limpieza
            try:
                self.page.wait_for_selector("text=¡Producto agregado con éxito!", state="hidden", timeout=3000)
            except:
                pass
            return 
            
        except PWTimeout:
            self._log_step(step, "Success toast not seen, checking for error modals...", level="WARNING")
            
            if self.page.is_visible("text=Opciones Disponibles") or self.page.is_visible('#dialog-title'):
                # Es stock insuficiente
                try:
                    if self.page.is_visible('[data-testid="icon-outlined-navigation-close"]'):
                        self.page.click('[data-testid="icon-outlined-navigation-close"]')
                    else:
                        self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)
                except:
                    pass

                raise ProductAddError(
                    f"Product {product_code} out of stock (Modal detected)",
                    step=step,
                    details="reason=no_stock"
                )
            
            # Si no hay toast ni modal de stock, asumimos falla
            ss = self._take_screenshot(f"unknown_add_result_{product_code}")
            raise ProductAddError(f"No confirmation toast nor error modal appeared", step=step, details=f"screenshot={ss}")
                f"Preflight urllib failed but DNS/TCP checks passed. Proceeding to Playwright. Proxy={proxy_env or 'none'}",
                level="WARNING",
            )
            return

        # Otherwise, raise an error to trigger retry
        raise LoginError(
            f"Network unreachable from container: could not reach {base} "
            f"after 3 attempts (urllib). Proxy={proxy_env or 'none'}. "
            f"If proxy is required, set HTTP_PROXY/HTTPS_PROXY env vars in the workflow.",
            step=step,
        )

    def _take_screenshot(self, name: str) -> str | None:
        """Save a screenshot and return the file path."""
        if not self.settings.screenshot_on_error:
            return None
        try:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            path = self.settings.screenshot_dir / f"{name}_{self.order_id}_{ts}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            self.page.screenshot(path=str(path), full_page=True)
            self._log_step("screenshot", f"Screenshot saved: {path}")
            return str(path)
        except Exception as e:
            logger.warning("screenshot_failed", error=str(e))
            return None

    def _safe_click(self, selector: str, timeout: int | None = None, step: str = "click") -> None:
        """Click an element with error handling and screenshot on failure."""
        t = timeout or self.settings.playwright_timeout
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=t)
            self.page.click(selector)
        except PWTimeout:
            ss = self._take_screenshot(f"timeout_{step}")
            raise NavigationError(
                f"Timeout waiting for selector: {selector}",
                step=step,
                details=f"screenshot={ss}",
            )

    def _safe_fill(self, selector: str, value: str, timeout: int | None = None, step: str = "fill") -> None:
        """Fill an input with error handling."""
        t = timeout or self.settings.playwright_timeout
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=t)
            self.page.fill(selector, value)
        except PWTimeout:
            ss = self._take_screenshot(f"timeout_{step}")
            raise NavigationError(
                f"Timeout waiting for input: {selector}",
                step=step,
                details=f"screenshot={ss}",
            )

    # ── STEP 1: Login ─────────────────────────

    def login(self) -> None:
        """Navigate to GSP login and authenticate as supervisor."""
        step = "login"
        self._log_step(step, "Navigating to login page")

        # ── Pre-flight: verify network connectivity from container ──
        # Disabled preflight check: some servers/WAFs block requests that
        # identify as bots (e.g. our urllib preflight used a GSPBot user-agent).
        # The container network was validated separately; allow Playwright
        # (with a human-like user-agent) to perform the navigation directly.
        # self._preflight_check(self.settings.gsp_login_url, step)

        max_nav_retries = 3
        for attempt in range(1, max_nav_retries + 1):
            try:
                self.page.goto(
                    self.settings.gsp_login_url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.playwright_timeout,
                )
                break  # success
            except Exception as nav_err:
                self._log_step(step, f"Navigation attempt {attempt}/{max_nav_retries} failed: {nav_err}", level="WARNING")
                if attempt == max_nav_retries:
                    ss = self._take_screenshot("login_navigation")
                    raise LoginError(
                        f"Login page did not load after {max_nav_retries} attempts: {nav_err}",
                        step=step,
                        details=f"screenshot={ss}",
                    )
                self.page.wait_for_timeout(3000)  # wait 3s before retry

        # Select "Código" from the combobox
        self._log_step(step, "Selecting 'Código' from login type dropdown")
        try:
            self.page.wait_for_selector('[role="combobox"]', state="visible", timeout=30000)
            self.page.click('[role="combobox"]')
            self.page.wait_for_selector('[role="option"][data-value="personCode"]', state="visible", timeout=10000)
            self.page.click('[role="option"][data-value="personCode"]')
        except PWTimeout:
            ss = self._take_screenshot("login_select_code")
            raise LoginError("Could not select 'Código' option", step=step, details=f"screenshot={ss}")

        # Enter supervisor code
        self._log_step(step, "Entering supervisor code")
        self._safe_fill('input[name="option"]', self.supervisor_code, step=step)

        # Enter password
        self._log_step(step, "Entering password")
        self._safe_fill('input[name="password"]', self.supervisor_password, step=step)

        # Click access button
        self._log_step(step, "Clicking ACCESO button")
        self._safe_click('[data-testid="button-access"]', step=step)

        # Wait for post-login page to load  
        self._log_step(step, "Waiting for post-login navigation")
        try:
            self.page.wait_for_selector('label[for="otherCn"]', state="visible", timeout=60000)
        except PWTimeout:
            ss = self._take_screenshot("login_post_wait")
            raise LoginError(
                "Post-login page did not load (label 'Para otra Consultora' not found)",
                step=step,
                details=f"screenshot={ss}",
            )

        self._log_step(step, "Login successful ✓")

    # ── STEP 2: Select "Para otra Consultora" ─

    def select_otra_consultora(self) -> None:
        """Click 'Para otra Consultora', accept impersonation and ensure input appears."""
        step = "select_otra_consultora"
        self._log_step(step, "Clicking 'Para otra Consultora'")

        try:
            # 1. Click the label to select the radio
            self.page.click('label[for="otherCn"]')

            # 2. Click the impersonation confirm button (Aceptar) if present
            try:
                # Wait briefly for the accept button to appear, then click it
                if self.page.is_visible('[data-testid="impersonation-accept-button"]'):
                    self.page.click('[data-testid="impersonation-accept-button"]')
                else:
                    # give it a short chance to appear
                    try:
                        self.page.wait_for_selector('[data-testid="impersonation-accept-button"]', state="visible", timeout=2000)
                        self.page.click('[data-testid="impersonation-accept-button"]')
                    except PWTimeout:
                        # Button not present — continue, maybe not required in this flow
                        self._log_step(step, "Impersonation accept button not present; continuing", level="DEBUG")
            except Exception as ex:
                self._log_step(step, f"Error clicking impersonation accept button: {ex}", level="WARNING")

            # 3. Now wait for the consultora input to appear (this appears after Accept)
            try:
                self.page.wait_for_selector('#naturaCode', state="visible", timeout=30000)
            except PWTimeout:
                # Last resort: force the radio click via DOM and wait a bit
                self._log_step(step, "Input not visible after accept; forcing radio via JS", level="WARNING")
                try:
                    self.page.evaluate("document.getElementById('otherCn').click()")
                    self.page.wait_for_selector('#naturaCode', state="visible", timeout=5000)
                except Exception as ex2:
                    ss = self._take_screenshot("otra_consultora_no_input")
                    raise ConsultoraSearchError(
                        f"Consultora input did not appear: {ex2}",
                        step=step,
                        details=f"screenshot={ss}",
                    )

        except Exception as e:
            ss = self._take_screenshot("otra_consultora_error")
            raise ConsultoraSearchError(
                f"Failed to select consultant option: {e}",
                step=step,
                details=f"screenshot={ss}",
            )

        self._log_step(step, "Selected 'Para otra Consultora' and accepted impersonation ✓")

    # ── STEP 3: Search consultora by code ─────

    def search_consultora(self, consultora_code: str) -> None:
        """Enter consultora code and search."""
        step = "search_consultora"
        self._log_step(step, f"Searching consultora: {consultora_code}")

        # Use the confirmed ID (#naturaCode) or fallback to data-testid
        try:
            self.page.wait_for_selector('#naturaCode, [data-testid="ds-input"]', state="visible", timeout=30000)

            if self.page.is_visible('#naturaCode'):
                self.page.fill('#naturaCode', consultora_code)
            else:
                self.page.fill('[data-testid="ds-input"]', consultora_code)

        except PWTimeout:
            ss = self._take_screenshot("search_input_timeout")
            raise NavigationError(
                "Timeout waiting for consultora input (#naturaCode)",
                step=step,
                details=f"screenshot={ss}",
            )

        # Click "Buscar"
        self._log_step(step, "Clicking Buscar")
        try:
            self.page.wait_for_selector('span.label-0-2-82:has-text("Buscar")', state="visible", timeout=15000)
            self.page.click('button:has(span:has-text("Buscar"))')
        except PWTimeout:
            try:
                self.page.click('[data-testid="icon-outlined-action-search"]')
            except Exception:
                ss = self._take_screenshot("search_consultora_btn")
                raise ConsultoraSearchError(
                    "Could not click Buscar button",
                    step=step,
                    consultora=consultora_code,
                    details=f"screenshot={ss}",
                )

        self._log_step(step, f"Consultora {consultora_code} searched ✓")

    # ── STEP 4: Confirm consultora ────────────

    def confirm_consultora(self) -> None:
        """Wait for and click the Confirmar button."""
        step = "confirm_consultora"
        self._log_step(step, "Waiting for Confirmar button")

        try:
            self.page.wait_for_selector('[data-testid="confirm-button"]', state="visible", timeout=30000)
            self.page.click('[data-testid="confirm-button"]')
        except PWTimeout:
            ss = self._take_screenshot("confirm_consultora")
            raise ConsultoraSearchError(
                "Confirmar button not found",
                step=step,
                details=f"screenshot={ss}",
            )

        self._log_step(step, "Consultora confirmed ✓")

    # ── STEP 5: Select cycle ──────────────────

    def select_cycle(self) -> None:
        """Dynamically select the first available cycle radio button and click Aceptar."""
        step = "select_cycle"
        self._log_step(step, "Waiting for cycle selection dialog")

        try:
            self.page.wait_for_selector('[data-testid="cycle-radio-button"]', state="visible", timeout=30000)
        except PWTimeout:
            ss = self._take_screenshot("cycle_wait")
            raise CycleSelectionError("Cycle dialog did not appear", step=step, details=f"screenshot={ss}")

        # Select the FIRST radio button dynamically
        radio_buttons = self.page.query_selector_all('[data-testid="cycle-radio-button"]')
        if not radio_buttons:
            ss = self._take_screenshot("cycle_no_options")
            raise CycleSelectionError("No cycle options found", step=step, details=f"screenshot={ss}")

        first_radio = radio_buttons[0]
        cycle_value = first_radio.get_attribute("value")
        self._log_step(step, f"Selecting first cycle: {cycle_value}")

        # Click the radio button's wrapper (ripple container) for proper MUI activation
        parent_wrapper = first_radio.evaluate_handle("el => el.closest('[data-testid=\"ripple-wrapper\"]')")
        if parent_wrapper:
            parent_wrapper.as_element().click()
        else:
            first_radio.click()

        # Click Aceptar
        self._log_step(step, "Clicking Aceptar")
        try:
            self.page.wait_for_selector('[data-testid="cycle-accept-button"]', state="visible", timeout=15000)
            self.page.click('[data-testid="cycle-accept-button"]')
        except PWTimeout:
            ss = self._take_screenshot("cycle_accept")
            raise CycleSelectionError("Aceptar button not found", step=step, details=f"screenshot={ss}")

        self._log_step(step, f"Cycle {cycle_value} selected ✓")

    # ── STEP 6: Open cart ─────────────────────

    def open_cart(self) -> None:
        """Wait for the page to load and click the shopping bag icon."""
        step = "open_cart"
        self._log_step(step, "Waiting for main page to load")

        try:
            self.page.wait_for_selector('[data-testid="icon-bag"]', state="visible", timeout=60000)
        except PWTimeout:
            ss = self._take_screenshot("cart_wait")
            raise CartError("Shopping bag icon not found", step=step, details=f"screenshot={ss}")
        # Buen indicio de que la página principal cargó: el atajo NATURA
        try:
            self.page.wait_for_selector('button[data-testid="category-shortcut-NATURA"]', state="visible", timeout=20000)
            self._log_step(step, "Category shortcut NATURA visible — page appears loaded")
        except PWTimeout:
            # No fatal: avisamos y seguimos, pero es útil para diagnóstico
            self._log_step(step, "Warning: Category shortcut NATURA not visible before opening cart", level="WARNING")

        self._log_step(step, "Clicking shopping bag")
        self.page.click('[data-testid="icon-bag"]')

        # Wait for cart input to appear
        try:
            self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=30000)
        except PWTimeout:
            ss = self._take_screenshot("cart_input_wait")
            raise CartError("Cart input did not appear after clicking bag", step=step, details=f"screenshot={ss}")

        self._log_step(step, "Cart opened ✓")

    # ── STEP 6b: Clear cart ─────────────────────

    def clear_cart(self) -> int:
        """Remove all products checking for the confirmation toast."""
        step = "clear_cart"
        self._log_step(step, "Checking for existing products in cart")

        delete_buttons = self.page.query_selector_all('a[data-testid^="remove-product-"]')

        if not delete_buttons:
            self._log_step(step, "Cart is empty, nothing to clear")
            return 0

        removed_count = 0
        removed_codes: list[str] = []

        # Recopilar códigos para el log
        for btn in delete_buttons:
            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"
            removed_codes.append(product_code)

        self._log_step(
            step,
            f"Found {len(delete_buttons)} product(s) in cart to remove: {removed_codes}",
            details={"products_in_cart": removed_codes},
        )

        # Borrar uno por uno verificando el Toast
        while True:
            # Re-consultar el botón porque el DOM cambia tras cada borrado
            btn = self.page.query_selector('a[data-testid^="remove-product-"]')
            if not btn:
                break

            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"

            try:
                btn.click()

                # NUEVO: Esperar explícitamente al Toast de confirmación
                # Usamos el texto exacto que nos diste
                try:
                    self.page.wait_for_selector("text=¡Producto eliminado con éxito!", state="visible", timeout=5000)
                    self._log_step(step, f"Confirmed removal toast for {product_code}")

                    # Esperar a que el toast desaparezca para no tapar otros elementos (opcional pero recomendado)
                    self.page.wait_for_selector("text=¡Producto eliminado con éxito!", state="hidden", timeout=3000)

                except PWTimeout:
                    self._log_step(step, f"Warning: Removal toast not detected for {product_code}", level="WARNING")

                removed_count += 1

            except Exception as e:
                self._log_step(step, f"Failed to remove {product_code}: {e}", level="WARNING")
                break

        self._log_step(step, f"Cart cleared: {removed_count} items removed ✓")
        return removed_count

    # ── STEP 7: Add product to cart ───────────

    def add_product(self, product_code: str, quantity: int) -> None:
        """Enter product/qty using Tab for validation and wait for success Toast."""
        step = "add_product"
        self._log_step(step, f"Adding product {product_code} x{quantity}")

        # Helper para esperar que se vayan los spinners/overlays
        def wait_for_loading_gone():
            try:
                self.page.wait_for_selector('div[class*="overlayContainer"]', state="hidden", timeout=3000)
            except Exception:
                pass

        # 1. Ingresar Código y Validar con TAB
        try:
            wait_for_loading_gone()
            code_input = self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=15000)
            code_input.click()
            code_input.fill("")
            code_input.fill(product_code)
            
            # Validar código
            self.page.keyboard.press("Tab")
            wait_for_loading_gone()
            
        except PWTimeout:
            ss = self._take_screenshot(f"product_code_{product_code}")
            raise ProductAddError(f"Product input not found/interactable", step=step, details=f"screenshot={ss}")

        # 2. Ingresar Cantidad
        qty_input = None
        qty_selectors = ['#code-and-quantity-quantity', 'input[inputmode="numeric"]', '[data-testid="quantity-input"]']
        
        for sel in qty_selectors:
            if self.page.is_visible(sel):
                qty_input = self.page.query_selector(sel)
                break
        
        if not qty_input:
             # Si no apareció rápido, damos un margen de espera
             try:
                 qty_input = self.page.wait_for_selector('input[inputmode="numeric"]', state="visible", timeout=5000)
             except PWTimeout:
                 ss = self._take_screenshot(f"product_qty_{product_code}")
                 raise ProductAddError(f"Quantity input not found", step=step, details=f"screenshot={ss}")

        try:
            qty_input.click(click_count=3)
            qty_input.fill(str(quantity))
            # Validar cantidad con TAB para habilitar botón
            self.page.keyboard.press("Tab")
            wait_for_loading_gone()
        except Exception as e:
             raise ProductAddError(f"Error entering quantity: {e}", step=step)

        # 3. Clic en Añadir (Esperando que se habilite)
        self._log_step(step, f"Clicking Añadir for {product_code}")
        try:
            btn_sel = '[data-testid="button-add-to-basket"]'
            self.page.wait_for_selector(f'{btn_sel}:not([disabled])', state="visible", timeout=5000)
            self.page.click(btn_sel)
        except PWTimeout:
            ss = self._take_screenshot(f"add_btn_error_{product_code}")
            raise ProductAddError(f"Añadir button never enabled", step=step, details=f"screenshot={ss}")

        # 4. VERIFICACIÓN FINAL: Toast vs Error Modal
        # Aquí es donde confirmamos si realmente se agregó
        try:
            # Esperamos el Toast de éxito
            self.page.wait_for_selector("text=¡Producto agregado con éxito!", state="visible", timeout=5000)
            self._log_step(step, f"Success detected: Toast '¡Producto agregado con éxito!' appeared")
            
            # Esperamos a que se vaya para limpiar la pantalla para el siguiente producto
            try:
                self.page.wait_for_selector("text=¡Producto agregado con éxito!", state="hidden", timeout=3000)
            except:
                pass # Si no se va rápido, seguimos igual
                
            return # ¡Éxito confirmado! Salimos de la función.
            
        except PWTimeout:
            # Si no salió el Toast, buscamos el Modal de Error/Stock
            self._log_step(step, "Success toast not seen, checking for error modals...", level="WARNING")
            
            if self.page.is_visible("text=Opciones Disponibles") or self.page.is_visible('#dialog-title'):
                # Es un error de stock
                self._take_screenshot(f"stock_error_{product_code}")
                
                # Intentar cerrar el modal
                try:
                    if self.page.is_visible('[data-testid="icon-outlined-navigation-close"]'):
                        self.page.click('[data-testid="icon-outlined-navigation-close"]')
                    else:
                        self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)
                except:
                    pass

                raise ProductAddError(
                    f"Product {product_code} out of stock (Modal detected)",
                    step=step,
                    details="reason=no_stock"
                )
            else:
                # Ni toast ni modal... algo raro pasó
                ss = self._take_screenshot(f"unknown_add_result_{product_code}")
                # Podríamos lanzar error o asumir éxito silencioso, pero mejor ser estrictos:
                raise ProductAddError(f"No confirmation toast nor error modal appeared", step=step, details=f"screenshot={ss}")

    # ── Full Flow Orchestration ───────────────

    def execute_order(
        self,
        consultora_code: str,
        products: list[dict],
    ) -> dict:
        """
        Execute the complete order flow for one consultora.

        Args:
            consultora_code: The consultora code to search.
            products: List of dicts with keys 'product_code' and 'quantity'.

        Returns:
            dict with results and step log.
        """
        start_time = time.time()
        result = {
            "success": False,
            "consultora_code": consultora_code,
            "products_added": [],
            "products_failed": [],
            "error": None,
            "error_step": None,
            "screenshot": None,
            "duration_seconds": 0,
            "step_log": [],
        }

        try:
            # Step 1: Login
            self.login()
            result["current_step"] = "login_ok"

            # Step 2: Select "Para otra Consultora"
            self.select_otra_consultora()
            result["current_step"] = "otra_consultora_selected"

            # Step 3: Search consultora
            self.search_consultora(consultora_code)
            result["current_step"] = "consultora_searched"

            # Step 4: Confirm consultora
            self.confirm_consultora()
            result["current_step"] = "consultora_confirmed"

            # Step 5: Select cycle
            self.select_cycle()
            result["current_step"] = "cycle_selected"

            # Step 6: Open cart
            self.open_cart()
            result["current_step"] = "cart_open"

            # Step 6b: Clear existing cart items
            cleared = self.clear_cart()
            if cleared > 0:
                result["current_step"] = "cart_cleared"

            # Step 7: Add products
            for product in products:
                pcode = product["product_code"]
                pqty = product.get("quantity", 1)
                try:
                    self.add_product(pcode, pqty)
                    result["products_added"].append({"product_code": pcode, "quantity": pqty})
                except ProductAddError as e:
                    is_stock = "no_stock" in (getattr(e, "details", "") or "")
                    reason = "out_of_stock" if is_stock else "add_error"
                    self._log_step(
                        "add_product",
                        f"FAILED to add {pcode}: {e}",
                        level="WARNING" if is_stock else "ERROR",
                        details={"product_code": pcode, "reason": reason},
                    )
                    result["products_failed"].append({
                        "product_code": pcode,
                        "quantity": pqty,
                        "error": str(e),
                        "reason": reason,
                    })

            result["current_step"] = "products_added"
            result["success"] = len(result["products_failed"]) == 0

        except Exception as e:
            result["error"] = str(e)
            result["error_step"] = getattr(e, "step", "unknown")
            result["screenshot"] = self._take_screenshot(f"error_{result.get('error_step', 'unknown')}")
            self._log_step("error", str(e), level="ERROR")

        result["duration_seconds"] = round(time.time() - start_time, 2)
        result["step_log"] = self.get_step_log()
        return result
