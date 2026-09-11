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

# Documented sandbox scenarios (no real cards). Clients send payment_token only.
# pm_test_visa_success  → CAPTURED
# pm_test_visa_declined → FAILED
# pm_test_visa_signature → AUTHORIZED + signature_required
# Amount ending .13 also forces failure (legacy test hook).


class SandboxPaymentGateway(PaymentGateway):
    """Deterministic sandbox adapter — never processes real card data."""

    provider_name = "sandbox"

    async def charge(self, request: PaymentRequest) -> PaymentResult:
        reference = f"sbx_{uuid4().hex[:16]}"
        auth = f"AUTH{uuid4().hex[:6].upper()}"
        token = str(request.metadata.get("payment_method_token") or request.metadata.get("payment_token") or "")
        scenario = str(request.metadata.get("sandbox_scenario") or "").lower()

        # Prefer explicit token / scenario; never accept raw PAN fields from metadata.
        for forbidden in ("pan", "card_number", "cvv", "cvc"):
            if forbidden in request.metadata:
                return PaymentResult(
                    success=False,
                    status=TransactionStatus.FAILED,
                    gateway_reference=reference,
                    error_message="Sandbox rejects raw card fields — send payment_method_token only",
                    raw_response={"provider": self.provider_name, "reason": "pci_reject"},
                )

        if request.amount % 1 == Decimal("0.13") or scenario == "declined" or token.endswith("declined"):
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference=reference,
                payment_method="visa",
                payment_method_token=token or None,
                card_last4="0002" if "declined" in token else None,
                raw_response={"provider": self.provider_name, "reason": "sandbox_forced_failure"},
                error_message="Sandbox declined (test scenario)",
            )

        from app.protocols.sandbox import resolve_sandbox_charge_flags

        protocol_code = str(request.metadata.get("protocol_code") or "") or None
        signature_required, prefer_authorized = resolve_sandbox_charge_flags(
            protocol_code,
            token=token,
            scenario=scenario,
        )

        status = (
            TransactionStatus.AUTHORIZED
            if (signature_required or prefer_authorized)
            else TransactionStatus.CAPTURED
        )

        return PaymentResult(
            success=True,
            status=status,
            gateway_reference=reference,
            payment_method="visa",
            authorization_code=auth,
            signature_required=signature_required,
            payment_method_token=token or f"pm_test_{uuid4().hex[:10]}",
            card_last4="1111",
            raw_response={
                "provider": self.provider_name,
                "amount": str(request.amount),
                "currency": request.currency,
                "merchant_reference": request.merchant_reference,
                "protocol_code": protocol_code,
                "signature_required": signature_required,
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
            raw_response={"headers": {k: v for k, v in headers.items() if "secret" not in k.lower()}, "payload": payload},
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
