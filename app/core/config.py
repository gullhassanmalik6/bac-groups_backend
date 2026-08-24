from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_cors_origins(value: object) -> list[str]:
    """Accept JSON arrays, comma-separated hosts, or empty (Railway-friendly)."""
    if value is None:
        return ["http://localhost:5173"]
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return ["http://localhost:5173"]
        if cleaned.startswith("["):
            import json

            try:
                parsed = json.loads(cleaned)
            except json.JSONDecodeError:
                return [cleaned]
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
            return [str(parsed).strip()] if str(parsed).strip() else ["http://localhost:5173"]
        return [item.strip() for item in cleaned.split(",") if item.strip()]
    return ["http://localhost:5173"]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "CryptoPOS"
    app_env: Literal["development", "testing", "production"] = "development"
    app_debug: bool = False
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api/v1"

    secret_key: str = Field(min_length=32)
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    jwt_algorithm: str = "HS256"

    database_url: str
    database_url_sync: str = ""

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Stored as a plain string so Railway env values are not JSON-decoded by pydantic-settings.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    rate_limit_per_minute: int = 120

    default_payment_gateway: str = "sandbox"
    default_exchange_provider: str = "sandbox"
    default_wallet_network: str = "trc20"
    allowed_currencies: str = "SAR,USD,EUR"

    nowpayments_api_key: str = ""
    nowpayments_ipn_secret: str = ""
    nowpayments_timeout_seconds: float = 30.0
    nowpayments_pos_verified: bool = False

    moyasar_secret_key: str = ""
    moyasar_publishable_key: str = ""
    moyasar_webhook_secret: str = ""
    moyasar_timeout_seconds: float = 30.0

    platform_fee_percent: float = 1.5
    settlement_currency: str = "USDT"

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "info@bacgroupsa.com"

    @model_validator(mode="after")
    def normalize_database_urls(self) -> "Settings":
        async_source = _sanitize_database_source(self.database_url)

        if self.app_env == "production":
            if "localhost" in async_source.lower() or "127.0.0.1" in async_source.lower():
                raise ValueError(
                    "DATABASE_URL must use Railway Postgres in production "
                    "(set to ${{Postgres.DATABASE_URL}} only). Remove localhost URLs."
                )
            # Alembic uses sync URL — always derive from DATABASE_URL in production.
            sync_source = async_source
        else:
            sync_source = _sanitize_database_source(self.database_url_sync or async_source)

        # asyncpg wants ssl=require; psycopg wants sslmode=require.
        self.database_url = _as_async_postgres(_with_asyncpg_ssl(async_source))
        self.database_url_sync = _as_sync_postgres(_with_psycopg_ssl(sync_source))
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return parse_cors_origins(self.cors_origins)

    @property
    def supported_currencies(self) -> set[str]:
        return {item.strip().upper() for item in self.allowed_currencies.split(",") if item.strip()}


def _strip_driver(url: str) -> str:
    value = url.strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgresql+psycopg2://"):
        if value.startswith(prefix):
            return "postgresql://" + value[len(prefix) :]
    return value


def _sanitize_database_source(url: str) -> str:
    """Strip accidental paste of a second URL after the Railway database name."""
    value = url.strip()
    for marker in ("postgresql+asyncpg://", "postgresql+psycopg://", "postgres://", "postgresql://"):
        if marker in value and not value.startswith(marker):
            head, _, _tail = value.partition(marker)
            if head.startswith(("postgres://", "postgresql://")):
                return head.rstrip("/")
    return value


def _is_local_db(url: str) -> bool:
    lowered = url.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered


def _strip_ssl_query_params(url: str) -> str:
    """Remove ssl / sslmode query params so we can re-apply driver-specific ones."""
    if "?" not in url:
        return url
    base, _, query = url.partition("?")
    kept = [
        part
        for part in query.split("&")
        if part and not part.lower().startswith("ssl=") and not part.lower().startswith("sslmode=")
    ]
    return f"{base}?{'&'.join(kept)}" if kept else base


def _with_asyncpg_ssl(url: str) -> str:
    """asyncpg rejects sslmode=; use ssl=require for Railway."""
    value = _strip_ssl_query_params(url.strip())
    if _is_local_db(value):
        return value
    if "ssl=" in value.lower():
        return value
    return f"{value}{'&' if '?' in value else '?'}ssl=require"


def _with_psycopg_ssl(url: str) -> str:
    """psycopg uses sslmode=require for Railway Postgres."""
    value = _strip_ssl_query_params(url.strip())
    if _is_local_db(value):
        return value
    if "sslmode=" in value.lower():
        return value
    return f"{value}{'&' if '?' in value else '?'}sslmode=require"


def _as_async_postgres(url: str) -> str:
    return "postgresql+asyncpg://" + _strip_driver(url).removeprefix("postgresql://")


def _as_sync_postgres(url: str) -> str:
    return "postgresql+psycopg://" + _strip_driver(url).removeprefix("postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
