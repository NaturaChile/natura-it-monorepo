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


# ── Screenshots ───────────────────────────────

@app.get("/screenshots/{filename}")
async def get_screenshot(filename: str):
    """Serve a screenshot file."""
    path = settings.screenshot_dir / filename
    if not path.exists():
        raise HTTPException(404, "Screenshot not found")
    return FileResponse(path, media_type="image/png")
