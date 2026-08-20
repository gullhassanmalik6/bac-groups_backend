from decimal import Decimal

import pytest

from app.payments.adapters.moyasar import MoyasarPaymentGateway
from app.payments.base import PaymentRequest


@pytest.mark.asyncio
async def test_moyasar_without_key_fails_closed():
    gateway = MoyasarPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("25.00"),
            currency="SAR",
            merchant_reference="mref-1",
            description="POS",
        )
    )
    assert result.success is False
    assert "not configured" in (result.error_message or "").lower() or "tokenized" in (result.error_message or "").lower()
