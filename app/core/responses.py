from datetime import UTC, datetime
from typing import Any

from fastapi.responses import ORJSONResponse


def utc_now() -> datetime:
    return datetime.now(UTC)


def success_response(
    data: Any = None,
    message: str = "Success",
    status_code: int = 200,
) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "message": message,
            "data": data,
            "errors": None,
            "timestamp": utc_now().isoformat(),
        },
    )


def error_response(
    message: str,
    *,
    status_code: int = 400,
    errors: dict[str, list[str]] | None = None,
    data: Any = None,
) -> ORJSONResponse:
    return ORJSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "data": data,
            "errors": errors,
            "timestamp": utc_now().isoformat(),
        },
    )
