"""
Gmail API sender using OAuth2 credentials.

Requires:
    pip install google-auth google-auth-oauthlib google-api-python-client

Token must include scope: https://mail.google.com/
"""

import base64
import mimetypes
import os
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders
from typing import List, Optional, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ---------------------------------------------------------------------------
# Scopes
# ---------------------------------------------------------------------------
GMAIL_SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
]


class GmailSender:
    """
    Envío de correos vía Gmail API con OAuth2.

    Soporta:
    - Correos HTML con texto plano alternativo
    - Múltiples destinatarios (to, cc, bcc)
    - Adjuntos de archivos
    - Auto-refresh del token

    Ejemplo:
        sender = GmailSender()
        sender.send(
            to="consultora@natura.cl",
            subject="Resultados del proceso",
            html_body="<h1>Resumen</h1><p>Todo OK</p>",
            cc=["supervisor@natura.cl"],
        )
    """

    def __init__(
        self,
        token_path: str = "token.json",
        credentials_path: str = "credentials_oauth.json",
        sender_email: str = "me",
    ):
        """
        Args:
            token_path: Ruta al token.json con OAuth2 credentials.
            credentials_path: Ruta al credentials_oauth.json (client secrets).
            sender_email: Email del remitente. "me" = el dueño del token.
        """
        self.token_path = token_path
        self.credentials_path = credentials_path
        self.sender_email = sender_email
        self._service = None
        self._creds = None

    # ------------------------------------------------------------------
    # Autenticación
    # ------------------------------------------------------------------
    def _authenticate(self) -> Credentials:
        """Obtiene credenciales válidas (refresca o pide login manual)."""
        creds = None

        # 1. Cargar token existente
        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.token_path, GMAIL_SCOPES
                )
            except Exception:
                print("⚠️  token.json corrupto, se re-generará.")
                creds = None

        # 2. Refrescar si expiró
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                print("🔄 Token refrescado automáticamente.")
                self._save_token(creds)
            except Exception as e:
                print(f"⚠️  Falló refresh: {e}")
                creds = None

        # 3. Login manual si no hay credenciales válidas
        if not creds or not creds.valid:
            if not os.path.exists(self.credentials_path):
                raise FileNotFoundError(
                    f"❌ No se encontró '{self.credentials_path}'. "
                    "Necesario para autenticación manual."
                )
            print("🔵 Abriendo navegador para autorizar Gmail...")
            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_path, GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            print("✅ Token generado con scope de Gmail.")

        return creds

    def _save_token(self, creds: Credentials) -> None:
        """Guarda el token en disco."""
        with open(self.token_path, "w") as f:
            f.write(creds.to_json())

    # ------------------------------------------------------------------
    # Servicio Gmail
    # ------------------------------------------------------------------
    @property
    def service(self):
        """Lazy-init del servicio Gmail API."""
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
            text_body: Texto plano alternativo (se genera automáticamente si es None).
            attachments: Lista de rutas de archivos a adjuntar.
            reply_to: Email para Reply-To header.

        Returns:
            dict con 'id', 'threadId', 'labelIds' del mensaje enviado.

        Raises:
            Exception: Si falla el envío.
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

        print(f"✅ Correo enviado → {self._format_recipients(to)} | ID: {result['id']}")
        return result

    def send_bulk(
        self,
        recipients: List[dict],
        subject_template: str,
        html_builder: callable,
        cc_map: Optional[dict] = None,
    ) -> List[dict]:
        """
        Envío masivo personalizado por consultora.

        Args:
            recipients: Lista de dicts con datos de cada destinatario.
                        Cada dict debe tener al menos 'email' y 'nombre'.
            subject_template: Template del asunto con {placeholders}.
            html_builder: Función que recibe un dict y retorna HTML.
            cc_map: Dict {nivel: [emails]} para copiar según nivel.

        Returns:
            Lista de resultados de envío.

        Ejemplo:
            results = sender.send_bulk(
                recipients=[
                    {"email": "ana@natura.cl", "nombre": "Ana", "nivel": "GZ", "data": {...}},
                    {"email": "luis@natura.cl", "nombre": "Luis", "nivel": "DN", "data": {...}},
                ],
                subject_template="Resultados GSP - {nombre}",
                html_builder=lambda r: build_results_email(r["nombre"], r["data"]),
                cc_map={"GZ": ["gz_lider@natura.cl"], "DN": ["dn_lider@natura.cl"]},
            )
        """
        results = []
        total = len(recipients)

        for i, recipient in enumerate(recipients, 1):
            email = recipient["email"]
            subject = subject_template.format(**recipient)
            html_body = html_builder(recipient)

            # Resolver CC según nivel
            cc = None
            if cc_map and "nivel" in recipient:
                cc = cc_map.get(recipient["nivel"])

            try:
                result = self.send(
                    to=email,
                    subject=subject,
                    html_body=html_body,
                    cc=cc,
                )
                result["status"] = "sent"
                result["recipient"] = email
                results.append(result)
                print(f"  [{i}/{total}] ✅ {email}")
            except Exception as e:
                print(f"  [{i}/{total}] ❌ {email}: {e}")
                results.append({"status": "error", "recipient": email, "error": str(e)})

        sent = sum(1 for r in results if r["status"] == "sent")
        print(f"\n📊 Envío masivo: {sent}/{total} exitosos")
        return results

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

        # Si hay adjuntos, usar mixed; si no, alternative
        if attachments:
            msg = MIMEMultipart("mixed")
            body_part = MIMEMultipart("alternative")
        else:
            msg = MIMEMultipart("alternative")
            body_part = msg

        # Headers
        msg["To"] = self._format_recipients(to)
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = self._format_recipients(cc)
        if bcc:
            msg["Bcc"] = self._format_recipients(bcc)
        if reply_to:
            msg["Reply-To"] = reply_to

        # Cuerpo: texto plano + HTML
        if text_body is None:
            # Generar texto plano básico removiendo tags HTML
            import re
            text_body = re.sub(r"<[^>]+>", "", html_body)
            text_body = re.sub(r"\s+", " ", text_body).strip()

        body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))

        # Si hay adjuntos, agregar cuerpo y luego adjuntos
        if attachments:
            msg.attach(body_part)
            for filepath in attachments:
                self._attach_file(msg, filepath)

        return msg

    @staticmethod
    def _attach_file(msg: MIMEMultipart, filepath: str) -> None:
        """Adjunta un archivo al mensaje."""
        if not os.path.exists(filepath):
            print(f"⚠️  Adjunto no encontrado: {filepath}")
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
