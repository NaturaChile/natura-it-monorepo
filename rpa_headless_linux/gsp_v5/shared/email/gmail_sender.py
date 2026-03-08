"""
Gmail API sender con OAuth2 y renovación automática de token.

Credenciales OAuth embebidas — no requiere credentials_oauth.json externo.
El token.json se refresca automáticamente; si está corrupto o vencido
sin refresh_token, se regenera via navegador (run_local_server).

Requires:
    pip install google-auth google-auth-oauthlib google-api-python-client

⚠️  INACTIVO — módulo aislado, no importado por ningún proceso todavía.
"""

import base64
import json
import logging
import mimetypes
import os
import re
import tempfile
from datetime import datetime, timezone
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path
from typing import List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Credenciales OAuth embebidas (client_id de la cuenta Natura IT)
# ═══════════════════════════════════════════════════════════════════════════
CLIENT_CONFIG = {
    "installed": {
        "client_id": "750447830718-ovpklqnoah5s7fjprvj3kr9girgj4c9f.apps.googleusercontent.com",
        "client_secret": "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",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]

# Ruta default del token: junto a este archivo
_DEFAULT_TOKEN_PATH = str(Path(__file__).parent / "token.json")


class GmailSender:
    """
    Envío de correos vía Gmail API con OAuth2 + renovación de token.

    Flujo de autenticación:
      1. Carga token.json existente
      2. Si expiró y tiene refresh_token → refresca automáticamente
      3. Si no hay token o falló el refresh → abre navegador para login
      4. Guarda el token renovado en disco

    Ejemplo::

        sender = GmailSender()
        sender.send(
            to="consultora@natura.cl",
            subject="Tu carrito está listo",
            html_body=build_consultora_email(...),
        )
    """

    def __init__(
        self,
        token_path: Optional[str] = None,
        sender_email: str = "me",
    ):
        """
        Args:
            token_path: Ruta al token.json. Default: shared/email/token.json
            sender_email: "me" = el dueño del token.
        """
        self.token_path = token_path or _DEFAULT_TOKEN_PATH
        self.sender_email = sender_email
        self._service = None
        self._creds = None

    # ------------------------------------------------------------------
    # Autenticación con renovación automática
    # ------------------------------------------------------------------
    def _authenticate(self) -> Credentials:
        """
        Obtiene credenciales válidas.
        Intenta: token existente → refresh → login manual (navegador).
        """
        creds = self._load_token()

        # Refrescar si expiró pero tiene refresh_token
        if creds and creds.expired and creds.refresh_token:
            creds = self._refresh_token(creds)

        # Si no hay creds válidas → login manual
        if not creds or not creds.valid:
            creds = self._interactive_login()

        return creds

    def _load_token(self) -> Optional[Credentials]:
        """Carga token.json si existe y es válido.

        Si no existe en disco pero la variable de entorno GMAIL_TOKEN_JSON
        contiene el JSON del token, lo escribe a disco automáticamente.
        Esto permite inyectar el token via Docker/.env sin copiarlo a mano.
        """
        # Auto-crear token.json desde variable de entorno si no existe
        if not os.path.exists(self.token_path):
            env_token = os.environ.get("GMAIL_TOKEN_JSON", "").strip()
            if env_token:
                logger.info(
                    "Creando token.json desde GMAIL_TOKEN_JSON env var → %s",
                    self.token_path,
                )
                token_dir = os.path.dirname(self.token_path)
                if token_dir:
                    os.makedirs(token_dir, exist_ok=True)
                with open(self.token_path, "w") as f:
                    f.write(env_token)
            else:
                logger.info("No existe token.json en %s", self.token_path)
                return None
        try:
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            logger.info(
                "Token cargado | expiry=%s | has_refresh=%s",
                creds.expiry,
                bool(creds.refresh_token),
            )
            return creds
        except Exception as e:
            logger.warning("token.json corrupto (%s), se re-generará.", e)
            return None

    def _refresh_token(self, creds: Credentials) -> Optional[Credentials]:
        """Intenta refrescar el token. Retorna None si falla."""
        try:
            creds.refresh(Request())
            self._save_token(creds)
            logger.info(
                "Token refrescado OK | nuevo expiry=%s",
                creds.expiry,
            )
            return creds
        except Exception as e:
            logger.warning("Falló refresh del token: %s. Se requiere login manual.", e)
            return None

    def _interactive_login(self) -> Credentials:
        """
        Login via navegador usando las credenciales embebidas.
        No necesita credentials_oauth.json en disco.
        """
        logger.info("Iniciando login interactivo de Gmail (navegador)...")

        # Escribir client config a archivo temporal (InstalledAppFlow lo requiere)
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, prefix="gmail_oauth_"
        )
        try:
            json.dump(CLIENT_CONFIG, tmp)
            tmp.close()

            flow = InstalledAppFlow.from_client_secrets_file(tmp.name, SCOPES)
            creds = flow.run_local_server(port=0)
        finally:
            os.unlink(tmp.name)

        self._save_token(creds)
        logger.info("Token generado OK con scopes de Gmail + Sheets + Drive.")
        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Guarda el token en disco (crea directorios si es necesario)."""
        token_dir = os.path.dirname(self.token_path)
        if token_dir:
            os.makedirs(token_dir, exist_ok=True)
        with open(self.token_path, "w") as f:
            f.write(creds.to_json())
        logger.info("Token guardado en %s", self.token_path)

    # ------------------------------------------------------------------
    # Renovación manual (para scripts CLI)
    # ------------------------------------------------------------------
    def renovar_token(self) -> None:
        """
        Fuerza la renovación del token eliminando el existente.
        Abre navegador para re-autorizar todos los scopes.

        Uso desde CLI::

            from shared.email.gmail_sender import GmailSender
            GmailSender().renovar_token()
        """
        if os.path.exists(self.token_path):
            os.remove(self.token_path)
            logger.info("Token anterior eliminado: %s", self.token_path)

        self._creds = self._interactive_login()
        self._service = None  # Forzar re-init del servicio

        # Verificar que funciona
        try:
            profile = (
                build("gmail", "v1", credentials=self._creds)
                .users()
                .getProfile(userId="me")
                .execute()
            )
            logger.info(
                "Token verificado OK → email: %s, mensajes: %s",
                profile.get("emailAddress"),
                profile.get("messagesTotal"),
            )
        except Exception as e:
            logger.error("Token generado pero falló verificación: %s", e)

    def token_status(self) -> dict:
        """
        Retorna info del estado actual del token (sin refrescar).

        Returns:
            dict con 'exists', 'valid', 'expired', 'expiry', 'email', 'scopes'
        """
        status = {
            "exists": os.path.exists(self.token_path),
            "valid": False,
            "expired": None,
            "expiry": None,
            "has_refresh_token": False,
            "email": None,
            "scopes": [],
            "path": self.token_path,
        }

        if not status["exists"]:
            return status

        try:
            with open(self.token_path) as f:
                data = json.load(f)

            status["scopes"] = data.get("scopes", [])
            status["has_refresh_token"] = bool(data.get("refresh_token"))

            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            status["expired"] = creds.expired
            status["valid"] = creds.valid
            if creds.expiry:
                status["expiry"] = creds.expiry.isoformat()

            # Intentar obtener email sin refrescar
            if creds.valid:
                svc = build("gmail", "v1", credentials=creds)
                profile = svc.users().getProfile(userId="me").execute()
                status["email"] = profile.get("emailAddress")
        except Exception as e:
            status["error"] = str(e)

        return status

    # ------------------------------------------------------------------
    # Servicio Gmail (lazy init)
    # ------------------------------------------------------------------
    @property
    def service(self):
        """Lazy-init del servicio Gmail API (autentica si es necesario)."""
        if self._service is None:
            self._creds = self._authenticate()
            self._service = build("gmail", "v1", credentials=self._creds)
        return self._service

    # ------------------------------------------------------------------
    # Envío de correos
    # ------------------------------------------------------------------
    def send(
        self,
        to: Union[str, List[str]],
        subject: str,
        html_body: str,
        cc: Optional[Union[str, List[str]]] = None,
        bcc: Optional[Union[str, List[str]]] = None,
        text_body: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> dict:
        """
        Envía un correo vía Gmail API.

        Args:
            to: Destinatario(s) principal(es).
            subject: Asunto del correo.
            html_body: Cuerpo HTML del correo.
            cc: Destinatario(s) en copia.
            bcc: Destinatario(s) en copia oculta.
            text_body: Texto plano alternativo (auto-generado si None).
            attachments: Rutas de archivos a adjuntar.
            reply_to: Email para Reply-To header.

        Returns:
            dict con 'id', 'threadId', 'labelIds' del mensaje enviado.
        """
        msg = self._build_message(
            to=to,
            subject=subject,
            html_body=html_body,
            cc=cc,
            bcc=bcc,
            text_body=text_body,
            attachments=attachments,
            reply_to=reply_to,
        )

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        body = {"raw": raw}

        result = (
            self.service.users()
            .messages()
            .send(userId=self.sender_email, body=body)
            .execute()
        )

        logger.info(
            "Correo enviado → %s | subject='%s' | ID: %s",
            self._format_recipients(to),
            subject[:50],
            result["id"],
        )
        return result

    def send_bulk(
        self,
        recipients: List[dict],
        subject_template: str,
        html_builder: callable,
        cc_map: Optional[dict] = None,
        delay_seconds: float = 0.5,
    ) -> dict:
        """
        Envío masivo personalizado con resumen.

        Args:
            recipients: Lista de dicts. Cada dict debe tener 'email'.
            subject_template: Template del asunto con {placeholders}.
            html_builder: Función(dict) → HTML string.
            cc_map: Dict {nivel: [emails]} para copiar según nivel.
            delay_seconds: Pausa entre envíos (evitar rate-limit Gmail).

        Returns:
            dict con 'sent', 'failed', 'total', 'results'.

        Ejemplo::

            summary = sender.send_bulk(
                recipients=[
                    {"email": "ana@natura.cl", "nombre": "Ana", "data": {...}},
                ],
                subject_template="Tu carrito - {nombre}",
                html_builder=lambda r: build_consultora_email(**r["data"]),
            )
        """
        import time

        results = []
        total = len(recipients)

        for i, recipient in enumerate(recipients, 1):
            email = recipient.get("email", "")
            if not email:
                logger.warning("[%d/%d] Destinatario sin email, saltando.", i, total)
                results.append({"status": "skipped", "recipient": "", "error": "sin email"})
                continue

            subject = subject_template.format(**recipient)
            html_body = html_builder(recipient)

            cc = None
            if cc_map and "nivel" in recipient:
                cc = cc_map.get(recipient["nivel"])

            try:
                result = self.send(to=email, subject=subject, html_body=html_body, cc=cc)
                result["status"] = "sent"
                result["recipient"] = email
                results.append(result)
                logger.info("[%d/%d] Enviado → %s", i, total, email)
            except Exception as e:
                logger.error("[%d/%d] Error → %s: %s", i, total, email, e)
                results.append({"status": "error", "recipient": email, "error": str(e)})

            # Pausa entre envíos para no saturar la API de Gmail
            if i < total and delay_seconds > 0:
                time.sleep(delay_seconds)

        sent = sum(1 for r in results if r.get("status") == "sent")
        failed = sum(1 for r in results if r.get("status") == "error")
        skipped = sum(1 for r in results if r.get("status") == "skipped")

        summary = {
            "total": total,
            "sent": sent,
            "failed": failed,
            "skipped": skipped,
            "results": results,
        }

        logger.info(
            "Envío masivo completado: %d/%d enviados, %d fallidos, %d saltados",
            sent, total, failed, skipped,
        )
        return summary

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_message(
        self,
        to: Union[str, List[str]],
        subject: str,
        html_body: str,
        cc: Optional[Union[str, List[str]]] = None,
        bcc: Optional[Union[str, List[str]]] = None,
        text_body: Optional[str] = None,
        attachments: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
    ) -> MIMEMultipart:
        """Construye el mensaje MIME completo."""
        if attachments:
            msg = MIMEMultipart("mixed")
            body_part = MIMEMultipart("alternative")
        else:
            msg = MIMEMultipart("alternative")
            body_part = msg

        msg["To"] = self._format_recipients(to)
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = self._format_recipients(cc)
        if bcc:
            msg["Bcc"] = self._format_recipients(bcc)
        if reply_to:
            msg["Reply-To"] = reply_to

        if text_body is None:
            text_body = re.sub(r"<[^>]+>", "", html_body)
            text_body = re.sub(r"\s+", " ", text_body).strip()

        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))

        if attachments:
            msg.attach(body_part)
            for filepath in attachments:
                self._attach_file(msg, filepath)

        return msg

    @staticmethod
    def _attach_file(msg: MIMEMultipart, filepath: str) -> None:
        """Adjunta un archivo al mensaje."""
        if not os.path.exists(filepath):
            logger.warning("Adjunto no encontrado: %s", filepath)
            return

        content_type, _ = mimetypes.guess_type(filepath)
        if content_type is None:
            content_type = "application/octet-stream"

        main_type, sub_type = content_type.split("/", 1)
        filename = os.path.basename(filepath)

        with open(filepath, "rb") as f:
            attachment = MIMEBase(main_type, sub_type)
            attachment.set_payload(f.read())

        encoders.encode_base64(attachment)
        attachment.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(attachment)

    @staticmethod
    def _format_recipients(recipients: Union[str, List[str]]) -> str:
        """Convierte lista de emails a string separado por comas."""
        if isinstance(recipients, str):
            return recipients
        return ", ".join(recipients)
