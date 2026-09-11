"""Security headers middleware tests (no database)."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.middlewares.security import SecurityHeadersMiddleware


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/v1/ping")
    async def ping():
        return {"ok": True}

    return TestClient(app)


def test_security_headers_present_on_responses():
    client = _client()
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers["Permissions-Policy"]
    assert response.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]


def test_api_paths_set_cache_control_no_store():
    client = _client()
    api = client.get("/api/v1/ping")
    assert api.headers["Cache-Control"] == "no-store"
    health = client.get("/health")
    assert "Cache-Control" not in health.headers or health.headers.get("Cache-Control") != "no-store"
