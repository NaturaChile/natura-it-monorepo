# ──────────────────────────────────────────────
# Celery Application Configuration
# ──────────────────────────────────────────────
from __future__ import annotations

from celery import Celery
from celery.signals import worker_init

from config.settings import get_settings
from shared.logging_config import setup_logging

settings = get_settings()

app = Celery(
    "gsp_worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["worker.tasks"],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone
    timezone="America/Santiago",
    enable_utc=True,

    # Concurrency and prefetch
    worker_concurrency=settings.celery_concurrency,
    worker_prefetch_multiplier=1,  # One task at a time per worker slot

    # Results
    result_expires=86400,  # 24h
    task_track_started=True,

    # Retry
    task_acks_late=True,  # ACK after task completes (not before)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes

    # Rate limiting
    task_default_rate_limit="10/m",  # Max 10 tasks per minute per worker

    # Routing
    task_routes={
        "worker.tasks.process_order": {"queue": "orders"},
        "worker.tasks.process_batch": {"queue": "batches"},
        "worker.tasks.health_check": {"queue": "default"},
    },

    # Dead letter / retry policy
    task_default_retry_delay=settings.celery_retry_delay,
    task_max_retries=settings.celery_max_retries,

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)


@worker_init.connect
def init_worker(**kwargs):
    """Initialize logging and DB when worker starts."""
    setup_logging()
    from shared.database import init_db
    init_db()
