"""Versioned merchant-fee math. Decimal only — never float.

Does not imply authorization, capture, settlement, or payout.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class FeeResult:
    gross_amount: Decimal
    fee_percent: Decimal
    fee_amount: Decimal
    net_amount: Decimal
    currency: str
    policy_version: str


def calculate_fee(
    gross_amount: Decimal,
    currency: str,
    fee_percent: Decimal,
    *,
    fixed_fee: Decimal = Decimal("0.00"),
    policy_version: str = "sandbox-v1",
) -> FeeResult:
    if gross_amount < 0:
        raise ValueError("gross_amount must be >= 0")
    if fee_percent < 0:
        raise ValueError("fee_percent must be >= 0")
    quant = Decimal("0.01")
    gross = gross_amount.quantize(quant, rounding=ROUND_HALF_UP)
    percent = fee_percent.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    variable = (gross * percent / Decimal("100")).quantize(quant, rounding=ROUND_HALF_UP)
    fixed = fixed_fee.quantize(quant, rounding=ROUND_HALF_UP)
    fee = (variable + fixed).quantize(quant, rounding=ROUND_HALF_UP)
    net = (gross - fee).quantize(quant, rounding=ROUND_HALF_UP)
    return FeeResult(
        gross_amount=gross,
        fee_percent=percent,
        fee_amount=fee,
        net_amount=net,
        currency=currency.upper(),
        policy_version=policy_version,
    )
