"""In-memory terminal session store (sandbox Phase 5).

Production persistence can replace this with a DB-backed repository later.
Sessions never store PAN/CVV.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import UUID, uuid4


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TerminalSessionRecord:
    id: UUID
    merchant_id: UUID
    user_id: UUID
    state: str
    amount_minor: int
    currency: str
    transaction_type: str
    protocol_id: str | None = None
    protocol_code: str | None = None
    protocol_label: str | None = None
    sandbox_outcome: str | None = None
    device_id: UUID | None = None
    idempotency_key: str | None = None
    environment: str = "SANDBOX"
    payment_method_token: str | None = None
    authorization_code: str | None = None
    processor_reference: str | None = None
    processor_status: str | None = None
    processor_message: str | None = None
    signature_required: bool = False
    card_brand: str | None = None
    card_last4: str | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def touch(self) -> None:
        self.updated_at = _utcnow()


class TerminalSessionStore:
    def __init__(self) -> None:
        self._lock = Lock()
        self._by_id: dict[UUID, TerminalSessionRecord] = {}
        self._by_idempotency: dict[str, UUID] = {}

    def create(self, record: TerminalSessionRecord) -> TerminalSessionRecord:
        with self._lock:
            if record.idempotency_key:
                existing_id = self._by_idempotency.get(f"{record.merchant_id}:{record.idempotency_key}")
                if existing_id and existing_id in self._by_id:
                    return self._by_id[existing_id]
                self._by_idempotency[f"{record.merchant_id}:{record.idempotency_key}"] = record.id
            self._by_id[record.id] = record
            return record

    def get(self, session_id: UUID) -> TerminalSessionRecord | None:
        with self._lock:
            return self._by_id.get(session_id)

    def save(self, record: TerminalSessionRecord) -> TerminalSessionRecord:
        with self._lock:
            record.touch()
            self._by_id[record.id] = record
            return record

    def list_all(self, *, limit: int = 500) -> list[TerminalSessionRecord]:
        with self._lock:
            items = list(self._by_id.values())
            items.sort(key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    def list_for_merchant(
        self,
        merchant_id: UUID,
        *,
        limit: int = 100,
        status: str | None = None,
        protocol: str | None = None,
        currency: str | None = None,
    ) -> list[TerminalSessionRecord]:
        with self._lock:
            items = [r for r in self._by_id.values() if r.merchant_id == merchant_id]
            if status:
                status_u = status.upper()
                items = [r for r in items if r.state.upper() == status_u]
            if protocol:
                p = protocol.lower()
                items = [
                    r
                    for r in items
                    if (r.protocol_code or "").lower().find(p) >= 0
                    or (r.protocol_id or "").lower().find(p) >= 0
                    or (r.protocol_label or "").lower().find(p) >= 0
                ]
            if currency:
                items = [r for r in items if r.currency.upper() == currency.upper()]
            items.sort(key=lambda r: r.created_at, reverse=True)
            return items[:limit]

    def clear(self) -> None:
        with self._lock:
            self._by_id.clear()
            self._by_idempotency.clear()


_store = TerminalSessionStore()


def get_terminal_session_store() -> TerminalSessionStore:
    return _store


def new_session_id() -> UUID:
    return uuid4()
