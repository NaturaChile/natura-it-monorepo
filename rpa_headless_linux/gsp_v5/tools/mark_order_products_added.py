"""CLI helper to mark OrderProduct lines as ADDED for a given order_id.

Usage examples:
  # Mark all products as ADDED and complete the order
  python -m tools.mark_order_products_added --order 494 --complete

  # Mark specific product codes (dry run)
  python -m tools.mark_order_products_added --order 494 --codes 237617 244486 --dry-run

This script uses the same application settings and DB connection as the app.
Run from the repository root where the package imports resolve.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import List

from config.settings import get_settings
from shared.database import get_session_factory
from shared.models import Order, OrderProduct, OrderLog, ProductStatus, OrderStatus, Batch, BatchStatus


def parse_args():
    p = argparse.ArgumentParser(description="Mark products of an order as ADDED")
    p.add_argument("--order", "-o", type=int, required=True, help="Order ID to operate on")
    p.add_argument("--codes", "-c", nargs="*", help="Optional list of product_code values to mark. If omitted, all products are updated.")
    p.add_argument("--complete", action="store_true", help="Also mark the order as COMPLETED and update batch counters")
    p.add_argument("--dry-run", action="store_true", help="Show changes but do not commit")
    return p.parse_args()


def main():
    args = parse_args()
    settings = get_settings()
    SessionFactory = get_session_factory()
    db = SessionFactory()

    try:
        order = db.query(Order).filter(Order.id == args.order).first()
        if not order:
            print(f"Order {args.order} not found")
            return

        print(f"Order {order.id}: consultora={order.consultora_code} products={len(order.products)} status={order.status}")

        # Normalize provided codes
        provided = None
        if args.codes:
            provided = {str(c).strip() for c in args.codes}

        existing_codes = [str(p.product_code).strip() for p in order.products]
        print("Existing product_codes:", existing_codes)

        # Determine targets
        if provided:
            targets = [p for p in order.products if str(p.product_code).strip() in provided]
        else:
            targets = list(order.products)

        if not targets:
            print("No matching products to update. Exiting.")
            return

        now = datetime.now(timezone.utc)
        print("Will update the following product IDs:", [p.id for p in targets])

        # Apply changes
        for p in targets:
            print(f" - {p.product_code}: {p.status} -> ADDED")
            p.status = ProductStatus.ADDED
            p.error_message = None
            p.added_at = now

        if args.complete:
            print("Will also mark order as COMPLETED")
            order.status = OrderStatus.COMPLETED
            order.error_message = None
            order.error_step = None
            order.finished_at = now

        # Add order log
        log = OrderLog(
            order_id=order.id,
            level="INFO",
            step="admin_cli_mark_products_added",
            message=f"CLI: marked {len(targets)} products as ADDED",
            details={"product_ids": [p.id for p in targets], "provided_codes": args.codes},
            timestamp=now,
        )
        db.add(log)

        if args.dry_run:
            db.rollback()
            print("Dry run - no changes committed")
            return

        db.commit()

        # If we completed the order and it belongs to a batch, update batch counters
        if args.complete and order.batch_id:
            try:
                batch = db.query(Batch).filter(Batch.id == order.batch_id).first()
                if batch:
                    orders = db.query(Order).filter(Order.batch_id == batch.id).all()
                    batch.completed_orders = sum(1 for o in orders if o.status == OrderStatus.COMPLETED)
                    batch.failed_orders = sum(1 for o in orders if o.status == OrderStatus.FAILED)
                    if (batch.completed_orders + batch.failed_orders) >= batch.total_orders:
                        batch.status = BatchStatus.COMPLETED if batch.failed_orders == 0 else BatchStatus.FAILED
                    db.commit()
            except Exception:
                db.rollback()

        print(f"Committed changes: updated {len(targets)} products for order {order.id}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
