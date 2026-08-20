from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


@dataclass(slots=True)
class WalletTransferRequest:
    to_address: str
    amount: Decimal
    network: str
    currency: str = "USDT"
    memo: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WalletTransferResult:
    success: bool
    tx_hash: str | None
    confirmation_count: int = 0
    raw_response: dict[str, Any] = field(default_factory=dict)
    error_message: str | None = None


class WalletProvider(ABC):
    network_name: str

    @abstractmethod
    async def validate_address(self, address: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def transfer(self, request: WalletTransferRequest) -> WalletTransferResult:
        raise NotImplementedError

    @abstractmethod
    async def get_transfer_status(self, tx_hash: str) -> WalletTransferResult:
        raise NotImplementedError
