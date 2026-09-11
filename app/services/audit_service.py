"""PCI-conscious audit logging — never record PAN/CVV/passwords."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.website import AuditLog

# Keys that must never appear in audit details.
_SENSITIVE_KEYS = frozenset(
    {
        "pan",
        "card_number",
        "cardnumber",
        "cvv",
        "cvc",
        "cvv2",
        "security_code",
        "track",
        "track2",
        "magnetic_stripe",
        "pin",
        "password",
        "secret",
        "access_token",
        "refresh_token",
        "authorization",
    }
)

_PAN_LIKE = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_CVV_LIKE = re.compile(r"(?i)\b(?:cvv|cvc)\s*[:=]?\s*\d{3,4}\b")


def _scrub_string(value: str) -> str:
    cleaned = _CVV_LIKE.sub("[REDACTED_CVV]", value)
    # Keep masked ****1234; scrub long digit runs that look like PAN.
    without_masked = re.sub(r"\*+\d{2,4}", "", cleaned)
    if _PAN_LIKE.search(without_masked):
        return _PAN_LIKE.sub("[REDACTED_PAN]", cleaned)
    return cleaned


def sanitize_metadata(data: dict[str, Any] | None) -> dict[str, Any]:
    if not data:
        return {}
    clean: dict[str, Any] = {}
    for key, value in data.items():
        lowered = key.lower()
        if lowered in _SENSITIVE_KEYS or "cvv" in lowered or "pan" in lowered:
            continue
        if isinstance(value, dict):
            clean[key] = sanitize_metadata(value)
        elif isinstance(value, str):
            clean[key] = _scrub_string(value)
        else:
            clean[key] = value
    return clean


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def record(
        self,
        *,
        action: str,
        resource_type: str,
        resource_id: str | None = None,
        actor_user_id: UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            user_agent=user_agent,
            details=sanitize_metadata(details),
        )
        self.session.add(entry)
        await self.session.flush()
        return entry
