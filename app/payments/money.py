"""Money helpers — prefer integer minor units over floats."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# ISO-4217 minor units (extend as needed).
CURRENCY_EXPONENTS: dict[str, int] = {
    "AED": 2,
    "CAD": 2,
    "EUR": 2,
    "GBP": 2,
    "SAR": 2,
    "USD": 2,
}


def currency_exponent(currency: str) -> int:
    code = currency.upper()
    if code not in CURRENCY_EXPONENTS:
        raise ValueError(f"Unsupported currency for minor-unit conversion: {code}")
    return CURRENCY_EXPONENTS[code]


def to_minor_units(amount: Decimal, currency: str) -> int:
    exp = currency_exponent(currency)
    quant = Decimal(10) ** exp
    normalized = amount.quantize(Decimal(1) / quant, rounding=ROUND_HALF_UP)
    return int(normalized * quant)


def from_minor_units(amount_minor: int, currency: str) -> Decimal:
    if amount_minor <= 0:
        raise ValueError("amount_minor must be > 0")
    exp = currency_exponent(currency)
    quant = Decimal(10) ** exp
    return (Decimal(amount_minor) / quant).quantize(Decimal(1) / quant)
