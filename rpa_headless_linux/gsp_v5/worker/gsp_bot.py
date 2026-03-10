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
from typing import Callable, Optional
import pandas as pd
import tempfile

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
    OutOfStockError,
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
        self.progress_callback: Optional[Callable] = None
        # Tracks whether the cart had items at arrival (audit count)
        self.cart_initial_count: int = 0

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

        # Build Chromium args dynamically
        chrome_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-http2",
            "--disable-quic",
            "--disable-blink-features=AutomationControlled",
            "--dns-prefetch-disable",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
            "--ignore-certificate-errors",
        ]

        # Proxy support: use corporate proxy if configured in env
        proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy")
        pw_proxy = None
        if proxy_url:
            logger.info("proxy_detected", proxy=proxy_url, worker=self.worker_id)
            pw_proxy = {"server": proxy_url}
        else:
            # Only disable proxy when we know there isn't one
            chrome_args.append("--no-proxy-server")

        self._browser = self._pw.chromium.launch(
            headless=self.settings.playwright_headless,
            slow_mo=self.settings.playwright_slow_mo,
            args=chrome_args,
            proxy=pw_proxy,
        )
        # Anti-detection headers used in troubleshooting runs
        extra_headers = {
            "sec-ch-ua": '"Chromium";v="121", "Not_A Brand";v="8"',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-mobile": "?0",
        }

        self._context = self._browser.new_context(
            viewport={"width": 1366, "height": 768},
            locale="es-CL",
            timezone_id="America/Santiago",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
            extra_http_headers=extra_headers,
            ignore_https_errors=True,
        )

        # Hide automation flag to reduce bot detection
        try:
            self._context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => false});")
        except Exception:
            # Non-fatal: if add_init_script fails for some reason, continue
            logger.info("add_init_script_failed", worker=self.worker_id)
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

        # Notify Celery task of progress (visible in Flower dashboard)
        if self.progress_callback:
            try:
                self.progress_callback(step, message, details)
            except Exception:
                pass  # Non-fatal: don't break bot flow for callback errors

    def get_step_log(self) -> list[dict]:
        return list(self._step_log)

    def _preflight_check(self, url: str, step: str = "preflight") -> None:
        """Verify network connectivity from the container before Playwright navigates.

        Uses Python's urllib (not Chromium) so we can distinguish between
        a Docker networking issue and a Playwright/Chromium issue.
        Tests: DNS -> TCP -> TLS -> HTTP, with proxy support.
        """
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(url)
        host = parsed.netloc
        base = f"{parsed.scheme}://{host}"

        # Log proxy configuration
        proxy_env = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
        self._log_step(step, f"Preflight target: {base} | proxy: {proxy_env or 'none'}")

        # --- Step 1: DNS resolution ---
        try:
            ip = socket.getaddrinfo(host, 443)[0][4][0]
            self._log_step(step, f"DNS OK: {host} -> {ip}")
            dns_ok = True
        except Exception as e:
            self._log_step(step, f"DNS FAILED for {host}: {e}", level="ERROR")
            dns_ok = False
            raise LoginError(
                f"DNS resolution failed for {host}: {e}. "
                f"Check container DNS config (dns: in docker-compose).",
                step=step,
            )

        # --- Step 2: TCP connection ---
        try:
            s = socket.create_connection((host, 443), timeout=10)
            s.close()
            self._log_step(step, f"TCP OK: connected to {host}:443")
            tcp_ok = True
        except Exception as e:
            self._log_step(step, f"TCP FAILED to {host}:443: {e}", level="ERROR")
            tcp_ok = False
            # If TCP fails, it's a firewall/routing issue.
            # If there's a proxy, urllib might still work via the proxy.
            self._log_step(step, "TCP direct failed. Will try HTTP with proxy if configured.", level="WARNING")

        # --- Step 3: HTTP request (urllib, respects proxy env vars) ---
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        for attempt in range(1, 4):
            try:
                req = urllib.request.Request(base, method="HEAD")
                req.add_header("User-Agent", "GSPBot-preflight/1.0")
                resp = urllib.request.urlopen(req, timeout=15, context=ctx)
                self._log_step(step, f"Preflight OK: {base} -> HTTP {resp.status}")
                return
            except Exception as e:
                self._log_step(step, f"Preflight attempt {attempt}/3 failed: {e}", level="WARNING")
                if attempt < 3:
                    time.sleep(3)

        # All 3 preflight attempts failed
        # If DNS/TCP checks passed but urllib failed, continue with a warning
        # because the issue may be specific to urllib (or intermittent). Let
        # Playwright attempt the navigation and capture browser-level errors.
        if dns_ok and tcp_ok:
            self._log_step(
                step,
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
        self._log_step(step, "Clicking 'Para otra Consultora' (Force Mode)")

        try:
            # Use the precise input radio and click with force (mirrors reference script)
            radio = self.page.locator('input[data-testid="impersonation-radio-button"][value="otherCn"]')
            radio.wait_for(state="visible", timeout=30000)
            radio.click(force=True)

            # Click Accept if present
            try:
                self.page.click('button[data-testid="impersonation-accept-button"]')
            except Exception:
                self._log_step(step, "Impersonation accept button not present; continuing", level="DEBUG")

            # Wait for consultora input
            self.page.wait_for_selector('#naturaCode', state="visible", timeout=30000)

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
            # Ported from reference script: wait for product grid/cards to confirm page load
            self._log_step(step, "Waiting for product grid to confirm load...")
            self.page.wait_for_selector('div[data-testid="cards-list"]', state="visible", timeout=60000)
            self.page.wait_for_selector('div[data-testid="cards-list"] >> div[data-testid^="card-"]', state="visible", timeout=30000)
            # Stabilization pause as in reference script
            self.page.wait_for_timeout(2000)

            # Now open the cart (use button selector from reference)
            self._log_step(step, "Opening cart")
            self.page.click('button[data-testid="icon-bag"]')
            # Validate cart opened by waiting for quick-order input
            try:
                self.page.wait_for_selector('#code-and-quantity-code', state="visible", timeout=10000)
            except PWTimeout:
                ss = self._take_screenshot("cart_input_wait")
                raise CartError("Cart input did not appear after clicking bag", step=step, details=f"screenshot={ss}")

        except PWTimeout:
            ss = self._take_screenshot("cart_wait")
            raise CartError("Shopping bag icon not found", step=step, details=f"screenshot={ss}")

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
        # Save HTML snapshot after successful clear for post-mortem review
        try:
            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            html_path = self.settings.screenshot_dir / f"cart_after_clear_{ts}_{self.order_id}.html"
            html_path.parent.mkdir(parents=True, exist_ok=True)
            with open(html_path, 'w', encoding='utf-8') as hf:
                hf.write(self.page.content())
            self._log_step(step, f"Saved cart HTML after clear: {html_path}")
        except Exception as save_html_ex:
            self._log_step(step, f"Failed saving cart HTML after clear: {save_html_ex}", level="WARNING")

        return removed_count

    # ── STEP 7: Add product to cart ───────────

    def add_product(self, product_code: str, quantity: int) -> None:
        step = "add_product"
        self._log_step(step, f"Adding product {product_code} x{quantity}")

        try:
            # 1. Fill product code
            self.page.fill('#code-and-quantity-code', product_code)

            # 2. Quantity: use the hierarchical selector from the script
            qty_container = self.page.locator('div[data-testid="code-and-quantity-counter"]')
            qty_input = qty_container.locator('input[inputmode="numeric"]')
            qty_input.wait_for(state="visible", timeout=15000)

            # Focus and fill
            qty_input.click()
            qty_input.fill(str(quantity))

            # 3. Click Add
            self.page.click('button[data-testid="button-add-to-basket"]')

            # 4. Validate success toast
            self.page.wait_for_selector('div:has-text("¡Producto agregado con éxito!")', state="visible", timeout=10000)
            self._log_step(step, f"Product {product_code} added ✓")
            return

        except Exception as e:
            ss = self._take_screenshot(f"add_product_error_{product_code}")
            raise ProductAddError(f"Failed to add product {product_code}: {e}", step=step, details=f"screenshot={ss}")

    # ── Bulk upload helpers ─────────────────────

    def _generate_order_excel(self, products: list[dict]) -> str:
        """Generate a temporary .xlsx file suitable for the bulk upload.

        Returns the absolute path to the created file.
        """
        # Log the exact product codes we will place in the Excel
        self._log_step("excel_generation", f"Preparing bulk upload for {len(products)} products: {[p['product_code'] for p in products]}")
        self._log_step("file_generation", "Generating .xlsx for bulk upload")
        data = []
        for p in products:
            data.append({
                "CÓDIGO": p["product_code"],
                "QTDE": p.get("quantity", 1),
            })

        df = pd.DataFrame(data)

        # Crear archivo temporal seguro
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
            tmp_path = tmp.name

        df.to_excel(tmp_path, index=False)
        self._log_step("file_generation", f"Generated temporary order file: {tmp_path}")
        return tmp_path

    def _is_at_cart(self) -> bool:
        """Check if we're at the cart page by URL ONLY.

        IMPORTANT: Do NOT use element-based fallbacks — elements like
        #code-and-quantity-code, button-add-to-basket, and even input[type='file']
        may or may not exist depending on whether the import button has been
        clicked. The ONLY reliable indicator is the URL containing '/cart'.
        """
        url = self.page.url or ""
        return "/cart" in url

    def _cleanup_cart(self, step: str) -> int:
        """Audit and remove existing products from the cart.

        Flow:
          1. Wait for cart content to render (up to 10s for item rows)
          2. Audit every item: code, name, qty → log
          3. Click "Vaciar carrito" to bulk-clear (wait for button visibility)
          4. Handle confirmation dialog if present
          5. Verify items disappeared from DOM
          6. Fallback: delete individually via trash icon

        Real GSP cart DOM structure:
          li.row-products__container              → each product row
            span.row-products__info__title         → product name
            span.row-products__info__data >> span  → product code
            input.form-control[value]              → quantity
          button:has-text("Vaciar carrito")        → bulk clear (only when items exist)
        """
        try:
            # ── Wait for cart content to fully render ──
            self._log_step(step, "Waiting for cart content to render...")
            has_items = False

            # Primary selector used across versions
            primary_sel = 'li.row-products__container'
            try:
                self.page.wait_for_selector(primary_sel, state='attached', timeout=10000)
                has_items = True
                self._log_step(step, "Cart item rows detected in DOM (primary selector)")
            except Exception:
                # Try alternative selectors if primary not found
                alt_selectors = [
                    'ul.bag-items li.row-products__container',
                    'div.row-products__container',
                    'ul.bag-items li',
                    'li[class*="row-products"]',
                    'div.row-products__item',
                ]
                for sel in alt_selectors:
                    try:
                        if self.page.locator(sel).count() > 0:
                            has_items = True
                            self._log_step(step, f"Cart items detected via alternative selector: {sel}")
                            break
                    except Exception:
                        continue

                if not has_items:
                    self._log_step(step, "No cart item rows found after 10s wait (all selectors)")

            # Double-check: if no items via selector, also look for "Vaciar carrito"
            # (button only appears when there are items)
            if not has_items:
                vaciar_check = self.page.locator('button:has-text("Vaciar carrito")')
                if vaciar_check.count() > 0:
                    self._log_step(step, "'Vaciar carrito' button present despite no item rows — clicking to be safe")
                    # Record that cart likely had items (button present)
                    try:
                        self.cart_initial_count = 1
                    except Exception:
                        pass
                    try:
                        vaciar_check.first.click(timeout=5000)
                        self.page.wait_for_timeout(3000)
                    except Exception as e:
                        self._log_step(step, f"Safety Vaciar click failed: {e}", level="WARNING")
                else:
                    self._log_step(step, "No existing items in cart ✓")
                return 0

            # Small extra wait for DOM to stabilize
            self.page.wait_for_timeout(1500)

            # ── Phase 1: Audit — log every item currently in the cart ──
            rows = self.page.locator('li.row-products__container')
            # If rows are not found with primary selector, try alternatives for iteration
            if rows.count() == 0:
                for sel in ['ul.bag-items li.row-products__container', 'div.row-products__container', 'ul.bag-items li', 'li[class*="row-products"]']:
                    try:
                        loc = self.page.locator(sel)
                        if loc.count() > 0:
                            rows = loc
                            self._log_step(step, f"Using alternative rows locator for audit: {sel}")
                            break
                    except Exception:
                        continue
            count = rows.count()
            # Record initial count observed during audit
            try:
                self.cart_initial_count = int(count)
            except Exception:
                self.cart_initial_count = count if isinstance(count, int) else 0
            self._log_step(step, f"Auditing {count} item(s) in cart...")

            cart_items: list[dict] = []
            for i in range(count):
                row = rows.nth(i)
                try:
                    name = row.locator('span.row-products__info__title').first.inner_text(timeout=3000)
                except Exception:
                    name = "(unknown)"
                try:
                    code = row.locator('span.row-products__info__data >> span').first.inner_text(timeout=3000)
                except Exception:
                    code = "(unknown)"
                try:
                    qty = row.locator('input.form-control').first.get_attribute('value') or "?"
                except Exception:
                    qty = "?"
                cart_items.append({"code": code.strip(), "name": name.strip(), "qty": qty.strip()})
                self._log_step(step, "  Item {}: code={} qty={} name={}".format(i + 1, code.strip(), qty.strip(), name.strip()))

            summary = ["{} x{}".format(it["code"], it["qty"]) for it in cart_items]
            self._log_step(
                step,
                f"Found {count} existing item(s) in cart: {summary}",
                details={"cart_items": cart_items},
            )

            # ── Phase 2: Click "Vaciar carrito" — robust locator + diagnostics + fallbacks ──
            # Prefer stable ARIA/role selectors over fragile class names
            clicked = False
            try:
                # Try role-based locator first (more stable than classes)
                try:
                    vaciar_btn = self.page.get_by_role('button', name='Vaciar carrito')
                except Exception:
                    vaciar_btn = None

                # Fallback to text-based locator if role API didn't find it
                if not vaciar_btn or vaciar_btn.count() == 0:
                    vaciar_btn = self.page.locator('button:has-text("Vaciar carrito")')

                # Diagnostics: record locator state before attempting click
                try:
                    btn_count = vaciar_btn.count() if vaciar_btn is not None else 0
                except Exception:
                    btn_count = 0

                ss_diag = None
                if btn_count == 0:
                    self._log_step(step, "'Vaciar carrito' button not found via role/text locators", level="WARNING")
                else:
                    el = vaciar_btn.first
                    try:
                        visible = el.is_visible()
                    except Exception:
                        visible = False
                    try:
                        enabled = el.is_enabled()
                    except Exception:
                        enabled = True
                    try:
                        inner = el.inner_text(timeout=2000)
                    except Exception:
                        inner = None
                    try:
                        bbox = el.bounding_box()
                    except Exception:
                        bbox = None

                    self._log_step(step, f"Vaciar diagnostics: count={btn_count} visible={visible} enabled={enabled} inner={inner} bbox={bbox}")

                    # Ensure the element is in view
                    try:
                        el.evaluate('e => e.scrollIntoView({block: "center"})')
                    except Exception:
                        pass

                    # Try clicking using a sequence of fallbacks
                    try:
                        el.click(timeout=5000)
                        clicked = True
                    except Exception:
                        try:
                            el.evaluate('e => { e.focus(); e.click(); }')
                            clicked = True
                        except Exception:
                            try:
                                # Try clicking the inner span (MUI structure)
                                span = el.locator('span:has-text("Vaciar carrito")')
                                if span.count() > 0:
                                    span.first.click(timeout=4000)
                                    clicked = True
                            except Exception:
                                try:
                                    # Force click as last resort
                                    el.click(force=True, timeout=5000)
                                    clicked = True
                                except Exception:
                                    # Mouse click on bounding box center as ultimate fallback
                                    try:
                                        if bbox:
                                            cx = bbox['x'] + bbox['width'] / 2
                                            cy = bbox['y'] + bbox['height'] / 2
                                            self.page.mouse.click(cx, cy)
                                            clicked = True
                                    except Exception:
                                        clicked = False

                    # If clicked is still False, try broader locators
                    if not clicked:
                        alt_locators = [
                            'button.MuiButtonBase-root:has-text("Vaciar carrito")',
                            'button:has(span:has-text("Vaciar carrito"))',
                            'button:has-text("Vaciar carrito")',
                            'text=Vaciar carrito',
                        ]
                        for sel in alt_locators:
                            try:
                                loc = self.page.locator(sel)
                                if loc.count() > 0:
                                    loc.first.evaluate('el => el.click()')
                                    clicked = True
                                    break
                            except Exception:
                                continue

                    # If after attempts not clicked, save diagnostic snapshot
                    if not clicked:
                        try:
                            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                            html_path = self.settings.screenshot_dir / f"vaciar_diag_{ts}_{self.order_id}.html"
                            html_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(html_path, 'w', encoding='utf-8') as hf:
                                hf.write(self.page.content())
                            ss_diag = self._take_screenshot(f"vaciar_diag_{ts}")
                            self._log_step(step, f"Vaciar click failed after fallbacks; saved HTML: {html_path} screenshot: {ss_diag}", level="WARNING")
                        except Exception as diag_ex:
                            self._log_step(step, f"Failed to capture vaciar diagnostics: {diag_ex}", level="WARNING")

                # Handle confirmation dialog — GSP shows "Eliminar" button (natds style)
                self.page.wait_for_timeout(1500)
                confirmed = False
                for confirm_text in ["Eliminar", "Confirmar", "Aceptar", "Sí", "Si", "OK"]:
                    try:
                        # Try role-based first, then text locator
                        try:
                            cb = self.page.get_by_role('button', name=confirm_text)
                            if cb.count() > 0 and cb.first.is_visible(timeout=2000):
                                self._log_step(step, f"Confirmation dialog detected; clicking '{confirm_text}' via role")
                                cb.first.evaluate('el => el.click()')
                                confirmed = True
                                break
                        except Exception:
                            pass

                        cb = self.page.locator('button:has-text("{}")'.format(confirm_text))
                        if cb.count() > 0 and cb.first.is_visible(timeout=3000):
                            self._log_step(step, "Confirmation dialog detected; clicking '{}'".format(confirm_text))
                            try:
                                cb.first.evaluate('el => el.click()')
                            except Exception:
                                cb.first.click(force=True, timeout=5000)
                            confirmed = True
                            break
                    except Exception:
                        continue
                if not confirmed:
                    self._log_step(step, "No confirmation dialog detected after Vaciar carrito click", level="WARNING")

                # Wait for item rows to disappear from DOM
                try:
                    self.page.wait_for_selector(
                        'li.row-products__container',
                        state='detached',
                        timeout=10000,
                    )
                    self._log_step(step, f"Cart emptied successfully ✓ ({count} item(s) removed)")
                    # Save HTML snapshot after successful bulk clear (alt path)
                    try:
                        ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                        html_path = self.settings.screenshot_dir / f"cart_after_clear_{ts}_{self.order_id}.html"
                        html_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(html_path, 'w', encoding='utf-8') as hf:
                            hf.write(self.page.content())
                        self._log_step(step, f"Saved cart HTML after bulk clear: {html_path}")
                    except Exception as save_ex:
                        self._log_step(step, f"Failed saving HTML after bulk clear: {save_ex}", level="WARNING")
                except Exception:
                    # Try alternative checks for remaining items
                    remaining = 0
                    for sel in ['li.row-products__container', 'ul.bag-items li', 'div.row-products__container', 'li[class*="row-products"]']:
                        try:
                            remaining = self.page.locator(sel).count()
                            if remaining > 0:
                                break
                        except Exception:
                            continue

                    if remaining == 0:
                        self._log_step(step, f"Cart emptied successfully ✓ ({count} item(s) removed)")
                        # Save HTML snapshot after successful bulk clear
                        try:
                            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                            html_path = self.settings.screenshot_dir / f"cart_after_clear_{ts}_{self.order_id}.html"
                            html_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(html_path, 'w', encoding='utf-8') as hf:
                                hf.write(self.page.content())
                            self._log_step(step, f"Saved cart HTML after bulk clear: {html_path}")
                        except Exception as save_ex:
                            self._log_step(step, f"Failed saving HTML after bulk clear: {save_ex}", level="WARNING")
                    else:
                        # Capture HTML snapshot and screenshot for diagnosis
                        try:
                            ts = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                            html_content = self.page.content()
                            html_path = self.settings.screenshot_dir / f"cart_discrepancy_{ts}_{self.order_id}.html"
                            html_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(html_path, 'w', encoding='utf-8') as hf:
                                hf.write(html_content)
                            ss = self._take_screenshot(f"cart_discrepancy_{ts}")
                            self._log_step(step, f"Cart still has {remaining} item(s) after Vaciar carrito; saved HTML: {html_path} screenshot: {ss}", level="WARNING")
                        except Exception as snap_ex:
                            self._log_step(step, f"Failed to capture discrepancy snapshot: {snap_ex}", level="WARNING")

            except Exception as vaciar_ex:
                # Fallback: delete items one by one via trash icon
                self._log_step(step, "'Vaciar carrito' button not available ({}); removing individually".format(vaciar_ex), level="WARNING")
                removed = 0
                for attempt_del in range(count + 3):
                    del_btn = self.page.locator('div.row-products__delete button').first
                    try:
                        del_btn.wait_for(state='visible', timeout=5000)
                    except Exception:
                        self._log_step(step, f"No more delete buttons visible after {removed} removals")
                        break
                    try:
                        del_btn.click(timeout=5000)
                        removed += 1
                        self._log_step(step, f"Deleted item {removed}/{count}")
                        # Wait for toast or item to disappear
                        self.page.wait_for_timeout(2000)
                    except Exception as del_ex:
                        self._log_step(step, f"Failed to delete item: {del_ex}", level="WARNING")
                        break
                remaining = 0
                for sel in ['li.row-products__container', 'ul.bag-items li', 'div.row-products__container', 'li[class*="row-products"]']:
                    try:
                        remaining = self.page.locator(sel).count()
                        if remaining > 0:
                            break
                    except Exception:
                        continue
                self._log_step(step, f"Individual cleanup done: {removed} removed, {remaining} remaining")

            # If we reach this point, return any observed removed counts
            if 'removed_count' in locals():
                return removed_count
            if 'removed' in locals():
                return removed
            return 0
        except Exception as audit_ex:
            self._log_step(step, f"Cart audit/cleanup error: {audit_ex}", level="WARNING")
            return 0

    def navigate_to_cart_adaptively(self) -> int:
        """Adaptive navigation loop that ensures we reach the cart page.

        Flow:
          1. Handle popups (cycle, venta directa, LISTO, recover order)
          2. Wait for the product grid (cards-list) to confirm showcase loaded
          3. Navigate directly to /cart URL (NO button click needed)
          4. Confirm URL is /cart, then audit/cleanup existing items

        Raises NavigationError if it cannot reach the cart after attempts.
        """
        step = "navigate_to_cart_adaptively"
        self._log_step(step, "Starting adaptive navigation to cart")

        max_attempts = 14
        for attempt in range(max_attempts):
            try:
                current_url = self.page.url or "(blank)"
                self._log_step(step, f"Attempt #{attempt+1}/{max_attempts} | URL: {current_url}")
                self.page.wait_for_timeout(2500)

                # If already at cart, audit & cleanup and return removed count
                if self._is_at_cart():
                    removed = self._cleanup_cart(step)
                    self._log_step(step, f"Already at cart: removed {removed} items")
                    return removed

                # 1) Handle cycle popup
                try:
                    radios = self.page.locator('input[data-testid="cycle-radio-button"]')
                    if radios.count() > 0:
                        # click first visible option
                        for i in range(radios.count()):
                            try:
                                r = radios.nth(i)
                                if r.is_visible(timeout=1500):
                                    r.evaluate('el => el.click()')
                                    break
                            except Exception:
                                continue
                        self.page.wait_for_timeout(800)
                        try:
                            self.page.locator('[data-testid="cycle-accept-button"]').evaluate('el => el.click()')
                        except Exception:
                            try:
                                self.page.get_by_role('button', name='Aceptar').first.evaluate('el => el.click()')
                            except Exception:
                                self._log_step(step, "Failed to accept cycle popup", level="WARNING")
                        self.page.wait_for_timeout(3000)
                        continue
                except Exception:
                    pass

                # 2) Venta directa quick accept
                try:
                    if self.page.locator('label[for="id_1"]').is_visible(timeout=2000):
                        self.page.locator('label[for="id_1"]').evaluate('el => el.click()')
                        self.page.wait_for_timeout(800)
                        try:
                            self.page.get_by_role('button', name='Aceptar').first.evaluate('el => el.click()')
                        except Exception:
                            pass
                        self.page.wait_for_timeout(3000)
                        continue
                except Exception:
                    pass

                # 3) Generic LISTO dialog
                try:
                    listo = self.page.locator('button:has-text("LISTO")')
                    if listo.count() > 0 and listo.first.is_visible(timeout=2000):
                        listo.first.evaluate('el => el.click()')
                        self.page.wait_for_timeout(2000)
                        continue
                except Exception:
                    pass

                # 4) Recover order dialog
                try:
                    if self.page.get_by_text("Este pedido esta guardado").is_visible(timeout=2000):
                        try:
                            self.page.get_by_role('button', name='Eliminar Pedido').evaluate('el => el.click()')
                        except Exception:
                            pass
                        self.page.wait_for_timeout(3000)
                        continue
                except Exception:
                    pass

                # 5) If product grid is visible, try direct navigation to /cart
                try:
                    cards = self.page.locator('div[data-testid="cards-list"]')
                    grid_visible = cards.count() > 0 and cards.first.is_visible(timeout=3000)
                except Exception:
                    grid_visible = False

                if grid_visible or attempt >= 3:
                    try:
                        from urllib.parse import urlparse
                        parsed = urlparse(self.page.url or "")
                        cart_url = f"{parsed.scheme}://{parsed.netloc}/cart"
                        self._log_step(step, f"Navigating to cart URL: {cart_url}")
                        self.page.goto(cart_url, wait_until="domcontentloaded", timeout=30000)
                        self.page.wait_for_timeout(4000)
                        if self._is_at_cart():
                            removed = self._cleanup_cart(step)
                            self._log_step(step, f"Arrived at cart and cleaned: removed {removed} items")
                            return removed
                    except Exception as e:
                        self._log_step(step, f"Direct navigation failed: {e}", level="WARNING")

                # 6) Midpoint recovery reload
                if attempt == 6:
                    try:
                        self.page.reload()
                        self.page.wait_for_load_state("domcontentloaded", timeout=20000)
                        self.page.wait_for_timeout(3000)
                    except Exception:
                        pass

            except Exception as loop_ex:
                self._log_step(step, f"Adaptive navigation loop error: {loop_ex}", level="WARNING")

        # Give up after attempts: capture screenshot for diagnostics
        ss = self._take_screenshot("cart_navigation_failed")
        self._log_step(step, f"Could not reach cart after {max_attempts} attempts. screenshot={ss}", level="ERROR")
        return 0

    def upload_order_file(self, file_path: str) -> None:
        step = "upload_order_file"
        self._log_step(step, f"Uploading order file... Current URL: {self.page.url}")

        # Some GSP versions require clicking an "Importar" / "Cargar archivo" button
        # before the <input type="file"> element is mounted in the DOM.
        try:
            import_selectors = [
                'button:has-text("Importar")',
                'button:has-text("Cargar")',
                'button:has-text("Subir")',
                'button:has-text("Upload")',
                '[data-testid="import-button"]',
                '[data-testid="upload-button"]',
                'label:has-text("Importar")',
            ]
            import_clicked = False
            for sel in import_selectors:
                try:
                    loc = self.page.locator(sel)
                    if loc.count() > 0 and loc.first.is_visible(timeout=3000):
                        self._log_step(step, f"Found import button via '{sel}'; clicking")
                        loc.first.click(timeout=5000)
                        self.page.wait_for_timeout(2000)
                        import_clicked = True
                        break
                except Exception:
                    continue
            if not import_clicked:
                self._log_step(step, "No import button found; assuming file input is already in DOM", level="DEBUG")
        except Exception as import_err:
            self._log_step(step, f"Import button search error (non-fatal): {import_err}", level="WARNING")

        try:
            self.page.wait_for_selector('input[type="file"]', state="attached", timeout=60000)
            # Use Playwright's set_input_files with selector
            self.page.set_input_files('input[type="file"]', file_path)
            self._log_step(step, "File injected into input; waiting for server processing...")
            # Wait for server-side processing
            self.page.wait_for_timeout(15000)

            # Post-upload validations
            try:
                # ── Check "indisponibles" modal (out-of-stock warning) ──
                indisponibles_detected = False
                try:
                    indisponible_loc = self.page.get_by_text("indisponibles")
                    if indisponible_loc.is_visible(timeout=5000):
                        indisponibles_detected = True
                        self._log_step(step, "⚠️ Detected 'productos indisponibles' modal — some products are out of stock", level="WARNING")
                        ss = self._take_screenshot("indisponibles_modal")
                        self._log_step(step, f"Screenshot of indisponibles modal: {ss}", level="INFO")

                        # Click "Entendido" to dismiss the modal
                        entendido_clicked = False
                        entendido_selectors = [
                            'button:has-text("Entendido")',
                            'span:has-text("Entendido")',
                            'button.Button-gaya',
                            'div.dialog-footer button',
                        ]
                        for sel in entendido_selectors:
                            try:
                                loc = self.page.locator(sel)
                                if loc.count() > 0 and loc.first.is_visible(timeout=3000):
                                    loc.first.click(timeout=5000)
                                    self._log_step(step, f"Clicked 'Entendido' via '{sel}'")
                                    entendido_clicked = True
                                    break
                            except Exception:
                                continue

                        if not entendido_clicked:
                            # Fallback: press Escape or click overlay
                            self._log_step(step, "Could not click Entendido; trying Escape key", level="WARNING")
                            self.page.keyboard.press("Escape")

                        self.page.wait_for_timeout(3000)
                except Exception as e:
                    self._log_step(step, f"Indisponibles check error (non-fatal): {e}", level="WARNING")

                # ── Check "No podemos encontrar los Códigos" modal ──
                if not indisponibles_detected:
                    if self.page.get_by_text("No podemos encontrar los Códigos").is_visible(timeout=5000):
                        # Capture the error text before closing modal
                        msg_el = self.page.locator("div.modal-body")
                        try:
                            error_message = msg_el.inner_text().replace("\n", " ")
                        except Exception:
                            error_message = "(failed to read modal body)"
                        self._log_step("upload_validation", f"GSP Validation Error: {error_message}", level="WARNING", details={"error_text": error_message})

                        try:
                            self.page.get_by_role('button', name='LISTO').first.evaluate('el => el.click()')
                        except Exception:
                            pass
                    else:
                        # Check inconsistencies
                        if self.page.get_by_text("hemos detectado inconsistencias").is_visible(timeout=5000):
                            self._log_step(step, "Detected inconsistencies after upload; closing with LISTO", level="WARNING")
                            try:
                                self.page.locator('button:has-text("LISTO")').first.evaluate('el => el.click()')
                            except Exception:
                                pass
            except Exception as e:
                self._log_step(step, f"Post-upload validation error (non-fatal): {e}", level="WARNING")
        except PWTimeout:
            ss = self._take_screenshot("upload_file_timeout")
            raise NavigationError("File upload input not available", step=step, details=f"screenshot={ss}")

    def verify_cart_contents(self, expected_products: list[dict]) -> dict:
        """
        Scrape the cart DOM to determine which products were actually added
        and which are out of stock.

        Reads two sections:
          1. ul.bag-items → products successfully in cart
          2. section#products-unavailable_section → products "Sin stock"

        Args:
            expected_products: List of dicts with 'product_code' and 'quantity'.

        Returns:
            dict with:
                products_added:    [{"product_code": ..., "quantity": ..., "name": ...}]
                products_failed:   [{"product_code": ..., "quantity": ..., "error": ..., "name": ...}]
                has_out_of_stock:  bool
                cart_screenshot:   str | None
        """
        step = "verify_cart"
        self._log_step(step, "Verifying cart contents after upload...")

        result = {
            "products_added": [],
            "products_failed": [],
            "has_out_of_stock": False,
            "cart_screenshot": None,
        }

        expected_codes = {p["product_code"]: p.get("quantity", 1) for p in expected_products}

        # Wait for cart to stabilize after modal dismissal
        self.page.wait_for_timeout(3000)

        # ── 1. Scrape successfully added products from ul.bag-items ──
        added_codes = set()
        try:
            cart_items = self.page.locator("ul.bag-items li.row-products__container")
            count = cart_items.count()
            self._log_step(step, f"Found {count} products in cart (bag-items)")

            for i in range(count):
                item = cart_items.nth(i)
                try:
                    # Product code is inside: span.row-products__info__data > span
                    # There are multiple .row-products__info__data spans, the one with "Código:" has the code
                    code_el = item.locator("span.row-products__info__data:has-text('Código:') span")
                    code = code_el.inner_text(timeout=3000).strip()

                    # Product name
                    name_el = item.locator("span.row-products__info__title")
                    name = ""
                    try:
                        name = name_el.inner_text(timeout=2000).strip()
                    except Exception:
                        pass

                    added_codes.add(code)
                    qty = expected_codes.get(code, 1)
                    result["products_added"].append({
                        "product_code": code,
                        "quantity": qty,
                        "name": name,
                    })
                    self._log_step(step, f"  ✓ In cart: {code} — {name}")
                except Exception as e:
                    self._log_step(step, f"  Could not read cart item {i}: {e}", level="WARNING")
        except Exception as e:
            self._log_step(step, f"Error scraping bag-items: {e}", level="WARNING")

        # ── 2. Scrape out-of-stock products from #products-unavailable_section ──
        oos_codes = set()
        try:
            unavailable_section = self.page.locator("section#products-unavailable_section")
            if unavailable_section.count() > 0 and unavailable_section.is_visible(timeout=5000):
                oos_items = unavailable_section.locator("li.products-unavailable_item")
                oos_count = oos_items.count()
                self._log_step(step, f"Found {oos_count} products in 'Productos Agotados' section", level="WARNING")
                result["has_out_of_stock"] = oos_count > 0

                for i in range(oos_count):
                    item = oos_items.nth(i)
                    try:
                        code_el = item.locator("span.row-products__info__data:has-text('Código:') span")
                        code = code_el.inner_text(timeout=3000).strip()

                        name_el = item.locator("span.row-products__info__title")
                        name = ""
                        try:
                            name = name_el.inner_text(timeout=2000).strip()
                        except Exception:
                            pass

                        oos_codes.add(code)
                        qty = expected_codes.get(code, 1)
                        result["products_failed"].append({
                            "product_code": code,
                            "quantity": qty,
                            "error": "out_of_stock",
                            "name": name,
                        })
                        self._log_step(step, f"  ✗ Out of stock: {code} — {name}", level="WARNING")
                    except Exception as e:
                        self._log_step(step, f"  Could not read unavailable item {i}: {e}", level="WARNING")
            else:
                self._log_step(step, "No 'Productos Agotados' section found — all products should be in cart")
        except Exception as e:
            self._log_step(step, f"Error scraping unavailable section: {e}", level="WARNING")

        # ── 3. Check for products that are neither in cart nor in unavailable ──
        all_found = added_codes | oos_codes
        for p in expected_products:
            code = p["product_code"]
            if code not in all_found:
                result["products_failed"].append({
                    "product_code": code,
                    "quantity": p.get("quantity", 1),
                    "error": "not_found_in_cart",
                    "name": "",
                })
                self._log_step(step, f"  ? Missing from cart and unavailable: {code}", level="WARNING")

        # Take a screenshot of the final cart state
        result["cart_screenshot"] = self._take_screenshot("cart_verification")

        # Summary
        total_added = len(result["products_added"])
        total_failed = len(result["products_failed"])
        total_oos = len(oos_codes)
        self._log_step(
            step,
            f"Cart verification complete: {total_added} added, {total_failed} failed ({total_oos} out of stock)",
            level="WARNING" if total_failed > 0 else "INFO",
        )

        return result

    # ── Empty Cart Flow ─────────────────────────

    def execute_empty_cart(self, consultora_code: str) -> dict:
        """
        Execute the cart-clearing flow for one consultora.

        Steps:
          1. Login as supervisor
          2. Select "Para otra Consultora"
          3. Search & confirm consultora
          4. Navigate to cart adaptively (handles popups, cycle, etc.)
          5. Clear all items from the cart

        Args:
            consultora_code: The consultora code whose cart should be emptied.

        Returns:
            dict with results and step log.
        """
        start_time = time.time()
        result = {
            "success": False,
            "consultora_code": consultora_code,
            "items_removed": 0,
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

            # Step 5: Navigate to cart (handles popups, cycle selection, etc.)
            # _cleanup_cart is called internally by navigate_to_cart_adaptively
            removed_nav = self.navigate_to_cart_adaptively()
            result["current_step"] = "cart_open"

            # Step 6: Explicit clear of any remaining items
            # (navigate_to_cart_adaptively already calls _cleanup_cart,
            #  but we do a second pass with clear_cart for thoroughness)
            removed_clear = self.clear_cart()
            total_removed = (removed_nav or 0) + (removed_clear or 0)
            result["items_removed"] = total_removed
            result["current_step"] = "cart_cleared"

            result["success"] = True
            self._log_step("cart_cleared", f"Cart emptied for {consultora_code}: {removed} items removed ✓")

        except Exception as e:
            result["error"] = str(e)
            result["error_step"] = getattr(e, "step", "unknown")
            result["screenshot"] = self._take_screenshot(f"error_empty_cart_{result.get('error_step', 'unknown')}")
            self._log_step("error", str(e), level="ERROR")

        result["duration_seconds"] = round(time.time() - start_time, 2)
        result["step_log"] = self.get_step_log()
        return result

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

            # New bulk upload flow:
            # Generate temporary Excel, navigate adaptively to cart, upload file
            excel_path = self._generate_order_excel(products)
            result["current_step"] = "excel_generated"

            # Navigate adaptively to the cart page (handles popups, reloads, etc.)
            removed_nav = self.navigate_to_cart_adaptively()
            result["current_step"] = "cart_open"

            # If the cart had pre-existing items, abort upload and mark as failed
            try:
                if getattr(self, 'cart_initial_count', 0) > 0:
                    msg = f"Cart had pre-existing items ({self.cart_initial_count}) — aborting upload"
                    self._log_step("cart_preexisting", msg, level="ERROR")
                    result["error"] = msg
                    result["error_step"] = "cart_preexisting"
                    result["screenshot"] = self._take_screenshot("cart_preexisting")
                    result["success"] = False
                    return result
            except Exception:
                # Non-fatal: continue if attribute access fails
                pass

            # Upload the generated Excel file
            self.upload_order_file(excel_path)
            result["current_step"] = "file_uploaded"

            # Cleanup temp file
            try:
                os.unlink(excel_path)
            except Exception:
                pass

            # ── Verify what actually landed in the cart ──
            verification = self.verify_cart_contents(products)
            result["current_step"] = "cart_verified"

            result["products_added"] = verification["products_added"]
            result["products_failed"] = verification["products_failed"]
            result["has_out_of_stock"] = verification.get("has_out_of_stock", False)
            result["cart_screenshot"] = verification.get("cart_screenshot")

            # Determine success: order succeeds if at least one product was added
            if len(verification["products_added"]) > 0:
                result["success"] = True
                if verification["has_out_of_stock"]:
                    self._log_step("order_result",
                        f"Order partially completed: {len(verification['products_added'])} added, "
                        f"{len(verification['products_failed'])} failed (out of stock)",
                        level="WARNING")
                else:
                    self._log_step("order_result",
                        f"Order completed: all {len(verification['products_added'])} products added ✓")
            else:
                # No products were added at all
                result["success"] = False
                result["error"] = "No products were added to cart — all may be out of stock"
                result["error_step"] = "cart_verification"
                self._log_step("order_result",
                    "Order FAILED: zero products in cart after upload",
                    level="ERROR")

        except Exception as e:
            result["error"] = str(e)
            result["error_step"] = getattr(e, "step", "unknown")
            result["screenshot"] = self._take_screenshot(f"error_{result.get('error_step', 'unknown')}")
            self._log_step("error", str(e), level="ERROR")

        result["duration_seconds"] = round(time.time() - start_time, 2)
        result["step_log"] = self.get_step_log()
        return result
