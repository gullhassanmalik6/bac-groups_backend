from typing import Any


class AppException(Exception):
    """Base application exception mapped to API error responses."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 400,
        errors: dict[str, list[str]] | None = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.errors = errors
        self.data = data


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message, status_code=401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "Permission denied") -> None:
        super().__init__(message, status_code=403)


class ConflictError(AppException):
    def __init__(self, message: str = "Conflict") -> None:
        super().__init__(message, status_code=409)


class PaymentError(AppException):
    def __init__(self, message: str = "Payment processing failed", data: Any = None) -> None:
        super().__init__(message, status_code=502, data=data)


class SettlementError(AppException):
    def __init__(self, message: str = "Settlement processing failed", data: Any = None) -> None:
        super().__init__(message, status_code=502, data=data)


class RateLimitError(AppException):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(message, status_code=429)
