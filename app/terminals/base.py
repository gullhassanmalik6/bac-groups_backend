"""Physical terminal abstraction — official SDK only when docs exist."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class TerminalPaymentRequest:
    amount_minor: int
    currency: str
    merchant_reference: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class TerminalPaymentResult:
    success: bool
    status: str
    terminal_reference: str
    error_message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class TerminalProvider(ABC):
    """
    Contract for a certified Android POS / SoftPOS SDK.

    Do NOT invent manufacturer commands. Implement adapters only from
    official Sunmi / acquirer documentation when supplied.
    """

    provider_name: str

    @abstractmethod
    async def initialize(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def connect(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def start_payment(self, request: TerminalPaymentRequest) -> TerminalPaymentResult:
        raise NotImplementedError

    @abstractmethod
    async def cancel_payment(self, terminal_reference: str) -> TerminalPaymentResult:
        raise NotImplementedError

    @abstractmethod
    async def get_status(self, terminal_reference: str) -> TerminalPaymentResult:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError
