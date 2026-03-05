"""
Módulo de correos para GSP Bot v5.

Contiene:
- GmailSender:         envío via Gmail API con OAuth2 + auto-refresh de token
- EmailOrchestrator:   métodos de alto nivel (send_consultora, send_lider, send_gerente)
- Templates:           3 plantillas HTML (consultora, líder, gerente)

Credenciales OAuth embebidas — no requiere credentials_oauth.json externo.
Token se renueva automáticamente; si falla → usa reparar_token.py.

⚠️  INACTIVO — no está conectado a ningún proceso.
    Para activar, importar y llamar manualmente o integrar en api.py / tasks.py.

Ejemplo rápido::

    from shared.email import EmailOrchestrator
    orch = EmailOrchestrator()
    orch.send_consultora(to="ana@natura.cl", consultora_nombre="Ana", ...)
"""

from shared.email.gmail_sender import GmailSender
from shared.email.templates import (
    build_consultora_email,
    build_lider_email,
    build_gerente_email,
)
from shared.email.send_emails import EmailOrchestrator

__all__ = [
    "GmailSender",
    "EmailOrchestrator",
    "build_consultora_email",
    "build_lider_email",
    "build_gerente_email",
]
