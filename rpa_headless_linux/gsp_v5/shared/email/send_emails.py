#!/usr/bin/env python3
"""
Orquestador de envío de correos para GSP Bot v5.

Envía notificaciones a 3 niveles después de un proceso de carga de carritos:
  1. Consultora  → "Tu carrito está listo" (individual)
  2. Líder       → Resumen de su sector (tabla de consultoras)
  3. Gerente     → Reporte gerencial (tabla de líderes)

⚠️  INACTIVO — no conectado al proceso principal.
    Para usar, llamar manualmente o integrar en api.py / tasks.py.

Uso CLI (standalone):
    python -m shared.email.send_emails --preview           # Genera HTMLs de preview
    python -m shared.email.send_emails --test ana@test.cl   # Envía test real
    python -m shared.email.send_emails --token-status       # Verifica token

Uso programático::

    from shared.email.send_emails import EmailOrchestrator

    orch = EmailOrchestrator()

    # Enviar a una consultora
    orch.send_consultora(
        to="consultora@natura.cl",
        consultora_nombre="Maria Celedon",
        cb="2373",
        ciclo="05-2026",
        lider_nombre="Constanza Acevedo",
    )

    # Enviar resumen a líder
    orch.send_lider(
        to="lider@natura.cl",
        lider_nombre="Constanza Acevedo",
        nombre_sector="Acacia",
        total_exitosos=15,
        total_errores=2,
        consultoras=[...],
    )

    # Enviar reporte a gerente
    orch.send_gerente(
        to="gerente@natura.cl",
        gn_nombre="Carolina Mendez",
        nombre_gerencia="Gerencia Sur",
        lideres=[...],
    )
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union

# Asegurar que el root de gsp_v5 esté en sys.path
_gsp_root = Path(__file__).resolve().parents[2]
if str(_gsp_root) not in sys.path:
    sys.path.insert(0, str(_gsp_root))

from shared.email.gmail_sender import GmailSender
from shared.email.templates import (
    build_consultora_email,
    build_lider_email,
    build_gerente_email,
)

logger = logging.getLogger(__name__)


class EmailOrchestrator:
    """
    Orquestador que combina GmailSender + Templates HTML.

    Provee métodos de alto nivel para cada tipo de notificación,
    ocultando la complejidad de auth, templates y envío.
    """

    def __init__(self, token_path: Optional[str] = None):
        """
        Args:
            token_path: Ruta al token.json. Default: shared/email/token.json
        """
        self._sender = GmailSender(token_path=token_path)

    @property
    def sender(self) -> GmailSender:
        """Acceso directo al GmailSender (para operaciones avanzadas)."""
        return self._sender

    # ------------------------------------------------------------------
    # 1. Envío individual a Consultora
    # ------------------------------------------------------------------
    def send_consultora(
        self,
        to: Union[str, List[str]],
        consultora_nombre: str,
        cb: str,
        ciclo: str,
        lider_nombre: str,
        evento: str = "Preventa del Día de las Madres",
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Envía notificación individual a una consultora.

        Args:
            to: Email de la consultora.
            consultora_nombre: Nombre completo.
            cb: Código de negocio.
            ciclo: Ciclo de campaña (ej: "05-2026").
            lider_nombre: Nombre de su líder.
            evento: Nombre del evento/campaña.
            cc: Emails en copia (opcional).
            subject: Asunto personalizado (default: auto-generado).

        Returns:
            dict con resultado del envío.
        """
        html = build_consultora_email(
            consultora_nombre=consultora_nombre,
            cb=cb,
            ciclo=ciclo,
            lider_nombre=lider_nombre,
            evento=evento,
        )

        if subject is None:
            subject = f"🎁 ¡Tu carrito del Live Shopping está listo! - CB {cb}"

        result = self._sender.send(
            to=to,
            subject=subject,
            html_body=html,
            cc=cc,
        )
        logger.info(
            "Correo consultora enviado → %s (CB: %s)", consultora_nombre, cb
        )
        return result

    # ------------------------------------------------------------------
    # 2. Envío de resumen a Líder
    # ------------------------------------------------------------------
    def send_lider(
        self,
        to: Union[str, List[str]],
        lider_nombre: str,
        nombre_sector: str,
        total_exitosos: int,
        total_errores: int,
        consultoras: List[Dict[str, str]],
        evento: str = "Preventa del Día de las Madres",
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Envía resumen de sector a una líder.

        Args:
            to: Email de la líder.
            lider_nombre: Nombre de la líder.
            nombre_sector: Nombre del sector.
            total_exitosos: Carritos cargados OK.
            total_errores: Carritos con problemas.
            consultoras: Lista de dicts {cb, consultora_nombre, estado}.
            evento: Nombre del evento.
            cc: Emails en copia (opcional).
            subject: Asunto personalizado.

        Returns:
            dict con resultado del envío.
        """
        html = build_lider_email(
            lider_nombre=lider_nombre,
            nombre_sector=nombre_sector,
            total_exitosos=total_exitosos,
            total_errores=total_errores,
            consultoras=consultoras,
            evento=evento,
        )

        if subject is None:
            subject = (
                f"🌸 Resultados Live Shopping - Sector {nombre_sector} "
                f"({total_exitosos} listos, {total_errores} pendientes)"
            )

        result = self._sender.send(
            to=to,
            subject=subject,
            html_body=html,
            cc=cc,
        )
        logger.info(
            "Correo líder enviado → %s (Sector: %s, %d/%d)",
            lider_nombre, nombre_sector, total_exitosos,
            total_exitosos + total_errores,
        )
        return result

    # ------------------------------------------------------------------
    # 3. Envío de reporte a Gerente
    # ------------------------------------------------------------------
    def send_gerente(
        self,
        to: Union[str, List[str]],
        gn_nombre: str,
        nombre_gerencia: str,
        lideres: List[Dict[str, str]],
        evento: str = "Preventa del Día de las Madres",
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
    ) -> dict:
        """
        Envía reporte gerencial.

        Args:
            to: Email del gerente.
            gn_nombre: Nombre del gerente.
            nombre_gerencia: Nombre de la gerencia.
            lideres: Lista de dicts {lider_nombre, nombre_sector, carritos_listos, no_cargados}.
            evento: Nombre del evento.
            cc: Emails en copia (opcional).
            subject: Asunto personalizado.

        Returns:
            dict con resultado del envío.
        """
        html = build_gerente_email(
            gn_nombre=gn_nombre,
            nombre_gerencia=nombre_gerencia,
            lideres=lideres,
            evento=evento,
        )

        total_ok = sum(l.get("carritos_listos", 0) for l in lideres)
        total_fail = sum(l.get("no_cargados", 0) for l in lideres)

        if subject is None:
            subject = (
                f"📈 Reporte Live Shopping - {nombre_gerencia} "
                f"({total_ok} listos, {total_fail} pendientes)"
            )

        result = self._sender.send(
            to=to,
            subject=subject,
            html_body=html,
            cc=cc,
        )
        logger.info(
            "Correo gerente enviado → %s (Gerencia: %s, %d OK / %d fail)",
            gn_nombre, nombre_gerencia, total_ok, total_fail,
        )
        return result

    # ------------------------------------------------------------------
    # Envío masivo (los 3 niveles en lote)
    # ------------------------------------------------------------------
    def send_all_notifications(
        self,
        consultoras_data: List[dict],
        lideres_data: List[dict],
        gerentes_data: List[dict],
    ) -> dict:
        """
        Envía todas las notificaciones para un proceso completo.

        Args:
            consultoras_data: Lista de dicts con keys:
                email, consultora_nombre, cb, ciclo, lider_nombre
            lideres_data: Lista de dicts con keys:
                email, lider_nombre, nombre_sector, total_exitosos,
                total_errores, consultoras (list)
            gerentes_data: Lista de dicts con keys:
                email, gn_nombre, nombre_gerencia, lideres (list)

        Returns:
            dict con resumen {consultoras, lideres, gerentes} cada uno con
            {total, sent, failed}
        """
        summary = {"consultoras": [], "lideres": [], "gerentes": []}

        # 1. Consultoras
        logger.info("Enviando %d correos a consultoras...", len(consultoras_data))
        for c in consultoras_data:
            try:
                result = self.send_consultora(
                    to=c["email"],
                    consultora_nombre=c["consultora_nombre"],
                    cb=c["cb"],
                    ciclo=c["ciclo"],
                    lider_nombre=c["lider_nombre"],
                )
                summary["consultoras"].append({"email": c["email"], "status": "sent"})
            except Exception as e:
                logger.error("Error consultora %s: %s", c.get("email"), e)
                summary["consultoras"].append(
                    {"email": c.get("email"), "status": "error", "error": str(e)}
                )

        # 2. Líderes
        logger.info("Enviando %d correos a líderes...", len(lideres_data))
        for l in lideres_data:
            try:
                result = self.send_lider(
                    to=l["email"],
                    lider_nombre=l["lider_nombre"],
                    nombre_sector=l["nombre_sector"],
                    total_exitosos=l["total_exitosos"],
                    total_errores=l["total_errores"],
                    consultoras=l["consultoras"],
                )
                summary["lideres"].append({"email": l["email"], "status": "sent"})
            except Exception as e:
                logger.error("Error líder %s: %s", l.get("email"), e)
                summary["lideres"].append(
                    {"email": l.get("email"), "status": "error", "error": str(e)}
                )

        # 3. Gerentes
        logger.info("Enviando %d correos a gerentes...", len(gerentes_data))
        for g in gerentes_data:
            try:
                result = self.send_gerente(
                    to=g["email"],
                    gn_nombre=g["gn_nombre"],
                    nombre_gerencia=g["nombre_gerencia"],
                    lideres=g["lideres"],
                )
                summary["gerentes"].append({"email": g["email"], "status": "sent"})
            except Exception as e:
                logger.error("Error gerente %s: %s", g.get("email"), e)
                summary["gerentes"].append(
                    {"email": g.get("email"), "status": "error", "error": str(e)}
                )

        # Resumen
        for nivel in ["consultoras", "lideres", "gerentes"]:
            total = len(summary[nivel])
            sent = sum(1 for r in summary[nivel] if r["status"] == "sent")
            failed = total - sent
            logger.info(
                "%s: %d/%d enviados, %d fallidos",
                nivel.title(), sent, total, failed,
            )

        return summary


# ═══════════════════════════════════════════════════════════════════════════
# CLI: Preview y test
# ═══════════════════════════════════════════════════════════════════════════

_SAMPLE_CONSULTORAS = [
    {"cb": "2373", "consultora_nombre": "Maria Alejandra Celedon Fuenzalida", "estado": "Cargado"},
    {"cb": "4165", "consultora_nombre": "Angelina Isabel Cortes Moya", "estado": "No Cargado"},
    {"cb": "5891", "consultora_nombre": "Carmen Rosa Perez Gutierrez", "estado": "Cargado"},
]

_SAMPLE_LIDERES = [
    {"lider_nombre": "Constanza Mariela Acevedo", "nombre_sector": "Acacia",
     "carritos_listos": 15, "no_cargados": 2},
    {"lider_nombre": "Maryorie Priscilla Cortes", "nombre_sector": "Acacia",
     "carritos_listos": 8, "no_cargados": 0},
]


def _preview_mode(output_dir: str = "."):
    """Genera las 3 plantillas como archivos HTML para revisar en navegador."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Consultora
    html1 = build_consultora_email(
        consultora_nombre="Maria Alejandra Celedon Fuenzalida",
        cb="2373",
        ciclo="05-2026",
        lider_nombre="Constanza Mariela Acevedo",
    )
    f1 = out / "preview_consultora.html"
    f1.write_text(html1, encoding="utf-8")

    # 2. Líder
    html2 = build_lider_email(
        lider_nombre="Constanza Mariela Acevedo",
        nombre_sector="Acacia",
        total_exitosos=15,
        total_errores=2,
        consultoras=_SAMPLE_CONSULTORAS,
    )
    f2 = out / "preview_lider.html"
    f2.write_text(html2, encoding="utf-8")

    # 3. Gerente
    html3 = build_gerente_email(
        gn_nombre="Carolina Andrea Mendez Rivera",
        nombre_gerencia="Gerencia Sur",
        lideres=_SAMPLE_LIDERES,
    )
    f3 = out / "preview_gerente.html"
    f3.write_text(html3, encoding="utf-8")

    print("═" * 50)
    print("  PREVIEW GENERADO")
    print("═" * 50)
    print(f"  1. {f1}")
    print(f"  2. {f2}")
    print(f"  3. {f3}")
    print()
    print("  Abre cualquiera en el navegador para ver el resultado.")
    print("═" * 50)


def _test_send(to_email: str, token_path: Optional[str] = None):
    """Envía las 3 plantillas de ejemplo a un email de prueba."""
    orch = EmailOrchestrator(token_path=token_path)

    print("═" * 50)
    print("  ENVÍO DE PRUEBA")
    print(f"  Destino: {to_email}")
    print("═" * 50)

    # 1. Consultora
    print("\n[1/3] Enviando plantilla Consultora...")
    orch.send_consultora(
        to=to_email,
        consultora_nombre="Maria Alejandra Celedon Fuenzalida",
        cb="2373",
        ciclo="05-2026",
        lider_nombre="Constanza Mariela Acevedo",
    )
    print("  ✅ Enviado")

    # 2. Líder
    print("[2/3] Enviando plantilla Líder...")
    orch.send_lider(
        to=to_email,
        lider_nombre="Constanza Mariela Acevedo",
        nombre_sector="Acacia",
        total_exitosos=15,
        total_errores=2,
        consultoras=_SAMPLE_CONSULTORAS,
    )
    print("  ✅ Enviado")

    # 3. Gerente
    print("[3/3] Enviando plantilla Gerente...")
    orch.send_gerente(
        to=to_email,
        gn_nombre="Carolina Andrea Mendez Rivera",
        nombre_gerencia="Gerencia Sur",
        lideres=_SAMPLE_LIDERES,
    )
    print("  ✅ Enviado")

    print()
    print("═" * 50)
    print(f"  3 correos enviados a {to_email}")
    print("═" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Envío de correos GSP Bot v5 — preview y test"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--preview", action="store_true",
        help="Genera archivos HTML de preview (sin enviar)"
    )
    group.add_argument(
        "--test", type=str, metavar="EMAIL",
        help="Envía las 3 plantillas de ejemplo a este email"
    )
    group.add_argument(
        "--token-status", action="store_true",
        help="Muestra el estado actual del token"
    )

    parser.add_argument(
        "--token-path", type=str, default=None,
        help="Ruta al token.json (default: shared/email/token.json)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=".",
        help="Directorio para archivos de preview (default: directorio actual)"
    )

    args = parser.parse_args()

    # Configurar logging para CLI
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.preview:
        _preview_mode(args.output_dir)
    elif args.test:
        _test_send(args.test, token_path=args.token_path)
    elif args.token_status:
        sender = GmailSender(token_path=args.token_path)
        status = sender.token_status()
        print("═" * 50)
        print("  ESTADO DEL TOKEN")
        print("═" * 50)
        for key, value in status.items():
            print(f"  {key:20s}: {value}")
        print("═" * 50)


if __name__ == "__main__":
    main()
