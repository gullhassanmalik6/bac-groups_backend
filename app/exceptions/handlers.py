from datetime import UTC, datetime

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import ORJSONResponse
from sqlalchemy.exc import IntegrityError

from app.core.logging import get_logger
from app.core.responses import error_response
from app.exceptions.base import AppException

logger = get_logger(__name__)


async def app_exception_handler(_: Request, exc: AppException) -> ORJSONResponse:
    return error_response(
        message=exc.message,
        status_code=exc.status_code,
        errors=exc.errors,
        data=exc.data,
    )


async def validation_exception_handler(_: Request, exc: RequestValidationError) -> ORJSONResponse:
    field_errors: dict[str, list[str]] = {}
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", []) if part != "body")
        field_errors.setdefault(location or "body", []).append(error.get("msg", "Invalid value"))
    return error_response(
        message="Validation failed",
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        errors=field_errors,
    )


async def integrity_exception_handler(_: Request, exc: IntegrityError) -> ORJSONResponse:
    logger.warning("database_integrity_error", error=str(exc.orig))
    return error_response(
        message="Database constraint violation",
        status_code=status.HTTP_409_CONFLICT,
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> ORJSONResponse:
    logger.exception("unhandled_exception", error=str(exc))
    return ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "data": None,
            "errors": None,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )
