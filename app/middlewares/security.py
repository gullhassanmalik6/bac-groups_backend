from collections.abc import Callable
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings
from app.core.responses import error_response

# Auth endpoints get a tighter per-IP budget (brute-force mitigation).
_AUTH_PATH_SUFFIXES = (
    "/auth/login",
    "/auth/register",
    "/auth/refresh",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory rate limiter with stricter auth budgets.

    Replace with Redis for multi-instance production (settings.redis_url).
    """

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[str, list[float]] = {}
        self._auth_hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        path = request.url.path
        if path.endswith("/health"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time()

        # Global budget
        window = self._hits.setdefault(client, [])
        self._hits[client] = [stamp for stamp in window if now - stamp < 60]
        if len(self._hits[client]) >= settings.rate_limit_per_minute:
            return error_response("Rate limit exceeded", status_code=429)
        self._hits[client].append(now)

        # Auth-specific budget
        if any(path.endswith(suffix) for suffix in _AUTH_PATH_SUFFIXES):
            auth_window = self._auth_hits.setdefault(client, [])
            self._auth_hits[client] = [stamp for stamp in auth_window if now - stamp < 60]
            if len(self._auth_hits[client]) >= settings.auth_rate_limit_per_minute:
                return error_response("Auth rate limit exceeded", status_code=429)
            self._auth_hits[client].append(now)

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        # API responses should not be cached by shared caches.
        if "/api/" in request.url.path:
            response.headers.setdefault("Cache-Control", "no-store")
        # Minimal CSP for API JSON (blocks accidental HTML framing/injection).
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response
