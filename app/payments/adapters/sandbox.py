from decimal import Decimal
from uuid import uuid4

from app.core.enums import TransactionStatus
from app.payments.base import (
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
    RefundRequest,
    RefundResult,
)


class SandboxPaymentGateway(PaymentGateway):
    """Deterministic sandbox adapter for local/dev and integration tests."""

    provider_name = "sandbox"

    async def charge(self, request: PaymentRequest) -> PaymentResult:
        reference = f"sbx_{uuid4().hex[:16]}"
        # Fail intentionally when amount ends with .13 for testability.
        if request.amount % 1 == Decimal("0.13"):
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference=reference,
                payment_method="visa",
                raw_response={"provider": self.provider_name, "reason": "sandbox_forced_failure"},
                error_message="Sandbox forced failure for amount ending in .13",
            )
        return PaymentResult(
            success=True,
            status=TransactionStatus.CAPTURED,
            gateway_reference=reference,
            payment_method="visa",
            raw_response={
                "provider": self.provider_name,
                "amount": str(request.amount),
                "currency": request.currency,
                "merchant_reference": request.merchant_reference,
            },
        )

    async def refund(self, request: RefundRequest) -> RefundResult:
        return RefundResult(
            success=True,
            status=TransactionStatus.REFUNDED,
            refund_reference=f"sbx_rf_{uuid4().hex[:12]}",
            raw_response={"provider": self.provider_name, "original": request.gateway_reference},
        )

    async def verify_callback(self, headers: dict[str, str], payload: dict) -> PaymentResult:
        reference = str(payload.get("gateway_reference") or f"sbx_cb_{uuid4().hex[:12]}")
        success = bool(payload.get("success", True))
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=reference,
            payment_method=str(payload.get("payment_method") or "visa"),
            raw_response={"headers": headers, "payload": payload},
            error_message=None if success else str(payload.get("error") or "Callback failure"),
        )

    async def get_status(self, gateway_reference: str) -> PaymentResult:
        return PaymentResult(
            success=True,
            status=TransactionStatus.CAPTURED,
            gateway_reference=gateway_reference,
            payment_method="visa",
            raw_response={"provider": self.provider_name, "gateway_reference": gateway_reference},
        )
