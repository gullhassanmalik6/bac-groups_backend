from decimal import Decimal, ROUND_HALF_UP

from app.crypto.base import ExchangeProvider, ExchangeQuote

# Approximate sandbox FX table (fiat -> USDT). Replace via live adapters in production.
_SANDBOX_RATES: dict[str, Decimal] = {
    "SAR": Decimal("0.2667"),
    "USD": Decimal("1.0000"),
    "AED": Decimal("0.2723"),
    "EUR": Decimal("1.0800"),
}


class SandboxExchangeProvider(ExchangeProvider):
    provider_name = "sandbox"

    async def get_rate(self, base_currency: str, quote_currency: str = "USDT") -> ExchangeQuote:
        base = base_currency.upper()
        quote = quote_currency.upper()
        if quote != "USDT":
            raise ValueError(f"Sandbox exchange only supports USDT quotes, got {quote}")
        rate = _SANDBOX_RATES.get(base)
        if rate is None:
            raise ValueError(f"Unsupported sandbox currency: {base}")
        return ExchangeQuote(
            base_currency=base,
            quote_currency=quote,
            buy_rate=rate,
            sell_rate=rate,
            provider=self.provider_name,
        )

    async def convert(
        self, amount: Decimal, base_currency: str, quote_currency: str = "USDT"
    ) -> tuple[Decimal, ExchangeQuote]:
        quote = await self.get_rate(base_currency, quote_currency)
        converted = (amount * quote.sell_rate).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
        return converted, quote
