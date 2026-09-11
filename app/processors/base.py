"""Card-present PaymentProcessor contract (terminal sessions).

Distinct from ``app.payments.base.PaymentGateway`` (legacy invoice / crypto charges).

Live Visa/Mastercard/Verifone wire formats are **not** implemented here.
Adapters must be supplied with official PSP/OEM documentation and credentials.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

ProcessorEnvironment = Literal["MOCK", "SANDBOX", "PRODUCTION"]


@dataclass
class ProcessorResult:
    transaction_id: str
    amount_minor: int
    currency: str
    status: str
    authorization_code: str | None
    processor_reference: str
    signature_required: bool = False
    message: str | None = None
    sandbox: bool = True
    card_brand: str | None = "VISA"
    card_last4: str | None = "1111"
    environment: ProcessorEnvironment = "SANDBOX"


class PaymentProcessor(ABC):
    """Authorize / capture / void / refund for terminal sessions."""

    name: str
    is_sandbox: bool
    environment: ProcessorEnvironment

    @abstractmethod
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
        raise NotImplementedError

    @abstractmethod
    def capture(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise NotImplementedError

    @abstractmethod
    def void_transaction(self, *, session_id: str, processor_reference: str) -> ProcessorResult:
        raise NotImplementedError

    @abstractmethod
    def refund(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise NotImplementedError

    @abstractmethod
    def complete_authorization(
        self,
        *,
        session_id: str,
        processor_reference: str,
        amount_minor: int,
        currency: str,
    ) -> ProcessorResult:
        raise NotImplementedError

    @abstractmethod
    def get_transaction_status(self, processor_reference: str) -> ProcessorResult:
        raise NotImplementedError

    def describe(self) -> dict[str, str | bool]:
        return {
            "name": self.name,
            "is_sandbox": self.is_sandbox,
            "environment": self.environment,
            "live_acquiring": False if self.is_sandbox else self.environment == "PRODUCTION",
        }
