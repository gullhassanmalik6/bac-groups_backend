"""Sandbox MockPaymentProcessor — full authorize/capture/void/refund surface.

Never moves real money. Auth codes are TEST- prefixed.
"""

from __future__ import annotations

from uuid import uuid4

from app.payments.terminal_state_machine import (
    AMOUNT_ENTERED,
    APPROVED,
    AUTHORIZING,
    CANCELLED,
    CAPTURED,
    CARD_PRESENTED,
    COMPLETED,
    CREATED,
    DECLINED,
    FAILED,
    PROTOCOL_SELECTED,
    transition,
)
from app.processors.base import PaymentProcessor, ProcessorResult

# Re-export for existing imports.
__all__ = [
    "MockPaymentProcessor",
    "ProcessorResult",
    "get_mock_processor",
    "simulate_terminal_authorize_flow",
]


class MockPaymentProcessor(PaymentProcessor):
    name = "mock_sandbox"
    is_sandbox = True
    environment = "SANDBOX"

    def __init__(self) -> None:
        self._store: dict[str, ProcessorResult] = {}

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
        if not payment_method_token.startswith("pm_"):
            raise ValueError("token required — never send raw PAN/CVV")
        scenario = scenario or self._resolve_scenario(amount_minor, payment_method_token, sandbox_outcome)
        ref = f"sbx_{uuid4().hex[:16]}"
        if scenario == "declined":
            result = ProcessorResult(
                session_id, amount_minor, currency, "DECLINED", None, ref, message="Sandbox declined"
            )
        elif scenario == "timeout":
            result = ProcessorResult(
                session_id, amount_minor, currency, "TIMEOUT", None, ref, message="Sandbox timeout"
            )
        elif scenario == "error":
            result = ProcessorResult(
                session_id, amount_minor, currency, "ERROR", None, ref, message="Sandbox processor error"
            )
        elif scenario == "cancelled":
            result = ProcessorResult(
                session_id, amount_minor, currency, "CANCELLED", None, ref, message="Sandbox cancelled"
            )
        elif scenario == "signature" or sandbox_outcome == "signature":
            result = ProcessorResult(
                session_id,
                amount_minor,
                currency,
                "APPROVED",
                f"TEST-{uuid4().hex[:6].upper()}",
                ref,
                signature_required=True,
                message="Approved — signature required (SANDBOX)",
            )
        else:
            result = ProcessorResult(
                session_id,
                amount_minor,
                currency,
                "APPROVED",
                f"TEST-{uuid4().hex[:6].upper()}",
                ref,
                message="Approved (SANDBOX)",
            )
        self._store[ref] = result
        return result

    def capture(self, *, session_id: str, processor_reference: str, amount_minor: int, currency: str) -> ProcessorResult:
        prior = self._store.get(processor_reference)
        if prior is None:
            raise KeyError("Unknown processor reference")
        if prior.status != "APPROVED":
            raise ValueError(f"Cannot capture from status {prior.status}")
        result = ProcessorResult(
            session_id,
            amount_minor,
            currency,
            "APPROVED",
            prior.authorization_code or f"TEST-{uuid4().hex[:6].upper()}",
            processor_reference,
            message="Captured (SANDBOX)",
            card_brand=prior.card_brand,
            card_last4=prior.card_last4,
        )
        self._store[processor_reference] = result
        return result

    def void_transaction(self, *, session_id: str, processor_reference: str) -> ProcessorResult:
        prior = self._store.get(processor_reference)
        if prior is None:
            raise KeyError("Unknown processor reference")
        result = ProcessorResult(
            session_id,
            prior.amount_minor,
            prior.currency,
            "CANCELLED",
            prior.authorization_code,
            processor_reference,
            message="Voided (SANDBOX)",
            card_brand=prior.card_brand,
            card_last4=prior.card_last4,
        )
        self._store[processor_reference] = result
        return result

    def refund(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        prior = self._store.get(processor_reference)
        if prior is None:
            raise KeyError("Unknown processor reference")
        ref = f"sbx_rf_{uuid4().hex[:12]}"
        result = ProcessorResult(
            session_id,
            amount_minor,
            currency,
            "APPROVED",
            f"TEST-{uuid4().hex[:6].upper()}",
            ref,
            message="Refunded (SANDBOX)",
            card_brand=prior.card_brand,
            card_last4=prior.card_last4,
        )
        self._store[ref] = result
        return result

    def complete_authorization(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        prior = self._store.get(processor_reference)
        if prior is None:
            raise KeyError("Unknown processor reference")
        result = ProcessorResult(
            session_id,
            amount_minor,
            currency,
            "APPROVED",
            prior.authorization_code or f"TEST-{uuid4().hex[:6].upper()}",
            processor_reference,
            message="Authorization completed (SANDBOX)",
            card_brand=prior.card_brand,
            card_last4=prior.card_last4,
        )
        self._store[processor_reference] = result
        return result

    def get_transaction_status(self, processor_reference: str) -> ProcessorResult:
        prior = self._store.get(processor_reference)
        if prior is None:
            raise KeyError("Unknown processor reference")
        return prior

    def _resolve_scenario(self, amount_minor: int, token: str, outcome: str) -> str:
        if "declined" in token:
            return "declined"
        if "timeout" in token:
            return "timeout"
        if "error" in token:
            return "error"
        if amount_minor % 100 == 13:
            return "declined"
        if amount_minor % 100 == 99:
            return "timeout"
        if amount_minor % 100 == 77:
            return "error"
        if outcome == "signature":
            return "signature"
        return "success"


def simulate_terminal_authorize_flow(
    *,
    amount_minor: int = 1000,
    currency: str = "CAD",
    sandbox_outcome: str = "capture",
    scenario: str | None = None,
) -> tuple[str, ProcessorResult]:
    """Drive terminal SM + mock authorize for unit tests."""
    processor = MockPaymentProcessor()
    state = CREATED
    state = transition(state, AMOUNT_ENTERED)
    state = transition(state, PROTOCOL_SELECTED)
    state = transition(state, CARD_PRESENTED)
    state = transition(state, AUTHORIZING)
    result = processor.authorize(
        session_id="test-session",
        amount_minor=amount_minor,
        currency=currency,
        sandbox_outcome=sandbox_outcome,
        scenario=scenario,
    )
    if result.status == "APPROVED":
        state = transition(state, APPROVED)
        if sandbox_outcome in {"capture", "force_post"}:
            state = transition(state, CAPTURED)
            state = transition(state, COMPLETED)
        elif sandbox_outcome == "completion":
            state = transition(state, COMPLETED)
    elif result.status == "DECLINED":
        state = transition(state, DECLINED)
    elif result.status in {"TIMEOUT", "ERROR"}:
        state = transition(state, FAILED)
    elif result.status == "CANCELLED":
        state = transition(state, CANCELLED)
    return state, result


def get_mock_processor() -> PaymentProcessor:
    """Prefer ``app.processors.factory.get_payment_processor`` for new code."""
    from app.processors.factory import get_payment_processor

    return get_payment_processor("mock_sandbox")
