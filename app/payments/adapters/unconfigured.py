from app.core.enums import TransactionStatus
from app.payments.base import (
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
    RefundRequest,
    RefundResult,
)


class UnconfiguredPaymentGateway(PaymentGateway):
    """Fail-closed adapter for providers that are registered but not credentialed."""

    provider_name = "unconfigured"

    def __init__(self, provider_name: str, display_name: str) -> None:
        self.provider_name = provider_name
        self._display_name = display_name

    def _blocked(self) -> str:
        return (
            f"{self._display_name} credentials are not configured. "
            "Launch uses NOWPayments after verification, or sandbox for Sunmi testing. "
            "Use gateway_provider=sandbox for device testing."
        )

    async def charge(self, request: PaymentRequest) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=TransactionStatus.FAILED,
            gateway_reference="",
            error_message=self._blocked(),
            raw_response={"provider": self.provider_name, "configured": False},
        )

    async def refund(self, request: RefundRequest) -> RefundResult:
        return RefundResult(
            success=False,
            status=TransactionStatus.FAILED,
            refund_reference="",
            error_message=self._blocked(),
        )

    async def verify_callback(self, headers: dict[str, str], payload: dict) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=TransactionStatus.FAILED,
            gateway_reference=str(payload.get("id") or ""),
            error_message=self._blocked(),
            raw_response={"headers": headers, "payload": payload},
        )

    async def get_status(self, gateway_reference: str) -> PaymentResult:
        return PaymentResult(
            success=False,
            status=TransactionStatus.FAILED,
            gateway_reference=gateway_reference,
            error_message=self._blocked(),
        )


class HyperPayGateway(UnconfiguredPaymentGateway):
    def __init__(self) -> None:
        super().__init__("hyperpay", "HyperPay")


class CheckoutGateway(UnconfiguredPaymentGateway):
    def __init__(self) -> None:
        super().__init__("checkout", "Checkout.com")


class StripeGateway(UnconfiguredPaymentGateway):
    def __init__(self) -> None:
        super().__init__("stripe", "Stripe")
