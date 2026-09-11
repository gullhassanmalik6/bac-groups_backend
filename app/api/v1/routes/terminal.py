from uuid import UUID

from fastapi import APIRouter, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.responses import success_response
from app.schemas.terminal import (
    AuthorizeTerminalSessionRequest,
    CreateTerminalSessionRequest,
    RefundTerminalSessionRequest,
)
from app.services.payment_service import PaymentService
from app.services.terminal_session_service import TerminalSessionService

router = APIRouter(prefix="/terminal", tags=["Terminal Sessions"])


@router.get("/protocols")
async def list_terminal_protocols(user: CurrentUser, transaction_type: str | None = None):
    """Alias of POS protocol catalog under /terminal namespace."""
    _ = user
    items = PaymentService.list_pos_protocols(transaction_type=transaction_type)
    return success_response(data=[p.model_dump() for p in items])


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    payload: CreateTerminalSessionRequest,
    session: DbSession,
    user: CurrentUser,
):
    service = TerminalSessionService(session)
    out = await service.create(user.id, payload)
    return success_response(data=out.model_dump(mode="json"), message="Terminal session created", status_code=201)


@router.get("/sessions")
async def list_sessions(
    session: DbSession,
    user: CurrentUser,
    status: str | None = None,
    protocol: str | None = None,
    currency: str | None = None,
):
    service = TerminalSessionService(session)
    items = await service.list_sessions(
        user.id,
        status=status,
        protocol=protocol,
        currency=currency,
    )
    return success_response(
        data={"items": [i.model_dump(mode="json") for i in items], "total": len(items)}
    )


@router.get("/sessions/{session_id}")
async def get_session(session_id: UUID, session: DbSession, user: CurrentUser):
    service = TerminalSessionService(session)
    out = await service.get(user.id, session_id)
    return success_response(data=out.model_dump(mode="json"))


@router.post("/sessions/{session_id}/authorize")
async def authorize_session(
    session_id: UUID,
    payload: AuthorizeTerminalSessionRequest,
    session: DbSession,
    user: CurrentUser,
):
    service = TerminalSessionService(session)
    out = await service.authorize(user.id, session_id, payload)
    return success_response(data=out.model_dump(mode="json"), message="Authorization processed")


@router.post("/sessions/{session_id}/capture")
async def capture_session(session_id: UUID, session: DbSession, user: CurrentUser):
    service = TerminalSessionService(session)
    out = await service.capture(user.id, session_id)
    return success_response(data=out.model_dump(mode="json"), message="Capture processed")


@router.post("/sessions/{session_id}/void")
async def void_session(session_id: UUID, session: DbSession, user: CurrentUser):
    service = TerminalSessionService(session)
    out = await service.void(user.id, session_id)
    return success_response(data=out.model_dump(mode="json"), message="Void processed")


@router.post("/sessions/{session_id}/refund")
async def refund_session(
    session_id: UUID,
    payload: RefundTerminalSessionRequest,
    session: DbSession,
    user: CurrentUser,
):
    service = TerminalSessionService(session)
    out = await service.refund(user.id, session_id, payload)
    return success_response(data=out.model_dump(mode="json"), message="Refund processed")


@router.post("/sessions/{session_id}/cancel")
async def cancel_session(session_id: UUID, session: DbSession, user: CurrentUser):
    service = TerminalSessionService(session)
    out = await service.cancel(user.id, session_id)
    return success_response(data=out.model_dump(mode="json"), message="Session cancelled")
