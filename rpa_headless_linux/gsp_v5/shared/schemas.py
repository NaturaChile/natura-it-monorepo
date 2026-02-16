# ──────────────────────────────────────────────
# Pydantic Schemas (API request/response)
# ──────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from shared.models import BatchStatus, OrderStatus, ProductStatus


# ── Products ──────────────────────────────────

class ProductIn(BaseModel):
    product_code: str
    quantity: int = Field(ge=1, default=1)


class ProductOut(BaseModel):
    id: int
    product_code: str
    quantity: int
    status: ProductStatus
    error_message: Optional[str] = None
    added_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ── Orders ────────────────────────────────────

class OrderIn(BaseModel):
    consultora_code: str
    consultora_name: str = ""
    products: list[ProductIn]


class OrderOut(BaseModel):
    id: int
    consultora_code: str
    consultora_name: str
    status: OrderStatus
    current_step: str
    retry_count: int
    error_message: Optional[str] = None
    error_step: Optional[str] = None
    worker_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    products: list[ProductOut] = []
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class OrderBrief(BaseModel):
    id: int
    consultora_code: str
    status: OrderStatus
    current_step: str
    retry_count: int
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


# ── Batches ───────────────────────────────────

class BatchCreate(BaseModel):
    name: str
    description: str = ""
    orders: list[OrderIn] = []


class BatchOut(BaseModel):
    id: int
    name: str
    description: str
    status: BatchStatus
    total_orders: int
    completed_orders: int
    failed_orders: int
    source_file: str
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class BatchDetail(BatchOut):
    orders: list[OrderBrief] = []


# ── Log ───────────────────────────────────────

class OrderLogOut(BaseModel):
    id: int
    level: str
    step: str
    message: str
    details: Optional[dict] = None
    screenshot_path: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True


# ── Stats ─────────────────────────────────────

class BatchStats(BaseModel):
    batch_id: int
    total: int
    pending: int
    queued: int
    in_progress: int
    completed: int
    failed: int
    retrying: int
    cancelled: int
    progress_pct: float
    eta_seconds: Optional[float] = None


class SystemStats(BaseModel):
    active_workers: int
    total_batches: int
    active_batches: int
    total_orders_pending: int
    total_orders_in_progress: int
    total_orders_completed: int
    total_orders_failed: int
