# ──────────────────────────────────────────────
# Master Orchestrator  –  Batch & Order Management
# ──────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import func

from shared.database import get_session_factory
from shared.models import (
    Batch, Order, OrderProduct, OrderLog,
    BatchStatus, OrderStatus, ProductStatus,
)
from shared.logging_config import get_logger
from worker.tasks import process_batch, process_order, retry_failed_orders

logger = get_logger("orchestrator")


class Orchestrator:
    """
    The master orchestrator manages batch lifecycle:
      - Start / pause / resume / cancel batches
      - Retry failed orders
      - Query stats and status
    """

    def __init__(self):
        self._session_factory = get_session_factory()

    def _db(self) -> Session:
        return self._session_factory()

    # ── Batch Operations ──────────────────────

    def start_batch(self, batch_id: int) -> dict:
        """Dispatch all pending orders in a batch to Celery workers."""
        db = self._db()
        try:
            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                return {"success": False, "error": "Batch not found"}

            if batch.status not in (BatchStatus.PENDING, BatchStatus.PAUSED, BatchStatus.FAILED):
                return {"success": False, "error": f"Batch is {batch.status.value}, cannot start"}

            batch.status = BatchStatus.RUNNING
            batch.started_at = batch.started_at or datetime.now(timezone.utc)
            db.commit()

            # Dispatch via Celery
            task = process_batch.apply_async(args=[batch_id], queue="batches")

            logger.info("batch_started", batch_id=batch_id, celery_task=task.id)
            return {"success": True, "batch_id": batch_id, "task_id": task.id}

        finally:
            db.close()

    def pause_batch(self, batch_id: int) -> dict:
        """Pause a running batch (pending orders won't be dispatched)."""
        db = self._db()
        try:
            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                return {"success": False, "error": "Batch not found"}

            batch.status = BatchStatus.PAUSED
            db.commit()

            # Revoke pending orders
            pending_orders = (
                db.query(Order)
                .filter(
                    Order.batch_id == batch_id,
                    Order.status.in_([OrderStatus.PENDING, OrderStatus.QUEUED]),
                )
                .all()
            )
            for order in pending_orders:
                if order.celery_task_id:
                    from worker.celery_app import app
                    app.control.revoke(order.celery_task_id, terminate=False)
                order.status = OrderStatus.PENDING
            db.commit()

            logger.info("batch_paused", batch_id=batch_id, revoked=len(pending_orders))
            return {"success": True, "batch_id": batch_id, "paused_orders": len(pending_orders)}

        finally:
            db.close()

    def cancel_batch(self, batch_id: int) -> dict:
        """Cancel a batch and all its pending/queued orders."""
        db = self._db()
        try:
            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                return {"success": False, "error": "Batch not found"}

            batch.status = BatchStatus.CANCELLED
            batch.finished_at = datetime.now(timezone.utc)

            orders = (
                db.query(Order)
                .filter(
                    Order.batch_id == batch_id,
                    Order.status.in_([
                        OrderStatus.PENDING, OrderStatus.QUEUED, OrderStatus.RETRYING
                    ]),
                )
                .all()
            )
            for order in orders:
                if order.celery_task_id:
                    from worker.celery_app import app
                    app.control.revoke(order.celery_task_id, terminate=True)
                order.status = OrderStatus.CANCELLED
            db.commit()

            logger.info("batch_cancelled", batch_id=batch_id, cancelled_orders=len(orders))
            return {"success": True, "batch_id": batch_id, "cancelled_orders": len(orders)}

        finally:
            db.close()

    def retry_batch_failures(self, batch_id: int) -> dict:
        """Re-queue all failed orders in a batch."""
        task = retry_failed_orders.apply_async(args=[batch_id], queue="batches")
        logger.info("batch_retry_requested", batch_id=batch_id, task_id=task.id)
        return {"success": True, "batch_id": batch_id, "task_id": task.id}

    def retry_single_order(self, order_id: int) -> dict:
        """Re-queue a single failed order."""
        db = self._db()
        try:
            order = db.query(Order).filter(Order.id == order_id).first()
            if not order:
                return {"success": False, "error": "Order not found"}

            if order.status not in (OrderStatus.FAILED, OrderStatus.CANCELLED):
                return {"success": False, "error": f"Order is {order.status.value}, cannot retry"}

            order.status = OrderStatus.RETRYING
            order.retry_count += 1
            order.error_message = None
            order.error_step = None
            db.commit()

            task = process_order.apply_async(args=[order_id], queue="orders")
            order.celery_task_id = task.id
            db.commit()

            logger.info("order_retry", order_id=order_id, task_id=task.id)
            return {"success": True, "order_id": order_id, "task_id": task.id}

        finally:
            db.close()

    # ── Queries ───────────────────────────────

    def get_batch(self, batch_id: int) -> Optional[Batch]:
        db = self._db()
        try:
            return db.query(Batch).filter(Batch.id == batch_id).first()
        finally:
            db.close()

    def get_batch_stats(self, batch_id: int) -> dict:
        """Get detailed statistics for a batch."""
        db = self._db()
        try:
            batch = db.query(Batch).filter(Batch.id == batch_id).first()
            if not batch:
                return {}

            status_counts = (
                db.query(Order.status, func.count(Order.id))
                .filter(Order.batch_id == batch_id)
                .group_by(Order.status)
                .all()
            )
            counts = {s.value: c for s, c in status_counts}

            total = batch.total_orders or 1
            completed = counts.get("completed", 0)
            failed = counts.get("failed", 0)
            done = completed + failed

            # ETA calculation
            avg_duration = (
                db.query(func.avg(Order.duration_seconds))
                .filter(Order.batch_id == batch_id, Order.duration_seconds.isnot(None))
                .scalar()
            )
            remaining = total - done
            eta = (avg_duration or 0) * remaining if remaining > 0 else 0

            return {
                "batch_id": batch_id,
                "total": batch.total_orders,
                "pending": counts.get("pending", 0),
                "queued": counts.get("queued", 0),
                "in_progress": counts.get("in_progress", 0),
                "completed": completed,
                "failed": failed,
                "retrying": counts.get("retrying", 0),
                "cancelled": counts.get("cancelled", 0),
                "progress_pct": round((done / total) * 100, 1),
                "eta_seconds": round(eta, 0) if eta else None,
            }

        finally:
            db.close()

    def get_order_logs(self, order_id: int) -> list[OrderLog]:
        db = self._db()
        try:
            return (
                db.query(OrderLog)
                .filter(OrderLog.order_id == order_id)
                .order_by(OrderLog.timestamp.asc())
                .all()
            )
        finally:
            db.close()

    def get_system_stats(self) -> dict:
        """Get overall system statistics."""
        db = self._db()
        try:
            from worker.celery_app import app
            inspector = app.control.inspect()
            active = inspector.active()
            active_workers = len(active) if active else 0

            total_batches = db.query(func.count(Batch.id)).scalar()
            active_batches = (
                db.query(func.count(Batch.id))
                .filter(Batch.status == BatchStatus.RUNNING)
                .scalar()
            )

            order_counts = (
                db.query(Order.status, func.count(Order.id))
                .group_by(Order.status)
                .all()
            )
            oc = {s.value: c for s, c in order_counts}

            return {
                "active_workers": active_workers,
                "total_batches": total_batches,
                "active_batches": active_batches,
                "total_orders_pending": oc.get("pending", 0) + oc.get("queued", 0),
                "total_orders_in_progress": oc.get("in_progress", 0),
                "total_orders_completed": oc.get("completed", 0),
                "total_orders_failed": oc.get("failed", 0),
            }

        except Exception as e:
            logger.warning("system_stats_error", error=str(e))
            return {"error": str(e)}
        finally:
            db.close()
