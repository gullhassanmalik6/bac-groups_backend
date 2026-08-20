from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, Query, Request, status

from app.api.v1.deps import CurrentUser, DbSession
from app.core.responses import success_response
from app.schemas.payment import CreatePaymentRequest, RefundPaymentRequest
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("/webhooks/nowpayments")
async def nowpayments_webhook(request: Request, session: DbSession):
    body: dict[str, Any] = await request.json()
    headers = {key.lower(): value for key, value in request.headers.items()}
    service = PaymentService(session)
    result = await service.handle_nowpayments_webhook(headers, body)
    return success_response(data=result, message="Webhook accepted")


@router.post("/webhooks/moyasar")
async def moyasar_webhook(request: Request, session: DbSession):
    body: dict[str, Any] = await request.json()
    headers = {key.lower(): value for key, value in request.headers.items()}
    service = PaymentService(session)
    result = await service.handle_moyasar_webhook(headers, body)
    return success_response(data=result, message="Webhook accepted")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_payment(payload: CreatePaymentRequest, session: DbSession, user: CurrentUser):
    service = PaymentService(session)
    payment = await service.create_payment(user.id, payload)
    return success_response(
        data=payment.model_dump(mode="json"),
        message="Payment processed",
        status_code=201,
    )


@router.get("")
async def list_payments(
    session: DbSession,
    user: CurrentUser,
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    service = PaymentService(session)
    result = await service.list_payments(
        user.id, status=status_filter, page=page, page_size=page_size
    )
    return success_response(data=result.model_dump(mode="json"))


@router.post("/{transaction_id}/refund")
async def refund_payment(
    transaction_id: UUID,
    session: DbSession,
    user: CurrentUser,
    payload: RefundPaymentRequest = Body(default_factory=RefundPaymentRequest),
):
    service = PaymentService(session)
    payment = await service.refund_payment(user.id, transaction_id, payload)
    return success_response(data=payment.model_dump(mode="json"), message="Refund processed")


@router.get("/{transaction_id}")
async def get_payment(transaction_id: UUID, session: DbSession, user: CurrentUser):
    service = PaymentService(session)
    payment = await service.get_payment(user.id, transaction_id)
    return success_response(data=payment.model_dump(mode="json"))


@router.get("/{transaction_id}/receipt")
async def get_receipt(transaction_id: UUID, session: DbSession, user: CurrentUser):
    service = PaymentService(session)
    receipt = await service.get_receipt(user.id, transaction_id)
    return success_response(data=receipt.model_dump(mode="json"))
