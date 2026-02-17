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

logger = get_logger("gsp_bot")


class GSPBot:
    """Stateful Playwright bot that executes the full GSP order flow."""

    # ── Lifecycle ─────────────────────────────

    def __init__(
        self,
        supervisor_code: str,
        supervisor_password: str,
        order_id: int | None = None,
        worker_id: str | None = None,
    ):
        self.settings = get_settings()
        self.supervisor_code = supervisor_code
        self.supervisor_password = supervisor_password
        self.order_id = order_id
        self.worker_id = worker_id or f"worker-{os.getpid()}"

        self._pw = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        self._step_log: list[dict] = []

    # ── Context manager ───────────────────────

    def __enter__(self):
        self.start_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def start_browser(self) -> None:
        """Launch Chromium via Playwright."""
        logger.info("launching_browser", headless=self.settings.playwright_headless, worker=self.worker_id)
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.settings.playwright_headless,
            slow_mo=self.settings.playwright_slow_mo,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-http2",
            ],
        )
        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="es-CL",
            timezone_id="America/Santiago",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            ignore_https_errors=True,
        )
        self._context.set_default_timeout(self.settings.playwright_timeout)
        self.page = self._context.new_page()

    def close(self) -> None:
        """Clean up browser resources."""
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as e:
            logger.warning("browser_close_error", error=str(e))

    # ── Helpers ───────────────────────────────

    def _log_step(self, step: str, message: str, level: str = "INFO", details: dict | None = None) -> None:
        """Record a step in the internal log and emit structured log."""
        entry = {
            "step": step,
            "message": message,
            "level": level,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "order_id": self.order_id,
            "worker_id": self.worker_id,
        }
        self._step_log.append(entry)
        log_fn = getattr(logger, level.lower(), logger.info)
        log_fn(message, **{k: v for k, v in entry.items() if k not in ("message", "level")})

    def get_step_log(self) -> list[dict]:
        return list(self._step_log)

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

        try:
            self.page.goto(self.settings.gsp_login_url, wait_until="networkidle", timeout=self.settings.playwright_timeout)
        except PWTimeout:
            ss = self._take_screenshot("login_navigation")
            raise LoginError("Login page did not load", step=step, details=f"screenshot={ss}")

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
        """Click 'Para otra Consultora' radio button."""
        step = "select_otra_consultora"
        self._log_step(step, "Clicking 'Para otra Consultora'")

        try:
            # Click the label or its parent container
            self.page.click('label[for="otherCn"]')
        except PWTimeout:
            ss = self._take_screenshot("otra_consultora")
            raise ConsultoraSearchError(
                "'Para otra Consultora' not clickable",
                step=step,
                details=f"screenshot={ss}",
            )

        self._log_step(step, "Selected 'Para otra Consultora' ✓")

    # ── STEP 3: Search consultora by code ─────

    def search_consultora(self, consultora_code: str) -> None:
        """Enter consultora code and search."""
        step = "search_consultora"
        self._log_step(step, f"Searching consultora: {consultora_code}")

        # Wait for the consultora input
        self._safe_fill('#naturaCode', consultora_code, timeout=30000, step=step)

        # Click "Buscar"
        self._log_step(step, "Clicking Buscar")
        try:
            self.page.wait_for_selector('span.label-0-2-82:has-text("Buscar")', state="visible", timeout=15000)
            self.page.click('button:has(span:has-text("Buscar"))')
        except PWTimeout:
            # Fallback: try icon-based search button
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
        """Remove all products currently in the cart. Returns count of removed items."""
        step = "clear_cart"
        self._log_step(step, "Checking for existing products in cart")

        # Find all delete buttons matching data-testid="remove-product-*"
        delete_buttons = self.page.query_selector_all('a[data-testid^="remove-product-"]')

        if not delete_buttons:
            self._log_step(step, "Cart is empty, nothing to clear")
            return 0

        removed_count = 0
        removed_codes: list[str] = []

        for btn in delete_buttons:
            # Extract product code from data-testid="remove-product-XXXXX"
            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"
            removed_codes.append(product_code)

        self._log_step(
            step,
            f"Found {len(delete_buttons)} product(s) in cart to remove: {removed_codes}",
            details={"products_in_cart": removed_codes},
        )

        # Delete one by one (DOM refreshes after each removal)
        while True:
            btn = self.page.query_selector('a[data-testid^="remove-product-"]')
            if not btn:
                break

            testid = btn.get_attribute("data-testid") or ""
            product_code = testid.replace("remove-product-", "") if testid else "unknown"

            try:
                btn.click()
                self.page.wait_for_timeout(1500)  # Wait for DOM to update
                removed_count += 1
                self._log_step(
                    step,
                    f"Removed product {product_code} from cart ({removed_count}/{len(removed_codes)})",
                    details={"removed_product": product_code},
                )
            except Exception as e:
                self._log_step(
                    step,
                    f"Failed to remove product {product_code}: {e}",
                    level="WARNING",
                    details={"product_code": product_code, "error": str(e)},
                )
                break

        self._log_step(
            step,
            f"Cart cleared: {removed_count} product(s) removed ✓",
            details={"removed_count": removed_count, "removed_codes": removed_codes},
        )
        return removed_count

    # ── STEP 7: Add product to cart ───────────

    def add_product(self, product_code: str, quantity: int) -> None:
        """Enter a product code and quantity, then click Añadir."""
        step = "add_product"
        self._log_step(step, f"Adding product {product_code} x{quantity}")

        # Clear and fill the product code input
        try:
            code_input = self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=15000)
            code_input.click()
            code_input.fill("")
            code_input.fill(product_code)
        except PWTimeout:
            ss = self._take_screenshot(f"product_code_{product_code}")
            raise ProductAddError(
                f"Product code input not found for {product_code}",
                step=step,
                details=f"screenshot={ss}",
            )

        # Fill quantity
        try:
            qty_input = self.page.wait_for_selector('input[inputmode="numeric"]', state="visible", timeout=10000)
            qty_input.click(click_count=3)  # select all
            qty_input.fill(str(quantity))
        except PWTimeout:
            ss = self._take_screenshot(f"product_qty_{product_code}")
            raise ProductAddError(
                f"Quantity input not found for {product_code}",
                step=step,
                details=f"screenshot={ss}",
            )

        # Click Añadir
        self._log_step(step, f"Clicking Añadir for {product_code}")
        try:
            self.page.wait_for_selector('[data-testid="button-add-to-basket"]', state="visible", timeout=10000)
            self.page.click('[data-testid="button-add-to-basket"]')
        except PWTimeout:
            ss = self._take_screenshot(f"product_add_btn_{product_code}")
            raise ProductAddError(
                f"Añadir button not found for {product_code}",
                step=step,
                details=f"screenshot={ss}",
            )

        # Wait for cart update and check for "Opciones Disponibles" (out of stock) modal
        self.page.wait_for_timeout(2000)

        out_of_stock_modal = self.page.query_selector('#dialog-title')
        if out_of_stock_modal:
            modal_text = out_of_stock_modal.inner_text()
            if "Opciones Disponibles" in modal_text:
                self._log_step(
                    step,
                    f"OUT OF STOCK: Product {product_code} has no available stock. Modal 'Opciones Disponibles' detected.",
                    level="WARNING",
                    details={"product_code": product_code, "quantity": quantity, "reason": "no_stock"},
                )
                # Close the modal
                try:
                    close_btn = self.page.query_selector('[data-testid="icon-outlined-navigation-close"]')
                    if close_btn:
                        close_btn.click()
                        self.page.wait_for_timeout(1000)
                        self._log_step(step, f"Closed 'Opciones Disponibles' modal for {product_code}")
                    else:
                        # Fallback: try the parent button
                        self.page.click('button:has([data-testid="icon-outlined-navigation-close"])')
                        self.page.wait_for_timeout(1000)
                        self._log_step(step, f"Closed modal via fallback for {product_code}")
                except Exception as e:
                    self._log_step(step, f"Could not close modal for {product_code}: {e}", level="WARNING")
                    self._take_screenshot(f"modal_close_fail_{product_code}")

                raise ProductAddError(
                    f"Product {product_code} out of stock (Opciones Disponibles modal)",
                    step=step,
                    details=f"product={product_code}, qty={quantity}, reason=no_stock",
                )

        self._log_step(step, f"Product {product_code} x{quantity} added ✓")

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
