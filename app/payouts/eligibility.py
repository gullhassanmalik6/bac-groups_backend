"""Payout eligibility — never marks payout confirmed without a provider result."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

PayoutEligibility = Literal[
    "PAYOUT_NOT_ELIGIBLE",
    "PAYOUT_PENDING",
    "PAYOUT_ON_HOLD",
    "PAYOUT_REQUIRES_REVIEW",
]


@dataclass(frozen=True, slots=True)
class PayoutEligibilityResult:
    status: PayoutEligibility
    reason: str
    network: str = "TRC20"
    destination_masked: str | None = None
    amount: Decimal | None = None
    currency: str | None = None
    provider_configured: bool = False


def evaluate_payout_eligibility(
    *,
    settlement_confirmed: bool,
    provider_configured: bool,
    destination_address: str | None,
    amount: Decimal | None = None,
    currency: str | None = None,
) -> PayoutEligibilityResult:
    masked = _mask_tron(destination_address)
    if not settlement_confirmed:
        return PayoutEligibilityResult(
            status="PAYOUT_NOT_ELIGIBLE",
            reason="Settlement is not confirmed by a licensed processor/acquirer.",
            destination_masked=masked,
            amount=amount,
            currency=currency,
            provider_configured=provider_configured,
        )
    if not provider_configured:
        return PayoutEligibilityResult(
            status="PAYOUT_NOT_ELIGIBLE",
            reason="No payout provider is configured. Do not broadcast TRC20 from the POS.",
            destination_masked=masked,
            amount=amount,
            currency=currency,
            provider_configured=False,
        )
    if not destination_address or not destination_address.startswith("T") or not (
        30 <= len(destination_address) <= 42
    ):
        return PayoutEligibilityResult(
            status="PAYOUT_REQUIRES_REVIEW",
            reason="Destination TRON address is missing or invalid.",
            destination_masked=masked,
            amount=amount,
            currency=currency,
            provider_configured=True,
        )
    return PayoutEligibilityResult(
        status="PAYOUT_PENDING",
        reason="Eligible for payout provider submission — awaiting provider confirmation. Not confirmed on-chain.",
        destination_masked=masked,
        amount=amount,
        currency=currency,
        provider_configured=True,
    )


def _mask_tron(address: str | None) -> str | None:
    if not address or len(address) < 10:
        return None
    return f"{address[:5]}••••{address[-4:]}"
