from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal


@dataclass(slots=True)
class ExchangeQuote:
    base_currency: str
    quote_currency: str
    buy_rate: Decimal
    sell_rate: Decimal
    provider: str


class ExchangeProvider(ABC):
    provider_name: str

    @abstractmethod
    async def get_rate(self, base_currency: str, quote_currency: str = "USDT") -> ExchangeQuote:
        raise NotImplementedError

    @abstractmethod
    async def convert(
        self, amount: Decimal, base_currency: str, quote_currency: str = "USDT"
    ) -> tuple[Decimal, ExchangeQuote]:
        raise NotImplementedError
