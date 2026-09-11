from fastapi import APIRouter, Depends, Query

from app.api.v1.deps import CurrentUser, DbSession, require_roles
from app.core.enums import UserRole
from app.core.responses import success_response
from app.models.user import User
from app.services.admin_dashboard_service import AdminDashboardService

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard")
async def dashboard(
    session: DbSession,
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN)),
    days: int = Query(default=14, ge=1, le=90),
):
    """Ops admin dashboard: KPIs, chart series, devices, processor status."""
    service = AdminDashboardService(session)
    data = await service.build(days=days)
    return success_response(data=data.model_dump(mode="json"))


@router.get("/me-check")
async def admin_me(user: CurrentUser):
    return success_response(
        data={"id": str(user.id), "role": user.role_code, "email": user.email}
    )
