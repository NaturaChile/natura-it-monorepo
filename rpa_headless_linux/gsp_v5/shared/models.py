# ──────────────────────────────────────────────
# SQLAlchemy ORM Models
# ──────────────────────────────────────────────
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Enum, Float,
    ForeignKey, Boolean, JSON, Index,
)
from sqlalchemy.orm import relationship

from shared.database import Base


# ── Enums ─────────────────────────────────────

class BatchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrderStatus(str, enum.Enum):
    PENDING = "pending"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    LOGIN_OK = "login_ok"
    CONSULTORA_SELECTED = "consultora_selected"
    CYCLE_SELECTED = "cycle_selected"
    CART_OPEN = "cart_open"
    PRODUCTS_ADDED = "products_added"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class ProductStatus(str, enum.Enum):
    PENDING = "pending"
    ADDED = "added"
    FAILED = "failed"
    NOT_FOUND = "not_found"


# ── Models ────────────────────────────────────

class Batch(Base):
    """A batch represents a single run / upload of orders to process."""
    __tablename__ = "batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(Enum(BatchStatus), default=BatchStatus.PENDING, nullable=False)
    total_orders = Column(Integer, default=0)
    completed_orders = Column(Integer, default=0)
    failed_orders = Column(Integer, default=0)
    source_file = Column(String(500), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    orders = relationship("Order", back_populates="batch", cascade="all, delete-orphan")


class Order(Base):
    """An order for a single consultora with one or more products."""
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_batch_status", "batch_id", "status"),
        Index("ix_orders_consultora", "consultora_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=False)
    consultora_code = Column(String(50), nullable=False)
    consultora_name = Column(String(255), default="")
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    current_step = Column(String(100), default="pending")
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    celery_task_id = Column(String(255), nullable=True)
    worker_id = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    error_step = Column(String(100), nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    batch = relationship("Batch", back_populates="orders")
    products = relationship("OrderProduct", back_populates="order", cascade="all, delete-orphan")
    logs = relationship("OrderLog", back_populates="order", cascade="all, delete-orphan")


class OrderProduct(Base):
    """A product line within an order."""
    __tablename__ = "order_products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_code = Column(String(50), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    status = Column(Enum(ProductStatus), default=ProductStatus.PENDING, nullable=False)
    error_message = Column(Text, nullable=True)
    added_at = Column(DateTime, nullable=True)

    order = relationship("Order", back_populates="products")


class OrderLog(Base):
    """Detailed step-by-step log for each order (audit trail)."""
    __tablename__ = "order_logs"
    __table_args__ = (
        Index("ix_order_logs_order_id", "order_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    level = Column(String(20), default="INFO")  # INFO, WARNING, ERROR, DEBUG
    step = Column(String(100), nullable=False)
    message = Column(Text, nullable=False)
    details = Column(JSON, nullable=True)
    screenshot_path = Column(String(500), nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    order = relationship("Order", back_populates="logs")
