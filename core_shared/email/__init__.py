"""
core_shared.email - Servicio de correo electrónico vía Gmail API (OAuth2).

Uso:
    from core_shared.email import GmailSender

    sender = GmailSender(token_path="token.json", credentials_path="credentials_oauth.json")
    sender.send(
        to="consultora@example.com",
        subject="Resultados GSP",
        html_body="<h1>Hola</h1>",
    )
"""

from core_shared.email.gmail_sender import GmailSender
from core_shared.email.html_templates import build_results_email

__all__ = ["GmailSender", "build_results_email"]
