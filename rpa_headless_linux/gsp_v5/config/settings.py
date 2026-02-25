# ──────────────────────────────────────────────
# GSP Bot v5 - Configuration Settings
# ──────────────────────────────────────────────
# Usa el mismo patrón de seguridad que el resto del monorepo:
#   GitHub Secrets/Vars → env: block en workflow → os.getenv() → Vault.get_secret()
# Nunca se genera un .env en disco. Dentro de Docker las variables
# se inyectan vía docker-compose environment / --env-file.
# ──────────────────────────────────────────────
from __future__ import annotations

import os
import sys
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field

# ── Integración con Vault del monorepo ────────
# Intentamos importar Vault; si no está disponible (ej. dentro de Docker
# sin acceso al path del monorepo), usamos os.getenv directo.
try:
    from core_shared.security.vault import Vault
    _USE_VAULT = True
except ImportError:
    _USE_VAULT = False


def _secret(key: str, default: str = "") -> str:
    """
    Lee un secreto usando el patrón estándar del monorepo:
      1. Vault.get_secret() (= os.getenv con logging)
      2. Fallback a os.getenv directo
    Compatible con ejecución dentro y fuera de Docker.
    """
    if _USE_VAULT:
        val = Vault.get_secret(key)
        if val:
            return val
    return os.getenv(key, default)


class Settings(BaseSettings):
    """
    Configuración centralizada.
    - Dentro de Docker: lee de environment vars inyectadas por docker-compose.
    - Fuera de Docker (CLI/tests): lee de os.getenv, que viene del env: block
      del workflow o del shell local. Vault.get_secret() como wrapper.
    """

    # ── General ───────────────────────────────
    app_env: str = Field("production", alias="APP_ENV")
    log_level: str = Field("INFO", alias="LOG_LEVEL")
    log_format: str = Field("json", alias="LOG_FORMAT")  # json | console
    base_dir: Path = Path(__file__).resolve().parent.parent

    # ── Redis ─────────────────────────────────
    redis_host: str = Field("redis", alias="REDIS_HOST")
    redis_port: int = Field(6379, alias="REDIS_PORT")
    redis_db: int = Field(0, alias="REDIS_DB")
    redis_password: str = Field("", alias="REDIS_PASSWORD")

    # ── PostgreSQL ────────────────────────────
    postgres_host: str = Field("postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(5432, alias="POSTGRES_PORT")
    postgres_db: str = Field("gsp_bot", alias="POSTGRES_DB")
    postgres_user: str = Field("gsp", alias="POSTGRES_USER")
    postgres_password: str = Field("changeme", alias="POSTGRES_PASSWORD")

    # ── Celery ────────────────────────────────
    celery_broker_url: str = Field("redis://redis:6379/0", alias="CELERY_BROKER_URL")
    celery_result_backend: str = Field("redis://redis:6379/1", alias="CELERY_RESULT_BACKEND")
    celery_concurrency: int = Field(3, alias="CELERY_CONCURRENCY")
    celery_max_retries: int = Field(3, alias="CELERY_MAX_RETRIES")
    celery_retry_delay: int = Field(30, alias="CELERY_RETRY_DELAY")

    # ── Workers ───────────────────────────────
    worker_count: int = Field(3, alias="WORKER_COUNT")

    # ── GSP (credenciales sensibles via Vault) ─
    gsp_login_url: str = Field(
        "https://natura-auth.prd.naturacloud.com/?company=natura"
        "&client_id=3ec6rhfe52b2k78h32kv7ml6ti"
        "&redirect_uri=https://gsp.natura.com&country=CL&language=es",
        alias="GSP_LOGIN_URL",
    )
    gsp_user_code: str = Field(default_factory=lambda: _secret("GSP_USER_CODE"), alias="GSP_USER_CODE")
    gsp_password: str = Field(default_factory=lambda: _secret("GSP_PASSWORD"), alias="GSP_PASSWORD")

    # ── Playwright ────────────────────────────
    playwright_headless: bool = Field(True, alias="PLAYWRIGHT_HEADLESS")
    playwright_timeout: int = Field(60000, alias="PLAYWRIGHT_TIMEOUT")
    playwright_slow_mo: int = Field(100, alias="PLAYWRIGHT_SLOW_MO")
    screenshot_on_error: bool = Field(True, alias="SCREENSHOT_ON_ERROR")
    screenshot_dir: Path = Field(Path("/app/screenshots"), alias="SCREENSHOT_DIR")

    # ── FastAPI ───────────────────────────────
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8000, alias="API_PORT")

    # ── Flower ────────────────────────────────
    flower_port: int = Field(5555, alias="FLOWER_PORT")

    @property
    def database_url(self) -> str:
        # Contraseña sensible: Vault-first
        pw = _secret("POSTGRES_PASSWORD", self.postgres_password)
        return (
            f"postgresql://{self.postgres_user}:{pw}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def async_database_url(self) -> str:
        return self.database_url.replace("postgresql://", "postgresql+asyncpg://")

    @property
    def redis_url(self) -> str:
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    class Config:
        # Sin env_file: las variables se inyectan via env: block (workflow)
        # o via docker-compose environment:
        env_file_encoding = "utf-8"
        populate_by_name = True


@lru_cache()
def get_settings() -> Settings:
    """Singleton cached settings instance."""
    return Settings()
