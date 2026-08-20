from collections.abc import Callable
from time import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import get_settings
from app.core.responses import error_response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiter. Replace with Redis in multi-instance production."""

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if request.url.path.endswith("/health"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time()
        window = self._hits.setdefault(client, [])
        self._hits[client] = [stamp for stamp in window if now - stamp < 60]
        if len(self._hits[client]) >= settings.rate_limit_per_minute:
            return error_response("Rate limit exceeded", status_code=429)
        self._hits[client].append(now)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
