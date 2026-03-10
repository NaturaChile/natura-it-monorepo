#!/usr/bin/env python3
"""
Orquestador de envío de correos para GSP Bot v5.

Envía notificaciones a 3 niveles después de un batch completado:
  1. Consultora  → "Tu carrito está listo" o "Parcialmente completo"
  2. Líder       → Resumen de su sector (tabla de consultoras)
  3. Gerente     → Reporte gerencial (tabla de líderes)

Uso:
    POST /batches/{batch_id}/send-emails  →  send_batch_notifications(batch_id)
"""

import csv
import logging
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Union

from sqlalchemy.orm import Session

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

# ── CSV loader ────────────────────────────────

_MATRIZ_PATH = Path(__file__).resolve().parents[2] / "data" / "consultoras_matriz.csv"


def _load_consultora_matriz(path: Path = _MATRIZ_PATH) -> Dict[str, dict]:
    """
    Load consultoras_matriz.csv into a dict keyed by CB (consultora_code).

    Returns:
        {cb_str: {nombre, mail_cb, nombre_lider, mail_lider, nombre_sector,
                  nombre_gn, mail_gn, nombre_gerencia, color}}
    """
    result = {}
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            cb = row.get("CB", "").strip()
            if not cb:
                continue
            result[cb] = {
                "nombre": row.get("Nombre", "").strip(),
                "mail_cb": row.get("MAIL CB", "").strip(),
                "nombre_lider": row.get("Nombre Lider", "").strip(),
                "mail_lider": row.get("Mail lider", "").strip(),
                "nombre_sector": row.get("Nombre Setor", "").strip(),
                "nombre_gn": row.get("Nombre GN", "").strip(),
                "mail_gn": row.get("Mail GN", "").strip(),
                "nombre_gerencia": row.get("Nombre Gerencia", "").strip(),
                "color": row.get("Color", "").strip(),
            }
    logger.info("Loaded %d consultoras from matriz CSV", len(result))
    return result


# ── EmailOrchestrator (low-level send wrappers) ──


class EmailOrchestrator:
    """Combines GmailSender + HTML templates for each notification level."""

    def __init__(self, token_path: Optional[str] = None):
        self._sender = GmailSender(token_path=token_path)

    @property
    def sender(self) -> GmailSender:
        return self._sender

    # 1. Consultora
    def send_consultora(
        self,
        to: Union[str, List[str]],
        consultora_nombre: str,
        cb: str,
        lider_nombre: str,
        products: Optional[List[Dict]] = None,
        is_partial: bool = False,
        evento: str = "Preventa del Día de las Madres",
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
    ) -> dict:
        html = build_consultora_email(
            consultora_nombre=consultora_nombre,
            cb=cb,
            lider_nombre=lider_nombre,
            products=products,
            is_partial=is_partial,
            evento=evento,
        )
        if subject is None:
            if is_partial:
                subject = f"⚠️ Tu carrito del Live Shopping se cargó parcialmente - CB {cb}"
            else:
                subject = f"🎁 ¡Tu carrito del Live Shopping está listo! - CB {cb}"

        result = self._sender.send(to=to, subject=subject, html_body=html, cc=cc)
        logger.info("Correo consultora → %s (CB: %s, parcial=%s)", consultora_nombre, cb, is_partial)
        return result

    # 2. Líder
    def send_lider(
        self,
        to: Union[str, List[str]],
        lider_nombre: str,
        nombre_sector: str,
        total_completos: int,
        total_parciales: int,
        consultoras: List[Dict[str, str]],
        evento: str = "Preventa del Día de las Madres",
        cc: Optional[Union[str, List[str]]] = None,
        subject: Optional[str] = None,
    ) -> dict:
        html = build_lider_email(
            lider_nombre=lider_nombre,
            nombre_sector=nombre_sector,
            total_completos=total_completos,
            total_parciales=total_parciales,
            consultoras=consultoras,
            evento=evento,
        )
        if subject is None:
            subject = (
                f"🌸 Resultados Live Shopping - Sector {nombre_sector} "
                f"({total_completos} completos, {total_parciales} parciales)"
            )
        result = self._sender.send(to=to, subject=subject, html_body=html, cc=cc)
        logger.info("Correo líder → %s (Sector: %s)", lider_nombre, nombre_sector)
        return result

    # 3. Gerente
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
        html = build_gerente_email(
            gn_nombre=gn_nombre,
            nombre_gerencia=nombre_gerencia,
            lideres=lideres,
            evento=evento,
        )
        total_ok = sum(l.get("completos", 0) for l in lideres)
        total_parcial = sum(l.get("parciales", 0) for l in lideres)
        if subject is None:
            subject = (
                f"📈 Reporte Live Shopping - {nombre_gerencia} "
                f"({total_ok} completos, {total_parcial} parciales)"
            )
        result = self._sender.send(to=to, subject=subject, html_body=html, cc=cc)
        logger.info("Correo gerente → %s (Gerencia: %s)", gn_nombre, nombre_gerencia)
        return result


# ═══════════════════════════════════════════════════════════════════════════
# BATCH NOTIFICATION — main entry point for the endpoint
# ═══════════════════════════════════════════════════════════════════════════

def send_batch_notifications(
    batch_id: int,
    db: Session,
    evento: str = "Preventa del Día de las Madres",
) -> dict:
    """
    Send email notifications for a completed batch at 3 levels.

    1. Loads consultoras_matriz.csv
    2. Queries orders + products for the batch
    3. Cross-references orders with CSV by consultora_code == CB
    4. Sends consultora emails (Completo or Parcialmente Completo)
    5. Aggregates by líder → sends líder emails
    6. Aggregates by GN → sends gerente emails

    Orders with status FAILED are skipped (no email sent).

    Returns:
        Summary dict with counts per level + error list.
    """
    from shared.models import Batch, Order, OrderProduct, OrderStatus, ProductStatus

    # ── 1. Validate batch ──
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        return {"error": f"Batch {batch_id} not found"}

    # ── 2. Load matriz CSV ──
    try:
        matriz = _load_consultora_matriz()
    except FileNotFoundError:
        return {"error": f"consultoras_matriz.csv not found at {_MATRIZ_PATH}"}

    # ── 3. Query orders ──
    orders = (
        db.query(Order)
        .filter(Order.batch_id == batch_id)
        .all()
    )
    if not orders:
        return {"error": f"No orders found in batch {batch_id}"}

    orch = EmailOrchestrator()

    summary = {
        "batch_id": batch_id,
        "consultoras": {"sent": 0, "skipped_no_email": 0, "skipped_failed": 0, "skipped_not_in_csv": 0},
        "lideres": {"sent": 0},
        "gerentes": {"sent": 0},
        "errors": [],
    }

    # ── 4. Process each order → consultora emails ──
    # Also collect data for líder / gerente aggregation
    lider_groups = defaultdict(lambda: {"consultoras": [], "completos": 0, "parciales": 0})
    gerente_groups = defaultdict(lambda: {"lideres_set": set()})

    for order in orders:
        cb = order.consultora_code

        # Skip FAILED orders
        if order.status == OrderStatus.FAILED:
            summary["consultoras"]["skipped_failed"] += 1
            logger.info("Skipped FAILED order %d (CB: %s)", order.id, cb)
            continue

        # Look up in CSV
        csv_row = matriz.get(cb)
        if not csv_row:
            summary["consultoras"]["skipped_not_in_csv"] += 1
            logger.warning("CB %s not found in consultoras_matriz.csv — skipped", cb)
            continue

        email = csv_row["mail_cb"]
        if not email:
            summary["consultoras"]["skipped_no_email"] += 1
            logger.warning("CB %s (%s) has no email in CSV — skipped", cb, csv_row["nombre"])
            continue

        # Load products for this order
        products_db = db.query(OrderProduct).filter(OrderProduct.order_id == order.id).all()

        ok_products = []
        failed_products = []
        for p in products_db:
            if p.status.name == "ADDED":
                ok_products.append({
                    "product_code": p.product_code,
                    "product_name": p.product_name or "",
                    "status": "ok",
                    "error_message": "",
                })
            else:
                failed_products.append({
                    "product_code": p.product_code,
                    "product_name": p.product_name or "",
                    "status": "failed",
                    "error_message": p.error_message or "Sin stock",
                })

        is_partial = len(failed_products) > 0 and len(ok_products) > 0
        all_products = ok_products + failed_products

        consultora_nombre = csv_row["nombre"] or order.consultora_name or cb
        lider_nombre = csv_row["nombre_lider"] or "tu Líder"

        # Send consultora email
        try:
            orch.send_consultora(
                to=email,
                consultora_nombre=consultora_nombre,
                cb=cb,
                lider_nombre=lider_nombre,
                products=all_products if all_products else None,
                is_partial=is_partial,
                evento=evento,
            )
            summary["consultoras"]["sent"] += 1
        except Exception as e:
            logger.error("Error sending to CB %s (%s): %s", cb, email, e)
            summary["errors"].append({"level": "consultora", "cb": cb, "email": email, "error": str(e)})

        # Aggregate for líder
        estado = "Parcialmente Completo" if is_partial else "Completo"
        lider_key = (csv_row["mail_lider"], csv_row["nombre_lider"], csv_row["nombre_sector"])
        lider_groups[lider_key]["consultoras"].append({
            "cb": cb,
            "consultora_nombre": consultora_nombre,
            "estado": estado,
        })
        if is_partial:
            lider_groups[lider_key]["parciales"] += 1
        else:
            lider_groups[lider_key]["completos"] += 1

        # Track for gerente aggregation
        gn_key = (csv_row["mail_gn"], csv_row["nombre_gn"], csv_row["nombre_gerencia"])
        gerente_groups[gn_key]["lideres_set"].add(lider_key)

    # ── 5. Send líder emails ──
    for (mail_lider, nombre_lider, nombre_sector), data in lider_groups.items():
        if not mail_lider:
            logger.warning("Líder '%s' has no email — skipped", nombre_lider)
            continue
        try:
            orch.send_lider(
                to=mail_lider,
                lider_nombre=nombre_lider,
                nombre_sector=nombre_sector,
                total_completos=data["completos"],
                total_parciales=data["parciales"],
                consultoras=data["consultoras"],
                evento=evento,
            )
            summary["lideres"]["sent"] += 1
        except Exception as e:
            logger.error("Error sending to líder %s (%s): %s", nombre_lider, mail_lider, e)
            summary["errors"].append({"level": "lider", "nombre": nombre_lider, "email": mail_lider, "error": str(e)})

    # ── 6. Send gerente emails ──
    for (mail_gn, nombre_gn, nombre_gerencia), gn_data in gerente_groups.items():
        if not mail_gn:
            logger.warning("GN '%s' has no email — skipped", nombre_gn)
            continue

        lideres_list = []
        for lider_key in gn_data["lideres_set"]:
            lider_data = lider_groups[lider_key]
            lideres_list.append({
                "lider_nombre": lider_key[1],
                "nombre_sector": lider_key[2],
                "completos": lider_data["completos"],
                "parciales": lider_data["parciales"],
            })

        try:
            orch.send_gerente(
                to=mail_gn,
                gn_nombre=nombre_gn,
                nombre_gerencia=nombre_gerencia,
                lideres=lideres_list,
                evento=evento,
            )
            summary["gerentes"]["sent"] += 1
        except Exception as e:
            logger.error("Error sending to GN %s (%s): %s", nombre_gn, mail_gn, e)
            summary["errors"].append({"level": "gerente", "nombre": nombre_gn, "email": mail_gn, "error": str(e)})

    logger.info(
        "Batch %d email summary: consultoras=%s, lideres=%s, gerentes=%s, errors=%d",
        batch_id, summary["consultoras"], summary["lideres"], summary["gerentes"], len(summary["errors"]),
    )
    return summary
