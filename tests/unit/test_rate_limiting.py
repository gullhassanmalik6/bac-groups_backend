"""Rate-limit middleware tests (no database)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.middlewares.security import RateLimitMiddleware


def _app_with_limits(*, global_limit: int, auth_limit: int) -> tuple[TestClient, int, int]:
    settings = get_settings()
    previous = (settings.rate_limit_per_minute, settings.auth_rate_limit_per_minute)
    settings.rate_limit_per_minute = global_limit
    settings.auth_rate_limit_per_minute = auth_limit

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/v1/ping")
    async def ping():
        return {"ok": True}

    @app.post("/api/v1/auth/login")
    async def login():
        return {"ok": True}

    return TestClient(app), previous[0], previous[1]


def _restore(global_limit: int, auth_limit: int) -> None:
    settings = get_settings()
    settings.rate_limit_per_minute = global_limit
    settings.auth_rate_limit_per_minute = auth_limit


def test_health_is_exempt_from_rate_limit():
    client, g, a = _app_with_limits(global_limit=2, auth_limit=2)
    try:
        for _ in range(8):
            assert client.get("/health").status_code == 200
    finally:
        _restore(g, a)


def test_global_rate_limit_returns_429():
    client, g, a = _app_with_limits(global_limit=3, auth_limit=100)
    try:
        assert client.get("/api/v1/ping").status_code == 200
        assert client.get("/api/v1/ping").status_code == 200
        assert client.get("/api/v1/ping").status_code == 200
        blocked = client.get("/api/v1/ping")
        assert blocked.status_code == 429
        assert "Rate limit" in blocked.json()["message"]
    finally:
        _restore(g, a)


def test_auth_path_has_stricter_budget():
    client, g, a = _app_with_limits(global_limit=100, auth_limit=2)
    try:
        assert client.post("/api/v1/auth/login").status_code == 200
        assert client.post("/api/v1/auth/login").status_code == 200
        blocked = client.post("/api/v1/auth/login")
        assert blocked.status_code == 429
        assert "Auth rate limit" in blocked.json()["message"]
    finally:
        _restore(g, a)
