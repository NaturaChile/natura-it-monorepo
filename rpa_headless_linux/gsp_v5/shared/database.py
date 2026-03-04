# ──────────────────────────────────────────────
# Database Engine & Session
# ──────────────────────────────────────────────
from __future__ import annotations

from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase

from config.settings import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""
    pass


_engine: Optional[object] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_size=20,
            max_overflow=10,
            pool_pre_ping=True,  # ensure dead connections are detected and replaced
            pool_recycle=1800,   # recycle long-lived connections (optional)
            echo=False,
        )
    return _engine


def dispose_engine() -> None:
    """Dispose the current engine so child processes recreate connections.

    Call this from worker process init (e.g. Celery worker_process_init) so
    each worker process builds its own engine instead of sharing a forked one.
    """
    global _engine, _SessionLocal
    if _engine is not None:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
    _SessionLocal = None


def get_session_factory() -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        # create factory lazily so it is created in the worker process after dispose_engine
        _SessionLocal = sessionmaker(bind=get_engine(), autocommit=False, autoflush=False, expire_on_commit=False)
    return _SessionLocal


def get_db() -> Session:
    """Yield a database session (for FastAPI dependency injection)."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (used on first startup)."""
    from shared.models import Base  # noqa: ensure models are imported
    Base.metadata.create_all(bind=get_engine())
    _migrate_enums()


def _migrate_enums() -> None:
    """Add new enum values to PostgreSQL if they don't exist yet.

    PostgreSQL ALTER TYPE ... ADD VALUE is idempotent with IF NOT EXISTS
    and must run outside a transaction block.
    """
    engine = get_engine()

    # (pg_enum_type, new_value)
    # NOTE: SQLAlchemy persists the enum member NAME (uppercase), not the .value
    _NEW_ENUM_VALUES = [
        ("productstatus", "OUT_OF_STOCK"),
    ]

    with engine.connect() as conn:
        # Need AUTOCOMMIT because ALTER TYPE ... ADD VALUE cannot run inside a transaction
        conn = conn.execution_options(isolation_level="AUTOCOMMIT")
        for enum_type, new_value in _NEW_ENUM_VALUES:
            try:
                conn.execute(text(
                    f"ALTER TYPE {enum_type} ADD VALUE IF NOT EXISTS :val"
                ), {"val": new_value})
            except Exception:
                pass  # Value already exists or older PostgreSQL without IF NOT EXISTS
