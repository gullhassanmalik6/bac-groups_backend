from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:5173"])
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
    email_from: str = "noreply@cryptopos.com"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors(cls, value: object) -> object:
        if isinstance(value, str):
            cleaned = value.strip()
            if cleaned.startswith("["):
                import json

                return json.loads(cleaned)
            return [item.strip() for item in cleaned.split(",") if item.strip()]
        return value

    @model_validator(mode="after")
    def normalize_database_urls(self) -> "Settings":
        async_source = self.database_url
        sync_source = self.database_url_sync or self.database_url
        if self.app_env == "production":
            async_source = _append_sslmode_if_needed(async_source)
            sync_source = _append_sslmode_if_needed(sync_source)
        self.database_url = _as_async_postgres(async_source)
        self.database_url_sync = _as_sync_postgres(sync_source)
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

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


def _append_sslmode_if_needed(url: str) -> str:
    """Railway Postgres requires SSL; append sslmode when not using localhost."""
    value = url.strip()
    lowered = value.lower()
    if "localhost" in lowered or "127.0.0.1" in lowered:
        return value
    if "sslmode=" in lowered:
        return value
    return f"{value}{'&' if '?' in value else '?'}sslmode=require"


def _as_async_postgres(url: str) -> str:
    return "postgresql+asyncpg://" + _strip_driver(url).removeprefix("postgresql://")


def _as_sync_postgres(url: str) -> str:
    return "postgresql+psycopg://" + _strip_driver(url).removeprefix("postgresql://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
