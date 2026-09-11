"""Validated transaction status transitions for POS / payment flows."""

from __future__ import annotations

from app.core.enums import TransactionStatus
from app.exceptions.base import AppException

# Canonical POS-oriented transitions. Settlement states remain allowed after capture.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    TransactionStatus.PENDING: frozenset(
        {
            TransactionStatus.PROCESSING,
            TransactionStatus.CANCELLED,
        }
    ),
    TransactionStatus.PROCESSING: frozenset(
        {
            TransactionStatus.AUTHORIZED,
            TransactionStatus.CAPTURED,
            TransactionStatus.FAILED,
            TransactionStatus.CANCELLED,
        }
    ),
    TransactionStatus.AUTHORIZED: frozenset(
        {
            TransactionStatus.CAPTURED,
            TransactionStatus.FAILED,
            TransactionStatus.CANCELLED,
        }
    ),
    TransactionStatus.CAPTURED: frozenset(
        {
            TransactionStatus.SUCCESS,
            TransactionStatus.SETTLEMENT_PENDING,
            TransactionStatus.SETTLEMENT_PROCESSING,
            TransactionStatus.COMPLETED,
            TransactionStatus.REFUNDED,
            TransactionStatus.CANCELLED,
        }
    ),
    TransactionStatus.SUCCESS: frozenset(
        {
            TransactionStatus.SETTLEMENT_PENDING,
            TransactionStatus.SETTLEMENT_PROCESSING,
            TransactionStatus.COMPLETED,
            TransactionStatus.REFUNDED,
        }
    ),
    TransactionStatus.SETTLEMENT_PENDING: frozenset(
        {
            TransactionStatus.SETTLEMENT_PROCESSING,
            TransactionStatus.SETTLEMENT_COMPLETE,
            TransactionStatus.COMPLETED,
            TransactionStatus.MANUAL_REVIEW,
            TransactionStatus.REFUNDED,
        }
    ),
    TransactionStatus.SETTLEMENT_PROCESSING: frozenset(
        {
            TransactionStatus.SETTLEMENT_COMPLETE,
            TransactionStatus.COMPLETED,
            TransactionStatus.MANUAL_REVIEW,
            TransactionStatus.FAILED,
        }
    ),
    TransactionStatus.SETTLEMENT_COMPLETE: frozenset(
        {
            TransactionStatus.COMPLETED,
            TransactionStatus.REFUNDED,
        }
    ),
    TransactionStatus.COMPLETED: frozenset({TransactionStatus.REFUNDED}),
    TransactionStatus.FAILED: frozenset(),
    TransactionStatus.CANCELLED: frozenset(),
    TransactionStatus.REFUNDED: frozenset(),
    TransactionStatus.EXPIRED: frozenset(),
    TransactionStatus.MANUAL_REVIEW: frozenset(
        {
            TransactionStatus.SETTLEMENT_PROCESSING,
            TransactionStatus.COMPLETED,
            TransactionStatus.REFUNDED,
        }
    ),
}


def assert_transition(from_status: str | None, to_status: str) -> None:
    """Raise if moving from_status → to_status is not allowed."""
    if from_status is None:
        if to_status not in {
            TransactionStatus.PENDING,
            TransactionStatus.PROCESSING,
        }:
            raise AppException(
                f"Invalid initial status '{to_status}'",
                status_code=409,
            )
        return

    allowed = ALLOWED_TRANSITIONS.get(from_status, frozenset())
    if to_status not in allowed:
        raise AppException(
            f"Invalid status transition: {from_status} → {to_status}",
            status_code=409,
        )
