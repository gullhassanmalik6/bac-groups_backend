from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.v1.deps import CurrentUser
from app.core.responses import success_response
from app.payouts.eligibility import evaluate_payout_eligibility

router = APIRouter(prefix="/payouts", tags=["Payouts"])


class PayoutQuoteRequest(BaseModel):
    settlement_confirmed: bool = False
    provider_configured: bool = False
    destination_address: str | None = Field(default=None, max_length=64)
    amount: str | None = None
    currency: str | None = Field(default="USDT", max_length=8)


@router.post("/quote")
async def payout_quote(payload: PayoutQuoteRequest, user: CurrentUser):
    """Eligibility only. Never broadcasts TRC20 or invents a chain hash."""
    _ = user
    from decimal import Decimal, InvalidOperation

    amount = None
    if payload.amount:
        try:
            amount = Decimal(payload.amount)
        except InvalidOperation:
            amount = None
    result = evaluate_payout_eligibility(
        settlement_confirmed=payload.settlement_confirmed,
        provider_configured=payload.provider_configured,
        destination_address=payload.destination_address,
        amount=amount,
        currency=payload.currency,
    )
    return success_response(
        data={
            "status": result.status,
            "reason": result.reason,
            "network": result.network,
            "destination_masked": result.destination_masked,
            "amount": str(result.amount) if result.amount is not None else None,
            "currency": result.currency,
            "provider_configured": result.provider_configured,
            "live_payout": False,
        }
    )
