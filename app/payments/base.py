from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class PaymentRequest:
    amount: Decimal
    currency: str
    merchant_reference: str
    description: str
    customer_email: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class PaymentResult:
    success: bool
    status: str
    gateway_reference: str
    payment_method: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


@dataclass(slots=True)
class RefundRequest:
    gateway_reference: str
    amount: Decimal
    currency: str
    reason: str | None = None


@dataclass(slots=True)
class RefundResult:
    success: bool
    status: str
    refund_reference: str
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class PaymentGateway(ABC):
    """Provider-agnostic payment gateway contract."""

    provider_name: str

    @abstractmethod
    async def charge(self, request: PaymentRequest) -> PaymentResult:
        raise NotImplementedError

    @abstractmethod
    async def refund(self, request: RefundRequest) -> RefundResult:
        raise NotImplementedError

    @abstractmethod
    async def verify_callback(self, headers: dict[str, str], payload: dict[str, Any]) -> PaymentResult:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, gateway_reference: str) -> PaymentResult:
        raise NotImplementedError
