from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.responses import success_response
from app.schemas.payment import CompleteSignatureRequest, SandboxTokenRequest
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/pos", tags=["POS Terminal"])


@router.get("/protocols")
async def list_protocols(
    user: CurrentUser,
    mode: str | None = Query(default=None, description="Filter: online | offline_test"),
    family: str | None = Query(default=None, description="Filter: 101 | 201 | 202"),
    transaction_type: str | None = Query(
        default=None,
        description="Filter by SALE | REFUND | VOID | AUTH | COMPLETION",
    ),
):
    """Protocol profile catalog — application profiles, not live card-network specs."""
    _ = user
    items = PaymentService.list_pos_protocols(
        mode=mode,
        family=family,
        transaction_type=transaction_type,
    )
    return success_response(data=[p.model_dump() for p in items])


@router.post("/sandbox/tokenize", status_code=status.HTTP_201_CREATED)
async def sandbox_tokenize(payload: SandboxTokenRequest, user: CurrentUser):
    """
    Convert documented TEST card hints into a payment_method_token.
    Never persists PAN/CVV. Production must use a certified processor token.
    """
    _ = user
    token = PaymentService.issue_sandbox_token(payload)
    return success_response(data=token.model_dump(), message="Sandbox token issued", status_code=201)


@router.post("/transactions/{transaction_id}/signature")
async def complete_signature(
    transaction_id: UUID,
    payload: CompleteSignatureRequest,
    session: DbSession,
    user: CurrentUser,
):
    service = PaymentService(session)
    payment = await service.complete_signature(user.id, transaction_id, payload)
    return success_response(data=payment.model_dump(mode="json"), message="Signature recorded")


@router.post("/transactions/{transaction_id}/cancel")
async def cancel_transaction(transaction_id: UUID, session: DbSession, user: CurrentUser):
    service = PaymentService(session)
    payment = await service.cancel_payment(user.id, transaction_id)
    return success_response(data=payment.model_dump(mode="json"), message="Transaction cancelled")
