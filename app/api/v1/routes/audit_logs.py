from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select

from app.api.v1.deps import CurrentUser, DbSession
from app.core.enums import UserRole
from app.core.responses import success_response
from app.models.website import AuditLog
from app.services.audit_service import sanitize_metadata

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


class AuditLogOut(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    action: str
    resource_type: str
    resource_id: str | None
    ip_address: str | None
    details: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("")
async def list_audit_logs(
    session: DbSession,
    user: CurrentUser,
    action: str | None = Query(default=None),
    resource_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
):
    """
    List audit events for the current actor (merchants see their own actions).
    Admins may pass without actor filter when role is admin/super_admin.
    Never returns PAN/CVV (sanitized at write time).
    """
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)

    is_admin = user.role_code in {UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value}
    if not is_admin:
        stmt = stmt.where(AuditLog.actor_user_id == user.id)

    rows = (await session.scalars(stmt)).all()
    items = [
        AuditLogOut(
            id=row.id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            resource_type=row.resource_type,
            resource_id=row.resource_id,
            ip_address=row.ip_address,
            details=sanitize_metadata(row.details) if row.details else None,
            created_at=row.created_at,
        ).model_dump(mode="json")
        for row in rows
    ]
    return success_response(data={"items": items, "total": len(items)})
