# ──────────────────────────────────────────────
# Custom Exceptions
# ──────────────────────────────────────────────
from __future__ import annotations


class GSPBotError(Exception):
    """Base exception for all GSP bot errors."""

    def __init__(self, message: str, step: str = "", consultora: str = "", details: str = ""):
        self.step = step
        self.consultora = consultora
        self.details = details
        super().__init__(message)


class LoginError(GSPBotError):
    """Failed to log in to GSP."""
    pass


class ConsultoraSearchError(GSPBotError):
    """Failed to search / select consultora."""
    pass


class CycleSelectionError(GSPBotError):
    """Failed to select the cycle."""
    pass


class CartError(GSPBotError):
    """Failed to open cart or add products."""
    pass


class ProductAddError(GSPBotError):
    """Failed to add a specific product to the cart."""
    pass


class NavigationError(GSPBotError):
    """Page navigation timed out or failed."""
    pass


class SessionExpiredError(GSPBotError):
    """The browser session expired and needs re-login."""
    pass
