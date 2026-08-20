from fastapi import APIRouter

from app.core.config import get_settings
from app.core.responses import success_response

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health():
    settings = get_settings()
    return success_response(
        data={
            "status": "ok",
            "service": settings.app_name,
            "version": settings.app_version,
            "environment": settings.app_env,
        }
    )
