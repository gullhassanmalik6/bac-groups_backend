from decimal import Decimal

import pytest

from app.crypto.adapters.sandbox import SandboxExchangeProvider
from app.payments.adapters.sandbox import SandboxPaymentGateway
from app.payments.base import PaymentRequest
from app.wallet.adapters.trc20 import Trc20WalletProvider
from app.wallet.base import WalletTransferRequest


@pytest.mark.asyncio
async def test_sandbox_payment_success():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("100.00"),
            currency="SAR",
            merchant_reference="ref-1",
            description="Test",
        )
    )
    assert result.success is True
    assert result.gateway_reference.startswith("sbx_")


@pytest.mark.asyncio
async def test_sandbox_payment_forced_failure():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("10.13"),
            currency="SAR",
            merchant_reference="ref-fail",
            description="Test",
        )
    )
    assert result.success is False


@pytest.mark.asyncio
async def test_sandbox_exchange_sar_to_usdt():
    exchange = SandboxExchangeProvider()
    usdt, quote = await exchange.convert(Decimal("100.00"), "SAR", "USDT")
    assert quote.provider == "sandbox"
    assert usdt == Decimal("26.67000000")


@pytest.mark.asyncio
async def test_trc20_wallet_transfer():
    wallet = Trc20WalletProvider()
    result = await wallet.transfer(
        WalletTransferRequest(
            to_address="TXyzabcdefghijklmnopqrstuvwx123456",
            amount=Decimal("10.5"),
            network="trc20",
        )
    )
    assert result.success is True
    assert result.tx_hash is not None
