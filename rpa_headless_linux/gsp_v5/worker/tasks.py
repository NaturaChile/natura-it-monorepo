# ──────────────────────────────────────────────
# Celery Tasks  –  Order Processing
# ──────────────────────────────────────────────
from __future__ import annotations

import socket
import time
from datetime import datetime, timezone

from celery import shared_task
from celery.exceptions import Retry
from celery.utils.log import get_task_logger
from sqlalchemy.orm import Session

from config.settings import get_settings
from shared.database import get_session_factory
from shared.models import (
    Order, OrderProduct, OrderLog, Batch,
    OrderStatus, ProductStatus, BatchStatus,
)
from worker.gsp_bot import GSPBot

task_logger = get_task_logger(__name__)
settings = get_settings()

# Step → percent mapping for Flower real-time progress tracking
STEP_PROGRESS = {
    "starting": 0,
    "preflight": 5,
    "login": 15,
    "select_otra_consultora": 25,
    "search_consultora": 35,
    "confirm_consultora": 45,
    "excel_generation": 50,
    "file_generation": 52,
    "navigate_to_cart_adaptively": 60,
    "cart_cleanup": 70,
    "upload_order_file": 85,
    "upload_validation": 92,
    "completed": 100,
}


def _get_db() -> Session:
    """Get a fresh DB session for task execution."""
    return get_session_factory()()


def _record_log(db: Session, order_id: int, step: str, message: str,
                level: str = "INFO", details: dict | None = None,
                screenshot_path: str | None = None) -> None:
    """Insert a log entry into order_logs table."""
    log_entry = OrderLog(
        order_id=order_id,
        step=step,
        message=message,
        level=level,
        details=details,
        screenshot_path=screenshot_path,
    )
    db.add(log_entry)
    db.commit()


def _update_order_status(db: Session, order: Order, status: OrderStatus,
                         step: str = "", error: str | None = None,
                         screenshot: str | None = None) -> None:
    """Update order status and related fields."""
    order.status = status
    if step:
        order.current_step = step
    if error:
        order.error_message = error
        order.error_step = step
    if screenshot:
        order.screenshot_path = screenshot
    order.updated_at = datetime.now(timezone.utc)
    db.commit()


def _update_batch_counters(db: Session, batch_id: int) -> None:
    """Recalculate batch completion counters."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        return

    orders = db.query(Order).filter(Order.batch_id == batch_id).all()
    batch.completed_orders = sum(1 for o in orders if o.status == OrderStatus.COMPLETED)
    batch.failed_orders = sum(1 for o in orders if o.status == OrderStatus.FAILED)

    # Check if batch is done
    total_done = batch.completed_orders + batch.failed_orders
    if total_done >= batch.total_orders:
        batch.status = BatchStatus.COMPLETED if batch.failed_orders == 0 else BatchStatus.FAILED
        batch.finished_at = datetime.now(timezone.utc)

    db.commit()


# ── Main Order Task ──────────────────────────

@shared_task(
    bind=True,
    name="worker.tasks.process_order",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
    reject_on_worker_lost=True,
    time_limit=600,       # Hard kill after 10 min
    soft_time_limit=540,  # Soft limit at 9 min
)
def process_order(self, order_id: int) -> dict:
    """
    Process a single consultora order end-to-end.

    This task:
    1. Launches a browser
    2. Logs in as supervisor
    3. Searches the consultora
    4. Selects cycle
    5. Opens cart and adds all products
    6. Records everything to the database

    On failure, it retries up to max_retries times.
    """
    worker_id = f"{socket.gethostname()}-{self.request.id[:8]}"
    db = _get_db()

    try:
        # Load order from DB
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            task_logger.error(f"Order {order_id} not found in database")
            return {"success": False, "error": "Order not found"}

        # Update status to IN_PROGRESS
        order.worker_id = worker_id
        order.celery_task_id = self.request.id
        order.started_at = datetime.now(timezone.utc)
        _update_order_status(db, order, OrderStatus.IN_PROGRESS, step="starting")
        _record_log(db, order_id, "starting", f"Worker {worker_id} picked up order")

        # Load products
        products = db.query(OrderProduct).filter(OrderProduct.order_id == order_id).all()
        product_list = [{"product_code": p.product_code, "quantity": p.quantity} for p in products]

        if not product_list:
            _update_order_status(db, order, OrderStatus.FAILED, step="validation", error="No products in order")
            _record_log(db, order_id, "validation", "Order has no products", level="ERROR")
            return {"success": False, "error": "No products"}

        _record_log(db, order_id, "starting", f"Processing {len(product_list)} products for consultora {order.consultora_code}")

        # Execute browser automation
        with GSPBot(
            supervisor_code=settings.gsp_user_code,
            supervisor_password=settings.gsp_password,
            order_id=order_id,
            worker_id=worker_id,
        ) as bot:
            # Wire up Celery progress tracking for Flower dashboard
            _last_pct = [0]

            def _on_progress(step: str, message: str, details: dict | None = None):
                try:
                    pct = STEP_PROGRESS.get(step, _last_pct[0])
                    _last_pct[0] = pct
                    self.update_state(state="PROGRESS", meta={
                        "step": step,
                        "message": message,
                        "percent": pct,
                        "order_id": order_id,
                        "consultora": order.consultora_code,
                        "worker_id": worker_id,
                        "products_total": len(product_list),
                        "started_at": order.started_at.isoformat() if order.started_at else None,
                    })
                except Exception:
                    pass  # Non-fatal

            bot.progress_callback = _on_progress

            result = bot.execute_order(
                consultora_code=order.consultora_code,
                products=product_list,
            )

        # Persist bot step log to DB
        for log_entry in result.get("step_log", []):
            _record_log(
                db, order_id,
                step=log_entry["step"],
                message=log_entry["message"],
                level=log_entry["level"],
                details=log_entry.get("details"),
            )

        # Update product statuses
        for p in products:
            added_codes = [a["product_code"] for a in result.get("products_added", [])]
            failed_items = {f["product_code"]: f.get("error", "") for f in result.get("products_failed", [])}

            if p.product_code in added_codes:
                p.status = ProductStatus.ADDED
                p.added_at = datetime.now(timezone.utc)
            elif p.product_code in failed_items:
                p.status = ProductStatus.FAILED
                p.error_message = failed_items[p.product_code]

        # Final order status
        order.duration_seconds = result.get("duration_seconds", 0)
        order.finished_at = datetime.now(timezone.utc)

        if result["success"]:
            self.update_state(state="PROGRESS", meta={
                "step": "completed", "message": "Order completed successfully",
                "percent": 100, "order_id": order_id,
                "consultora": order.consultora_code, "worker_id": worker_id,
                "products_total": len(product_list),
            })
            _update_order_status(db, order, OrderStatus.COMPLETED, step="completed")
            _record_log(db, order_id, "completed",
                        f"Order completed successfully in {result['duration_seconds']}s")
            _update_batch_counters(db, order.batch_id)
            db.commit()

            return {
                "success": True,
                "order_id": order_id,
                "consultora_code": order.consultora_code,
                "products_added": len(result.get("products_added", [])),
                "products_failed": len(result.get("products_failed", [])),
                "duration": result.get("duration_seconds", 0),
            }
        else:
            error_msg = result.get("error", "Products failed")
            error_step = result.get("error_step", "unknown")
            screenshot = result.get("screenshot")

            if order.retry_count < order.max_retries and result.get("error"):
                # Requeue for retry
                order.retry_count += 1
                _update_order_status(db, order, OrderStatus.RETRYING, step=error_step, error=error_msg, screenshot=screenshot)
                _record_log(db, order_id, "retrying",
                            f"Retry {order.retry_count}/{order.max_retries}: {error_msg}",
                            level="WARNING")
                db.commit()
                raise self.retry(
                    exc=Exception(error_msg),
                    countdown=settings.celery_retry_delay * order.retry_count,
                )
            else:
                _update_order_status(db, order, OrderStatus.FAILED, step=error_step, error=error_msg, screenshot=screenshot)
                _record_log(db, order_id, "failed",
                            f"Order failed after {order.retry_count} retries: {error_msg}",
                            level="ERROR")
                _update_batch_counters(db, order.batch_id)
                db.commit()
                # Raise so Celery marks as FAILURE (visible in Flower + allows retry)
                raise Exception(f"Order {order_id} failed: {error_msg}")

    except Retry:
        # Don't interfere with intentional Celery retries
        raise

    except process_order.MaxRetriesExceededError:
        _update_order_status(db, order, OrderStatus.FAILED, step="max_retries", error="Max retries exceeded")
        _record_log(db, order_id, "max_retries", "Max retries exceeded", level="ERROR")
        _update_batch_counters(db, order.batch_id)
        db.commit()
        # Re-raise so Celery marks as FAILURE (visible in Flower + allows retry)
        raise

    except Exception as exc:
        task_logger.exception(f"Unexpected error processing order {order_id}")
        try:
            if order:
                _update_order_status(db, order, OrderStatus.FAILED, step="unexpected_error", error=str(exc))
                _record_log(db, order_id, "unexpected_error", str(exc), level="ERROR")
                _update_batch_counters(db, order.batch_id)
                db.commit()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=60, max_retries=1)

    finally:
        db.close()


# ── Batch Dispatch Task ──────────────────────

@shared_task(
    bind=True,
    name="worker.tasks.process_batch",
    time_limit=3600,
)
def process_batch(self, batch_id: int) -> dict:
    """
    Dispatch all orders in a batch to the order processing queue.
    This is the 'master' task that fans out work to workers.
    """
    db = _get_db()

    try:
        batch = db.query(Batch).filter(Batch.id == batch_id).first()
        if not batch:
            return {"success": False, "error": "Batch not found"}

        batch.status = BatchStatus.RUNNING
        batch.started_at = datetime.now(timezone.utc)
        db.commit()

        # Get all pending orders for this batch
        orders = (
            db.query(Order)
            .filter(Order.batch_id == batch_id)
            .filter(Order.status.in_([OrderStatus.PENDING, OrderStatus.RETRYING]))
            .all()
        )

        task_logger.info(f"Dispatching {len(orders)} orders for batch {batch_id}")

        dispatched = 0
        for order in orders:
            order.status = OrderStatus.QUEUED
            order.celery_task_id = None
            db.commit()

            # Send to the orders queue
            task = process_order.apply_async(
                args=[order.id],
                queue="orders",
            )
            order.celery_task_id = task.id
            db.commit()
            dispatched += 1

        task_logger.info(f"Batch {batch_id}: dispatched {dispatched} orders")
        return {"success": True, "batch_id": batch_id, "dispatched": dispatched}

    except Exception as exc:
        task_logger.exception(f"Error dispatching batch {batch_id}")
        if batch:
            batch.status = BatchStatus.FAILED
            db.commit()
        raise

    finally:
        db.close()


# ── Utility Tasks ────────────────────────────

@shared_task(name="worker.tasks.health_check")
def health_check() -> dict:
    """Simple health check task to verify workers are alive."""
    return {
        "status": "ok",
        "hostname": socket.gethostname(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@shared_task(
    bind=True,
    name="worker.tasks.stress_test_login",
    time_limit=120,
    soft_time_limit=100,
    acks_late=True,
)
def stress_test_login(self, attempt_number: int, total_attempts: int) -> dict:
    """Stress test: login only, then close.

    Used to determine how many concurrent GSP sessions the provider allows.
    Each task opens a browser, performs login, records timing, and closes.
    """
    worker_id = f"{socket.gethostname()}-{self.request.id[:8]}"
    start = time.time()

    self.update_state(state="PROGRESS", meta={
        "step": "starting",
        "message": f"Login attempt {attempt_number}/{total_attempts}",
        "percent": 0,
        "attempt": attempt_number,
        "worker_id": worker_id,
    })

    try:
        with GSPBot(
            supervisor_code=settings.gsp_user_code,
            supervisor_password=settings.gsp_password,
            order_id=None,
            worker_id=worker_id,
        ) as bot:
            def _on_progress(step: str, message: str, details: dict | None = None):
                try:
                    self.update_state(state="PROGRESS", meta={
                        "step": step,
                        "message": message,
                        "percent": 50 if step == "login" else 0,
                        "attempt": attempt_number,
                        "worker_id": worker_id,
                    })
                except Exception:
                    pass

            bot.progress_callback = _on_progress

            # Only perform login
            bot.login()
            elapsed = round(time.time() - start, 2)

            self.update_state(state="PROGRESS", meta={
                "step": "completed",
                "message": f"Login OK in {elapsed}s",
                "percent": 100,
                "attempt": attempt_number,
                "worker_id": worker_id,
            })

            return {
                "success": True,
                "attempt": attempt_number,
                "worker_id": worker_id,
                "login_time_seconds": elapsed,
                "message": "Login successful",
            }

    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        task_logger.warning(f"Login stress test attempt {attempt_number} failed: {exc}")
        raise Exception(
            f"Login attempt {attempt_number} failed after {elapsed}s: {exc}"
        )


@shared_task(
    bind=True,
    name="worker.tasks.retry_failed_orders",
    time_limit=300,
)
def retry_failed_orders(self, batch_id: int) -> dict:
    """Re-queue all failed orders in a batch for retry."""
    db = _get_db()

    try:
        failed_orders = (
            db.query(Order)
            .filter(Order.batch_id == batch_id, Order.status == OrderStatus.FAILED)
            .all()
        )

        requeued = 0
        for order in failed_orders:
            if order.retry_count < order.max_retries + 2:  # Allow extra retries on manual retry
                order.status = OrderStatus.RETRYING
                order.retry_count += 1
                order.error_message = None
                order.error_step = None
                db.commit()

                task = process_order.apply_async(args=[order.id], queue="orders")
                order.celery_task_id = task.id
                db.commit()
                requeued += 1

        return {"success": True, "batch_id": batch_id, "requeued": requeued}

    finally:
        db.close()
