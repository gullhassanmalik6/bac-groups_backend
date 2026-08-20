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

NOWPAYMENTS_API = "https://api.nowpayments.io/v1"
PAY_CURRENCY_USDT_TRC20 = "usdttrc20"

# Pending official confirmation: Saudi merchant fiat eligibility + Sunmi V3 card capture path.
POS_VERIFICATION_BLOCK = (
    "NOWPayments is registered but not enabled for live Sunmi POS charges yet. "
    "Provider verification is in progress (Saudi company KYB, fiat-to-crypto eligibility, "
    "and physical card capture on Sunmi V3). Use gateway_provider=sandbox until approved."
)


def _normalize_fiat_currency(currency: str) -> str:
    return currency.strip().lower()


class NowPaymentsGateway(PaymentGateway):
    """NOWPayments invoice/IPN adapter. Fail-closed until keys exist and POS flow is verified."""

    provider_name = "nowpayments"

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.nowpayments_api_key.strip()
        self._ipn_secret = settings.nowpayments_ipn_secret.strip()
        self._timeout = settings.nowpayments_timeout_seconds
        self._pos_verified = settings.nowpayments_pos_verified

    def _client(self) -> httpx.AsyncClient:
        if not self._api_key:
            raise RuntimeError("NOWPAYMENTS_API_KEY is not configured")
        return httpx.AsyncClient(
            base_url=NOWPAYMENTS_API,
            timeout=self._timeout,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "x-api-key": self._api_key,
            },
        )

    async def charge(self, request: PaymentRequest) -> PaymentResult:
        if not self._api_key:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=(
                    "NOWPayments is not configured. Add NOWPAYMENTS_API_KEY on Railway "
                    "after merchant approval, or use gateway_provider=sandbox."
                ),
                raw_response={"provider": self.provider_name, "configured": False},
            )

        if not self._pos_verified:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=POS_VERIFICATION_BLOCK,
                raw_response={"provider": self.provider_name, "pos_verified": False},
            )

        payload: dict[str, Any] = {
            "price_amount": str(request.amount),
            "price_currency": _normalize_fiat_currency(request.currency),
            "pay_currency": PAY_CURRENCY_USDT_TRC20,
            "order_id": request.merchant_reference,
            "order_description": request.description,
            "is_fixed_rate": True,
        }
        callback = request.metadata.get("ipn_callback_url")
        if isinstance(callback, str) and callback.strip():
            payload["ipn_callback_url"] = callback.strip()

        try:
            async with self._client() as client:
                response = await client.post("/invoice", json=payload)
                body = response.json()
        except httpx.HTTPError as exc:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=f"NOWPayments network error: {exc}",
                raw_response={"provider": self.provider_name},
            )

        if not response.is_success:
            message = str(body.get("message") or body.get("error") or "Invoice creation failed")
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference="",
                error_message=message,
                raw_response=body if isinstance(body, dict) else {"body": body},
            )

        invoice_id = str(body.get("id") or body.get("invoice_id") or "")
        return PaymentResult(
            success=False,
            status=TransactionStatus.PENDING,
            gateway_reference=invoice_id,
            payment_method="nowpayments_invoice",
            raw_response=body if isinstance(body, dict) else {},
            error_message=(
                "NOWPayments invoice created. Customer must complete hosted fiat payment; "
                "final USDT settlement is confirmed via IPN webhook."
            ),
        )

    async def refund(self, request: RefundRequest) -> RefundResult:
        return RefundResult(
            success=False,
            status=TransactionStatus.FAILED,
            refund_reference="",
            error_message=(
                "NOWPayments refunds are not automated in CryptoPOS yet. "
                "Handle refund policy with NOWPayments support after go-live."
            ),
            raw_response={"provider": self.provider_name, "gateway_reference": request.gateway_reference},
        )

    async def verify_callback(self, headers: dict[str, str], payload: dict[str, Any]) -> PaymentResult:
        payment_status = str(
            payload.get("payment_status") or payload.get("status") or ""
        ).lower()
        payment_id = str(payload.get("payment_id") or payload.get("invoice_id") or payload.get("id") or "")
        success = payment_status in {"finished", "confirmed", "paid", "completed"}
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=payment_id,
            payment_method="nowpayments",
            raw_response={"headers": headers, "payload": payload},
            error_message=None if success else f"NOWPayments status: {payment_status or 'unknown'}",
        )

    async def get_status(self, gateway_reference: str) -> PaymentResult:
        if not self._api_key:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference=gateway_reference,
                error_message="NOWPayments is not configured",
            )
        try:
            async with self._client() as client:
                response = await client.get(f"/payment/{gateway_reference}")
                body = response.json()
        except httpx.HTTPError as exc:
            return PaymentResult(
                success=False,
                status=TransactionStatus.FAILED,
                gateway_reference=gateway_reference,
                error_message=str(exc),
            )
        status = str(body.get("payment_status") or body.get("status") or "").lower()
        success = response.is_success and status in {"finished", "confirmed", "paid", "completed"}
        return PaymentResult(
            success=success,
            status=TransactionStatus.CAPTURED if success else TransactionStatus.FAILED,
            gateway_reference=str(body.get("payment_id") or gateway_reference),
            payment_method="nowpayments",
            raw_response=body if isinstance(body, dict) else {},
        )
