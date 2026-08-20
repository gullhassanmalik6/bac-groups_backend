from decimal import Decimal
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.enums import TransactionStatus
from app.payments.base import (
    PaymentGateway,
    PaymentRequest,
    PaymentResult,
    RefundRequest,
    RefundResult,
)

MOYASAR_API = "https://api.moyasar.com/v1"


def _to_minor_units(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


class MoyasarPaymentGateway(PaymentGateway):
    """Official Moyasar Payments API adapter. Fails closed without credentials."""

    provider_name = "moyasar"

    def __init__(self) -> None:
        settings = get_settings()
        self._secret = settings.moyasar_secret_key.strip()
        self._timeout = settings.moyasar_timeout_seconds

    def _client(self) -> httpx.AsyncClient:
        if not self._secret:
            raise RuntimeError("MOYASAR_SECRET_KEY is not configured")
        return httpx.AsyncClient(
            base_url=MOYASAR_API,
            auth=(self._secret, ""),
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )

    async def charge(self, request: PaymentRequest) -> PaymentResult:
        if not self._secret:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=(
                    "Moyasar is not configured. Add MOYASAR_SECRET_KEY on Railway "
                    "or use gateway_provider=sandbox until the merchant account is approved."
                ),
                raw_response={"provider": self.provider_name, "configured": False},
            )

        source = request.metadata.get("moyasar_source")
        if not isinstance(source, dict):
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=(
                    "Moyasar requires a tokenized card source. NFC tap on the POS does not "
                    "expose PAN. Use sandbox for device testing, or supply a Moyasar token "
                    "after the hosted payment / Sunmi acquiring path is enabled."
                ),
                raw_response={"provider": self.provider_name, "reason": "missing_source"},
            )

        payload: dict[str, Any] = {
            "amount": _to_minor_units(request.amount),
            "currency": request.currency.upper(),
            "description": request.description,
            "metadata": {
                "merchant_reference": request.merchant_reference,
                **{k: str(v) for k, v in request.metadata.items() if k != "moyasar_source"},
            },
            "source": source,
        }

        try:
            async with self._client() as client:
                response = await client.post("/payments", json=payload)
                body = response.json()
        except httpx.HTTPError as exc:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=f"Moyasar network error: {exc}",
                raw_response={"provider": self.provider_name},
            )

        payment_id = str(body.get("id") or "")
        status = str(body.get("status") or "failed")
        success = response.is_success and status in {"paid", "captured", "authorized"}
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=payment_id,
            payment_method=str((body.get("source") or {}).get("company") or "card"),
            raw_response=body if isinstance(body, dict) else {"body": body},
            error_message=None if success else str(body.get("message") or body.get("type") or "Moyasar declined"),
        )

    async def refund(self, request: RefundRequest) -> RefundResult:
        if not self._secret:
            return RefundResult(
                success=False,
                status=TransactionStatus.FAILED,
                refund_reference="",
                error_message="Moyasar is not configured",
            )
        try:
            async with self._client() as client:
                response = await client.post(
                    f"/payments/{request.gateway_reference}/refund",
                    json={"amount": _to_minor_units(request.amount)},
                )
                body = response.json()
        except httpx.HTTPError as exc:
            return RefundResult(
                success=False,
                status=TransactionStatus.FAILED,
                refund_reference="",
                error_message=str(exc),
            )
        success = response.is_success
        return RefundResult(
            success=success,
            status=TransactionStatus.REFUNDED if success else TransactionStatus.FAILED,
            refund_reference=str(body.get("id") or request.gateway_reference),
            raw_response=body if isinstance(body, dict) else {},
            error_message=None if success else str(body.get("message") or "Refund failed"),
        )

    async def verify_callback(self, headers: dict[str, str], payload: dict[str, Any]) -> PaymentResult:
        payment_id = str(payload.get("id") or payload.get("data", {}).get("id") or "")
        status = str(payload.get("status") or "")
        success = status in {"paid", "captured", "authorized"}
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=payment_id,
            payment_method="card",
            raw_response={"headers": headers, "payload": payload},
        )

    async def get_status(self, gateway_reference: str) -> PaymentResult:
        if not self._secret:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference=gateway_reference,
                error_message="Moyasar is not configured",
            )
        async with self._client() as client:
            response = await client.get(f"/payments/{gateway_reference}")
            body = response.json()
        status = str(body.get("status") or "")
        success = response.is_success and status in {"paid", "captured", "authorized"}
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=str(body.get("id") or gateway_reference),
            payment_method=str((body.get("source") or {}).get("company") or "card"),
            raw_response=body if isinstance(body, dict) else {},
        )
