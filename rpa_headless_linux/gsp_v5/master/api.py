# ──────────────────────────────────────────────
# FastAPI Monitoring & Control API
# ──────────────────────────────────────────────
from __future__ import annotations

import shutil
from pathlib import Path
from datetime import datetime, timezone

from fastapi import FastAPI, Depends, UploadFile, File, HTTPException, Query
from fastapi import Body
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

from config.settings import get_settings
from shared.database import get_db, init_db
from shared.logging_config import setup_logging, get_logger
from shared.models import Batch, Order, OrderProduct, OrderLog, OrderStatus, BatchStatus, ProductStatus
from shared.schemas import (
    BatchCreate, BatchOut, BatchDetail, BatchStats,
    OrderOut, OrderLogOut, SystemStats,
    EmailSendResult,
)
from master.orchestrator import Orchestrator
from master.loader import load_from_csv, load_single_order
from worker.gsp_bot import GSPBot

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


@app.post("/batches/{batch_id}/reprocess-missing")
async def reprocess_missing_products(batch_id: int):
    """Reprocess orders that contain products with status OUT_OF_STOCK or NOT_FOUND.

    This will requeue orders (set to `retrying`) and dispatch them to workers.
    """
    result = orchestrator.reprocess_orders_with_missing_products(batch_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
    return result


@app.post("/admin/batches/{batch_id}/reprocess-failed")
async def admin_reprocess_failed(batch_id: int):
    """Admin endpoint: trigger reprocessing of all failed orders in a batch.

    This is equivalent to the public `/batches/{batch_id}/retry` but exposed
    under the `/admin` namespace for operational use.
    """
    result = orchestrator.retry_batch_failures(batch_id)
    if not result.get("success"):
        raise HTTPException(400, result.get("error"))
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


# ── Test Email ────────────────────────────────

@app.post("/test-email")
async def send_test_email(
    to: str = Query(..., description="Email del destinatario de prueba"),
    nombre: str = Query("Consultora de Prueba", description="Nombre de la consultora"),
    cb: str = Query("9999", description="Código CB de prueba"),
    is_partial: bool = Query(False, description="True para simular carrito parcial"),
    evento: str = Query("Preventa del Día de las Madres", description="Nombre del evento"),
):
    """Send a test email with sample product data to any email address.

    Use is_partial=true to preview the partial variant (with product tables).
    Use is_partial=false (default) to preview the complete variant.
    """
    from shared.email.send_emails import EmailOrchestrator

    sample_products = [
        {"product_code": "88934", "product_name": "Luna Absoluta Perfume de Mujer", "status": "ok", "error_message": ""},
        {"product_code": "91205", "product_name": "Ekos Maracuyá Jabón Líquido", "status": "ok", "error_message": ""},
        {"product_code": "76543", "product_name": "Tododia Crema Corporal Frambuesa", "status": "ok", "error_message": ""},
    ]
    if is_partial:
        sample_products[2]["status"] = "failed"
        sample_products[2]["error_message"] = "Sin stock"

    try:
        orch = EmailOrchestrator()
        result = orch.send_consultora(
            to=to,
            consultora_nombre=nombre,
            cb=cb,
            lider_nombre="Líder de Prueba",
            products=sample_products,
            is_partial=is_partial,
            evento=evento,
        )
        return {"status": "sent", "to": to, "is_partial": is_partial, "detail": result}
    except Exception as e:
        raise HTTPException(500, f"Error sending test email: {e}")


@app.post("/test-email/lider")
async def send_test_email_lider(
    to: str = Query(..., description="Email del destinatario de prueba"),
    lider: str = Query("María González", description="Nombre de la líder"),
    sector: str = Query("Sector Oriente", description="Nombre del sector"),
    evento: str = Query("Preventa del Día de las Madres", description="Nombre del evento"),
):
    """Send a test líder email with sample consultora data."""
    from shared.email.send_emails import EmailOrchestrator

    sample_consultoras = [
        {"cb": "10028439", "consultora_nombre": "Ana Pérez", "estado": "Completo"},
        {"cb": "10031245", "consultora_nombre": "Carla Muñoz", "estado": "Completo"},
        {"cb": "10045678", "consultora_nombre": "Luisa Rojas", "estado": "Parcialmente Completo"},
        {"cb": "10052301", "consultora_nombre": "Patricia Silva", "estado": "Completo"},
        {"cb": "10067890", "consultora_nombre": "Daniela Torres", "estado": "Parcialmente Completo"},
    ]

    try:
        orch = EmailOrchestrator()
        result = orch.send_lider(
            to=to,
            lider_nombre=lider,
            nombre_sector=sector,
            total_completos=3,
            total_parciales=2,
            consultoras=sample_consultoras,
            evento=evento,
        )
        return {"status": "sent", "to": to, "type": "lider", "detail": result}
    except Exception as e:
        raise HTTPException(500, f"Error sending test líder email: {e}")


@app.post("/test-email/gerente")
async def send_test_email_gerente(
    to: str = Query(..., description="Email del destinatario de prueba"),
    gerente: str = Query("Roberto Fernández", description="Nombre del gerente"),
    gerencia: str = Query("Gerencia Zona Central", description="Nombre de la gerencia"),
    evento: str = Query("Preventa del Día de las Madres", description="Nombre del evento"),
):
    """Send a test gerente email with sample líder/sector data."""
    from shared.email.send_emails import EmailOrchestrator

    sample_lideres = [
        {"lider_nombre": "María González", "nombre_sector": "Sector Oriente", "completos": 12, "parciales": 3},
        {"lider_nombre": "Carmen Vidal", "nombre_sector": "Sector Poniente", "completos": 8, "parciales": 5},
        {"lider_nombre": "Francisca López", "nombre_sector": "Sector Norte", "completos": 15, "parciales": 1},
    ]

    try:
        orch = EmailOrchestrator()
        result = orch.send_gerente(
            to=to,
            gn_nombre=gerente,
            nombre_gerencia=gerencia,
            lideres=sample_lideres,
            evento=evento,
        )
        return {"status": "sent", "to": to, "type": "gerente", "detail": result}
    except Exception as e:
        raise HTTPException(500, f"Error sending test gerente email: {e}")


# ── Orders ────────────────────────────────────

@app.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: int, db: Session = Depends(get_db)):
    """Get order details with products."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")
    return order


@app.post("/admin/check_showcase_badge")
async def check_showcase_badge(consultora_code: str = Query(..., description="Código de la consultora a verificar")):
    """Open the showcase, impersonate the consultora, and read the header cart badge.

    Reads the element: div[aria-label="notifications"][data-testid="icon-badge"]
    and returns its `value` or inner text as badge_count. Useful to detect if
    the cart already has items before attempting uploads.
    """
    worker_id = f"api-check-{consultora_code}"
    try:
        with GSPBot(supervisor_code=settings.gsp_user_code, supervisor_password=settings.gsp_password, order_id=None, worker_id=worker_id) as bot:
            # Login and impersonate the consultora
            bot.login()
            bot.select_otra_consultora()
            bot.search_consultora(consultora_code)
            bot.confirm_consultora()

            # Wait for the showcase header badge to appear
            step = "check_showcase_badge"
            bot._log_step(step, "Waiting for header cart badge selector")
            try:
                sel = 'div[aria-label="notifications"][data-testid="icon-badge"]'
                bot.page.wait_for_selector(sel, timeout=10000)
                el = bot.page.locator(sel).first
                # Try attribute 'value' then inner span text
                badge_val = el.get_attribute('value')
                if not badge_val:
                    try:
                        badge_val = el.locator('span').first.inner_text()
                    except Exception:
                        badge_val = el.inner_text()

                try:
                    badge_count = int(str(badge_val).strip())
                except Exception:
                    badge_count = None

                ss = bot._take_screenshot('badge_check')
                result = {
                    'consultora_code': consultora_code,
                    'badge_raw': badge_val,
                    'badge_count': badge_count,
                    'has_items': (badge_count is not None and badge_count > 0),
                    'screenshot': ss,
                    'step_log': bot.get_step_log(),
                }
                return JSONResponse(result)

            except Exception as sel_err:
                ss = bot._take_screenshot('badge_check_fail')
                bot._log_step(step, f"Badge selector not found: {sel_err}", level="WARNING")
                return JSONResponse({
                    'consultora_code': consultora_code,
                    'error': str(sel_err),
                    'screenshot': ss,
                    'step_log': bot.get_step_log(),
                }, status_code=500)

    except Exception as e:
        logger.exception(f"check_showcase_badge_failed: {e}")
        raise HTTPException(500, f"Failed to check badge: {e}")


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


@app.post("/admin/orders/fail/upload")
async def upload_orders_fail_csv(
    file: UploadFile = File(...),
    reason: str = Query("Marked as failed via CSV upload", description="Motivo opcional para el fallo"),
    db: Session = Depends(get_db),
):
    """Upload a CSV/Excel file with `order_id` column and mark those orders as FAILED.

    Expected file format:
        order_id,reason(optional)
        123
        456,No stock
        ...

    For each found order the endpoint will:
      - set `order.status = OrderStatus.FAILED`
      - set `order.error_message` (from file or `reason`)
      - set `order.finished_at` to now
      - insert an `OrderLog` entry with level=ERROR and step='admin_mark_failed'
    Returns a summary with counts and any not-found ids.
    """
    import pandas as pd
    from datetime import datetime, timezone

    if not file.filename.endswith((".csv", ".xlsx", ".xls")):
        raise HTTPException(400, "Only CSV and Excel files are supported")

    # Save uploaded file
    upload_dir = settings.base_dir / "data" / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = upload_dir / f"orders_fail_{ts}_{file.filename}"

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Parse file
    try:
        if dest.suffix in (".xlsx", ".xls"):
            df = pd.read_excel(dest)
        else:
            df = pd.read_csv(dest)

        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        if "order_id" not in df.columns:
            raise ValueError(f"Missing 'order_id' column. Found: {list(df.columns)}")

        # If there's a per-row reason column use it; otherwise use query `reason`
        per_row_reason = "reason" in df.columns

        ids = df["order_id"].astype(str).str.strip().unique().tolist()
        ids = [i for i in ids if i and i != "nan"]

        if not ids:
            raise ValueError("No valid order_id values found in file")

    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.error("orders_fail_upload_parse_failed", error=str(e))
        raise HTTPException(500, f"Failed to parse file: {e}")

    # Apply updates
    now = datetime.now(timezone.utc)
    updated = []
    not_found = []
    skipped = []

    for oid in ids:
        try:
            oid_int = int(oid)
        except Exception:
            not_found.append(oid)
            continue

        order = db.query(Order).filter(Order.id == oid_int).first()
        if not order:
            not_found.append(oid_int)
            continue

        # Determine reason for this row
        row_reason = reason
        if per_row_reason:
            # find first matching row for this order id
            matches = df[df["order_id"].astype(str).str.strip() == str(oid)]
            if not matches.empty and "reason" in matches.columns:
                val = str(matches.iloc[0]["reason"]).strip()
                if val and val.lower() != "nan":
                    row_reason = val

        # Only update if not already failed
        if order.status == OrderStatus.FAILED:
            skipped.append(oid_int)
            continue

        order.status = OrderStatus.FAILED
        order.error_message = row_reason
        order.finished_at = now

        # increment batch failed count if applicable
        try:
            if order.batch is not None:
                order.batch.failed_orders = (order.batch.failed_orders or 0) + 1
        except Exception:
            pass

        # add an order log
        log = OrderLog(
            order_id=order.id,
            level="ERROR",
            step="admin_mark_failed",
            message=row_reason or "Marked failed via CSV upload",
            details={"source": file.filename},
            timestamp=now,
        )
        db.add(log)
        updated.append(order.id)

    # Commit all changes
    try:
        db.commit()
    except Exception as e:
        logger.error("orders_fail_commit_error", error=str(e))
        db.rollback()
        raise HTTPException(500, f"Failed committing changes: {e}")

    return {
        "action": "mark_orders_failed",
        "source_file": file.filename,
        "processed": len(ids),
        "updated": len(updated),
        "skipped_already_failed": len(skipped),
        "not_found": not_found,
        "updated_ids": updated,
    }



@app.post("/admin/orders/{order_id}/confirm")
async def admin_mark_order_complete(
    order_id: int,
    note: str = Query("Marked complete via admin", description="Optional note for the audit log"),
    db: Session = Depends(get_db),
):
    """Admin endpoint: mark a single order as COMPLETED and set all products as ADDED/ok.

    This forcibly updates the order and its product lines, clears error messages,
    sets timestamps and inserts an `OrderLog` entry with step `admin_mark_complete`.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")

    # If already completed, skip
    if order.status == OrderStatus.COMPLETED:
        return {"action": "mark_order_complete", "order_id": order.id, "status": "already_completed"}

    # Update order
    order.status = OrderStatus.COMPLETED
    order.error_message = None
    order.error_step = None
    order.finished_at = now

    # Update products to reflect they were successfully added
    updated_products = []
    for p in order.products:
        p.status = ProductStatus.ADDED
        p.error_message = None
        p.added_at = now
        updated_products.append(p.id)

    # Increment batch counters if applicable
    try:
        if order.batch is not None:
            order.batch.completed_orders = (order.batch.completed_orders or 0) + 1
    except Exception:
        pass

    # Add an audit log
    log = OrderLog(
        order_id=order.id,
        level="INFO",
        step="admin_mark_complete",
        message=note or "Marked complete via admin",
        details={"updated_products": updated_products},
        timestamp=now,
    )
    db.add(log)

    try:
        db.commit()
    except Exception as e:
        logger.error("admin_mark_complete_commit_error", error=str(e))
        db.rollback()
        raise HTTPException(500, f"Failed committing changes: {e}")

    return {
        "action": "mark_order_complete",
        "order_id": order.id,
        "updated_products": updated_products,
        "status": "completed",
    }



@app.post("/admin/orders/{order_id}/mark-products-added")
async def admin_mark_products_added(
    order_id: int,
    product_codes: list[str] | None = Body(None, description="Optional list of product_code values to mark as ADDED. If omitted, all products in the order will be marked."),
    complete: bool = Query(False, description="If true, also mark the order as COMPLETED and update batch counters."),
    db: Session = Depends(get_db),
):
    """Admin endpoint: mark products for an order as ADDED.

    - If `product_codes` is provided (JSON array), only those product lines are updated.
    - Otherwise all product lines for the order are set to ADDED.
    - Use `complete=true` to also mark the order as COMPLETED and update batch counters.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(404, "Order not found")

    # Determine target products
    if product_codes:
        targets = [p for p in order.products if (p.product_code and p.product_code in product_codes)]
    else:
        targets = list(order.products)

    if not targets:
        return {"action": "mark_products_added", "order_id": order_id, "updated": 0, "message": "No matching products found"}

    updated_ids = []
    for p in targets:
        p.status = ProductStatus.ADDED
        p.error_message = None
        p.added_at = now
        updated_ids.append(p.id)

    # Optionally complete the order
    if complete:
        order.status = OrderStatus.COMPLETED
        order.error_message = None
        order.error_step = None
        order.finished_at = now
        # Try to increment batch counters safely
        try:
            if order.batch is not None:
                order.batch.completed_orders = (order.batch.completed_orders or 0) + 1
        except Exception:
            pass

    # Add an audit log entry
    log = OrderLog(
        order_id=order.id,
        level="INFO",
        step="admin_mark_products_added",
        message=f"Marked products as ADDED: {len(updated_ids)}",
        details={"updated_product_ids": updated_ids, "product_codes": product_codes},
        timestamp=now,
    )
    db.add(log)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("admin_mark_products_commit_error", error=str(e))
        raise HTTPException(500, f"Failed committing changes: {e}")

    # Recalculate batch counters if we changed order status
    try:
        if complete and order.batch is not None:
            _update_batch_counters(db, order.batch.id)
    except Exception:
        pass

    return {"action": "mark_products_added", "order_id": order_id, "updated": len(updated_ids), "updated_ids": updated_ids}
