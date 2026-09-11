"""Fail-closed stub for a future certified SoftPOS / acquirer SDK.

Does not invent Visa, Mastercard, or Verifone host protocols.
Enable only after official docs + credentials are provisioned.
"""

from __future__ import annotations

from app.exceptions.base import AppException
from app.processors.base import PaymentProcessor, ProcessorResult


class UnconfiguredCertifiedPaymentProcessor(PaymentProcessor):
    """Registered under certified_* keys — always blocked until a real adapter exists."""

    name = "certified_unconfigured"
    is_sandbox = True
    environment = "SANDBOX"

    def _blocked(self) -> AppException:
        return AppException(
            "Certified PSP/acquirer is not configured. "
            "Terminal sessions use mock_sandbox only. "
            "Do not claim live Visa/Mastercard acquiring until a licensed adapter "
            "and credentials are provisioned.",
            status_code=503,
        )

    def authorize(
        self,
        *,
        session_id: str,
        amount_minor: int,
        currency: str,
        sandbox_outcome: str = "capture",
        payment_method_token: str = "pm_test_visa_success",
        scenario: str | None = None,
    ) -> ProcessorResult:
        raise self._blocked()

    def capture(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise self._blocked()

    def void_transaction(self, *, session_id: str, processor_reference: str) -> ProcessorResult:
        raise self._blocked()

    def refund(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise self._blocked()

    def complete_authorization(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise self._blocked()

    def get_transaction_status(self, processor_reference: str) -> ProcessorResult:
        raise self._blocked()
