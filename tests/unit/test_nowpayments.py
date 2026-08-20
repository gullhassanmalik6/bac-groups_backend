from decimal import Decimal

import pytest

from app.payments.adapters.nowpayments import NowPaymentsGateway
from app.payments.base import PaymentRequest


@pytest.mark.asyncio
async def test_nowpayments_without_key_fails_closed():
    gateway = NowPaymentsGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("25.00"),
            currency="SAR",
            merchant_reference="mref-np-1",
            description="POS",
        )
    )
    assert result.success is False
    assert "not configured" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_nowpayments_with_key_but_unverified_pos_fails_closed(monkeypatch):
    monkeypatch.setenv("NOWPAYMENTS_API_KEY", "test-key-for-unit-tests-only")
    monkeypatch.setenv("NOWPAYMENTS_POS_VERIFIED", "false")
    from app.core.config import get_settings

    get_settings.cache_clear()
    gateway = NowPaymentsGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("25.00"),
            currency="USD",
            merchant_reference="mref-np-2",
            description="POS",
        )
    )
    get_settings.cache_clear()
    assert result.success is False
    assert "verification" in (result.error_message or "").lower()
