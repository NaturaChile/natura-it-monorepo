# ──────────────────────────────────────────────
# FastAPI Monitoring & Control API
# ──────────────────────────────────────────────
from __future__ import annotations

import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from config.settings import get_settings
from shared.database import get_db, init_db
from shared.logging_config import setup_logging, get_logger
from shared.models import Batch, Order, OrderProduct, OrderLog, OrderStatus, BatchStatus
from shared.schemas import (
    BatchCreate, BatchOut, BatchDetail, BatchStats,
    OrderOut, OrderLogOut, SystemStats,
    EmailSendResult,
)
from master.orchestrator import Orchestrator
from master.loader import load_from_csv, load_single_order

# ── App Setup ─────────────────────────────────

setup_logging()
logger = get_logger("api")
settings = get_settings()

app = FastAPI(
    title="GSP Bot v5 - Control Panel",
    description="API para monitorear y controlar el bot de carga masiva de pedidos GSP Natura",
    version="5.0.0",
)

orchestrator = Orchestrator()


@app.on_event("startup")
async def startup():
    init_db()
    logger.info("api_started", host=settings.api_host, port=settings.api_port)


# ── Health ────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats", response_model=SystemStats)
async def system_stats():
    """Get overall system statistics."""
    data = orchestrator.get_system_stats()
    if "error" in data:
        raise HTTPException(500, data["error"])
    return data


# ── Batches ───────────────────────────────────

@app.post("/batches/upload", response_model=BatchOut)
async def upload_batch(
    file: UploadFile = File(...),
    name: str = Query("", description="Nombre del batch"),
    description: str = Query("", description="Descripción del batch"),
    db: Session = Depends(get_db),
):
    """Upload a CSV/Excel file to create a new batch of orders."""
    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Only CSV and Excel files are supported")

    # Save uploaded file
    upload_dir = settings.base_dir / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = upload_dir / f"{ts}_{file.filename}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        batch_id = load_from_csv(
            dest,
            batch_name=name or file.filename,
            description=description,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("upload_failed", error=str(e))
        raise HTTPException(500, f"Failed to load file: {e}")

    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    return batch


@app.post("/batches", response_model=BatchOut)
async def create_batch(payload: BatchCreate, db: Session = Depends(get_db)):
    """Create a batch from JSON payload."""
    batch = Batch(
        name=payload.name,
        description=payload.description,
        status=BatchStatus.PENDING,
        total_orders=len(payload.orders),
    )
    db.add(batch)
    db.flush()

    for order_in in payload.orders:
        order = Order(
            batch_id=batch.id,
            consultora_code=order_in.consultora_code,
            consultora_name=order_in.consultora_name,
            status=OrderStatus.PENDING,
        )
        db.add(order)
        db.flush()

        for prod in order_in.products:
            db.add(OrderProduct(
                order_id=order.id,
                product_code=prod.product_code,
                quantity=prod.quantity,
            ))

    db.commit()
    db.refresh(batch)
    return batch


@app.get("/batches", response_model=list[BatchOut])
async def list_batches(db: Session = Depends(get_db)):
    """List all batches."""
    return db.query(Batch).order_by(Batch.created_at.desc()).all()


@app.get("/batches/{batch_id}", response_model=BatchDetail)
async def get_batch(batch_id: int, db: Session = Depends(get_db)):
    """Get batch details with all orders."""
    batch = db.query(Batch).filter(Batch.id == batch_id).first()
    if not batch:
        raise HTTPException(404, "Batch not found")
    return batch


@app.get("/batches/{batch_id}/stats", response_model=BatchStats)
async def batch_stats(batch_id: int):
    """Get detailed statistics for a batch."""
    data = orchestrator.get_batch_stats(batch_id)
    if not data:
        raise HTTPException(404, "Batch not found")
    return data


# ── Batch Actions ─────────────────────────────

@app.post("/batches/{batch_id}/start")
async def start_batch(batch_id: int):
    """Start processing a batch (dispatches all orders to workers)."""
    result = orchestrator.start_batch(batch_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
    return result


@app.post("/batches/{batch_id}/pause")
async def pause_batch(batch_id: int):
    """Pause a running batch."""
    result = orchestrator.pause_batch(batch_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
    return result


@app.post("/batches/{batch_id}/cancel")
async def cancel_batch(batch_id: int):
    """Cancel a batch and all pending orders."""
    result = orchestrator.cancel_batch(batch_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
    return result


@app.post("/batches/{batch_id}/retry")
async def retry_batch(batch_id: int):
    """Retry all failed orders in a batch."""
    result = orchestrator.retry_batch_failures(batch_id)
    return result


# ── Batch Email Notifications ─────────────────

@app.post("/batches/{batch_id}/send-emails", response_model=EmailSendResult)
async def send_batch_emails(
    batch_id: int,
    evento: str = Query("Preventa del Día de las Madres", description="Nombre del evento"),
    db: Session = Depends(get_db),
):
    """Send email notifications for a completed batch at 3 levels.

    1. Consultora — individual email per order (Completo / Parcialmente Completo)
    2. Líder — aggregated summary per sector
    3. Gerente — aggregated summary per gerencia

    Orders with FAILED status are skipped. Consultoras without email in the
    CSV matriz are skipped with a warning.
    """
    from shared.email.send_emails import send_batch_notifications

    result = send_batch_notifications(
        batch_id=batch_id,
        db=db,
        evento=evento,
    )
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


# ── Orders ────────────────────────────────────

@app.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get order details with products."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@app.post("/orders/{order_id}/retry")
async def retry_order(order_id: int):
    """Retry a single failed order."""
    result = orchestrator.retry_single_order(order_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
    return result


@app.get("/orders/{order_id}/logs", response_model=list[OrderLogOut])
async def order_logs(order_id: int, db: Session = Depends(get_db)):
    """Get the audit log for an order (all steps, errors, screenshots)."""
    logs = (
        db.query(OrderLog)
        .filter(OrderLog.order_id == order_id)
        .order_by(OrderLog.timestamp.asc())
        .all()
    )
    return logs


# ── Batch Orders list ─────────────────────────

@app.get("/batches/{batch_id}/orders", response_model=list[OrderOut])
async def batch_orders(
    batch_id: int,
    status: str | None = Query(None, description="Filter by status"),
    db: Session = Depends(get_db),
):
    """List all orders in a batch, optionally filtered by status."""
    q = db.query(Order).filter(Order.batch_id == batch_id)
    if status:
        try:
            q = q.filter(Order.status == OrderStatus(status))
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    return q.order_by(Order.id).all()


# ── Stress Tests ──────────────────────────────

@app.post("/tests/login-stress")
async def login_stress_test():
    """Launch concurrent login-only tasks (workers × concurrency) to test GSP session limits.

    The number of concurrent attempts is calculated automatically from the
    deployed WORKER_COUNT and CELERY_CONCURRENCY settings. Each task opens
    a browser, logs in, and closes. Results are tracked in Flower.
    """
    from worker.tasks import stress_test_login

    worker_count = settings.worker_count
    concurrency = settings.celery_concurrency
    total = worker_count * concurrency

    task_ids = []
    for i in range(1, total + 1):
        task = stress_test_login.apply_async(
            args=[i, total],
            queue="orders",
        )
        task_ids.append({"attempt": i, "task_id": task.id})

    logger.info("login_stress_started", workers=worker_count, concurrency=concurrency, total=total)
    return {
        "test": "login_stress",
        "workers": worker_count,
        "concurrency_per_worker": concurrency,
        "total_logins": total,
        "tasks": task_ids,
        "message": f"Launched {total} login attempts ({worker_count} workers × {concurrency} concurrency). Check Flower for progress.",
    }


@app.get("/tests/login-stress/results")
async def login_stress_results(
    task_ids: str = Query(..., description="Comma-separated task IDs from the stress test launch"),
):
    """Check results of a login stress test by task IDs."""
    from celery.result import AsyncResult
    from worker.celery_app import app as celery_app

    ids = [t.strip() for t in task_ids.split(",") if t.strip()]
    results = []
    succeeded = 0
    failed = 0

    for task_id in ids:
        ar = AsyncResult(task_id, app=celery_app)
        entry = {
            "task_id": task_id,
            "state": ar.state,
        }
        if ar.state == "SUCCESS":
            entry["result"] = ar.result
            succeeded += 1
        elif ar.state == "FAILURE":
            entry["error"] = str(ar.result)
            failed += 1
        elif ar.state == "PROGRESS":
            entry["progress"] = ar.info
        results.append(entry)

    return {
        "total": len(ids),
        "succeeded": succeeded,
        "failed": failed,
        "in_progress": len(ids) - succeeded - failed,
        "results": results,
    }


# ── Cart Clear ────────────────────────────────

@app.post("/cart/clear/upload")
async def upload_cart_clear(
    file: UploadFile = File(...),
    name: str = Query("", description="Nombre descriptivo del lote"),
):
    """Upload a CSV/Excel with consultora codes to empty their carts.

    Expected file format:
        consultora_code
        12345678
        87654321
        ...

    Only the 'consultora_code' column is required.
    Dispatches one cart-clear task per unique consultora.
    """
    import pandas as pd

    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Only CSV and Excel files are supported")

    # Save uploaded file
    upload_dir = settings.base_dir / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = upload_dir / f"cart_clear_{ts}_{file.filename}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse file
    try:
        if dest.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(dest)
        else:
            df = pd.read_csv(dest)

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        if "consultora_code" not in df.columns:
            raise ValueError(f"Missing 'consultora_code' column. Found: {list(df.columns)}")

        codes = df["consultora_code"].astype(str).str.strip().unique().tolist()
        codes = [c for c in codes if c and c != "nan"]

        if not codes:
            raise ValueError("No valid consultora codes found in file")

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("cart_clear_upload_failed", error=str(e))
        raise HTTPException(500, f"Failed to parse file: {e}")

    # Dispatch tasks
    from worker.tasks import empty_cart

    total = len(codes)
    task_ids = []
    for i, code in enumerate(codes, 1):
        task = empty_cart.apply_async(
            args=[code, i, total],
            queue="orders",
        )
        task_ids.append({"consultora_code": code, "task_id": task.id})

    logger.info("cart_clear_dispatched", total=total, source=file.filename)
    return {
        "action": "cart_clear",
        "total_consultoras": total,
        "source_file": file.filename,
        "tasks": task_ids,
        "message": f"Dispatched {total} cart-clear tasks. Use /cart/clear/results to check progress.",
    }


@app.get("/cart/clear/results")
async def cart_clear_results(
    task_ids: str = Query(..., description="Comma-separated task IDs from the upload response"),
):
    """Check results of cart-clear tasks by task IDs."""
    from celery.result import AsyncResult
    from worker.celery_app import app as celery_app

    ids = [t.strip() for t in task_ids.split(",") if t.strip()]
    results = []
    succeeded = 0
    failed = 0

    for task_id in ids:
        ar = AsyncResult(task_id, app=celery_app)
        entry = {
            "task_id": task_id,
            "state": ar.state,
        }
        if ar.state == "SUCCESS":
            entry["result"] = ar.result
            succeeded += 1
        elif ar.state == "FAILURE":
            entry["error"] = str(ar.result)
            failed += 1
        elif ar.state == "PROGRESS":
            entry["progress"] = ar.info
        results.append(entry)

    return {
        "total": len(ids),
        "succeeded": succeeded,
        "failed": failed,
        "in_progress": len(ids) - succeeded - failed,
        "results": results,
    }


# ── Screenshots ───────────────────────────────

@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """Serve a screenshot file."""
    path = settings.screenshot_dir / filename
    if not path.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(path, media_type="image/png")
