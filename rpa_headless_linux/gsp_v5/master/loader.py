# ──────────────────────────────────────────────
# Data Loader  –  CSV / Excel → Database
# ──────────────────────────────────────────────
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

import pandas as pd
from sqlalchemy.orm import Session

from shared.database import get_session_factory
from shared.models import Batch, Order, OrderProduct, BatchStatus, OrderStatus
from shared.logging_config import get_logger

logger = get_logger("loader")


def load_from_csv(file_path: str | Path, batch_name: str = "", description: str = "") -> int:
    """
    Load orders from a CSV file and insert into the database.

    Expected CSV columns:
        consultora_code, consultora_name (optional), product_code, quantity

    Multiple rows with the same consultora_code will be grouped into
    a single order with multiple products.

    Returns:
        batch_id of the created batch.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Read CSV or Excel
    if file_path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(file_path)
    else:
        df = pd.read_csv(file_path)

    # Normalize column names
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    required_cols = {"consultora_code", "product_code", "quantity"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Found: {list(df.columns)}")

    # Clean data
    df["consultora_code"] = df["consultora_code"].astype(str).str.strip()
    df["product_code"] = df["product_code"].astype(str).str.strip()
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(1).astype(int)
    if "consultora_name" not in df.columns:
        df["consultora_name"] = ""

    # Group by consultora
    grouped = df.groupby("consultora_code")

    db: Session = get_session_factory()()
    try:
        # Create batch
        batch = Batch(
            name=batch_name or f"Batch {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            description=description,
            source_file=str(file_path),
            status=BatchStatus.PENDING,
            total_orders=len(grouped),
        )
        db.add(batch)
        db.flush()  # Get batch.id

        order_count = 0
        product_count = 0

        for consultora_code, group in grouped:
            consultora_name = group["consultora_name"].iloc[0] if "consultora_name" in group.columns else ""

            order = Order(
                batch_id=batch.id,
                consultora_code=str(consultora_code),
                consultora_name=str(consultora_name),
                status=OrderStatus.PENDING,
            )
            db.add(order)
            db.flush()

            for _, row in group.iterrows():
                product = OrderProduct(
                    order_id=order.id,
                    product_code=str(row["product_code"]),
                    quantity=int(row["quantity"]),
                )
                db.add(product)
                product_count += 1

            order_count += 1

        db.commit()

        logger.info(
            "data_loaded",
            batch_id=batch.id,
            orders=order_count,
            products=product_count,
            source=str(file_path),
        )

        return batch.id

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def load_single_order(
    consultora_code: str,
    products: list[dict],
    batch_name: str = "",
) -> tuple[int, int]:
    """
    Load a single order programmatically.

    Args:
        consultora_code: Consultora code.
        products: List of dicts with 'product_code' and 'quantity'.
        batch_name: Optional batch name.

    Returns:
        Tuple of (batch_id, order_id).
    """
    db: Session = get_session_factory()()
    try:
        batch = Batch(
            name=batch_name or f"Single - {consultora_code}",
            status=BatchStatus.PENDING,
            total_orders=1,
        )
        db.add(batch)
        db.flush()

        order = Order(
            batch_id=batch.id,
            consultora_code=consultora_code,
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.flush()

        for p in products:
            db.add(OrderProduct(
                order_id=order.id,
                product_code=p["product_code"],
                quantity=p.get("quantity", 1),
            ))

        db.commit()
        logger.info("single_order_loaded", batch_id=batch.id, order_id=order.id)
        return batch.id, order.id

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
