"""Terminal POS UI state machine (Android Phase 2 parity).

Separate from settlement TransactionStatus — used for smart-POS session flow.
Does not authorize real cards.
"""

from __future__ import annotations

from app.exceptions.base import AppException

# Mirrors Android TerminalTransactionState
CREATED = "CREATED"
AMOUNT_ENTERED = "AMOUNT_ENTERED"
PROTOCOL_SELECTED = "PROTOCOL_SELECTED"
CARD_PRESENTED = "CARD_PRESENTED"
CARD_DATA_READ = "CARD_DATA_READ"
AUTHORIZING = "AUTHORIZING"
APPROVED = "APPROVED"
DECLINED = "DECLINED"
CAPTURED = "CAPTURED"
COMPLETED = "COMPLETED"
VOIDED = "VOIDED"
REFUNDED = "REFUNDED"
CANCELLED = "CANCELLED"
FAILED = "FAILED"

ALLOWED_TERMINAL_TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED: frozenset({AMOUNT_ENTERED, CANCELLED}),
    AMOUNT_ENTERED: frozenset({PROTOCOL_SELECTED, CANCELLED}),
    PROTOCOL_SELECTED: frozenset({CARD_PRESENTED, CANCELLED}),
    CARD_PRESENTED: frozenset({CARD_DATA_READ, AUTHORIZING, CANCELLED, FAILED}),
    CARD_DATA_READ: frozenset({AUTHORIZING, CANCELLED, FAILED}),
    AUTHORIZING: frozenset({APPROVED, DECLINED, FAILED, CANCELLED}),
    APPROVED: frozenset({CAPTURED, COMPLETED, VOIDED, CANCELLED}),
    CAPTURED: frozenset({COMPLETED, REFUNDED, VOIDED}),
    COMPLETED: frozenset({REFUNDED}),
    DECLINED: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
    VOIDED: frozenset(),
    REFUNDED: frozenset(),
}


def can_terminal_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TERMINAL_TRANSITIONS.get(from_status, frozenset())


def assert_terminal_transition(from_status: str, to_status: str) -> None:
    if not can_terminal_transition(from_status, to_status):
        raise AppException(
            f"Invalid terminal transition: {from_status} → {to_status}",
            status_code=409,
        )


def transition(from_status: str, to_status: str) -> str:
    assert_terminal_transition(from_status, to_status)
    return to_status
