from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateTerminalSessionRequest(BaseModel):
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    transaction_type: str = Field(default="SALE", max_length=32)
    protocol_code: str | None = Field(default=None, max_length=64)
    device_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class AuthorizeTerminalSessionRequest(BaseModel):
    payment_method_token: str = Field(default="pm_test_visa_success", max_length=128)
    scenario: str | None = Field(default=None, max_length=32)


class RefundTerminalSessionRequest(BaseModel):
    amount_minor: int | None = Field(default=None, gt=0)
    reason: str | None = Field(default=None, max_length=255)


class TerminalSessionOut(BaseModel):
    id: UUID
    state: str
    amount_minor: int
    currency: str
    transaction_type: str
    protocol_id: str | None = None
    protocol_code: str | None = None
    protocol_label: str | None = None
    sandbox_outcome: str | None = None
    environment: str = "SANDBOX"
    authorization_code: str | None = None
    processor_reference: str | None = None
    processor_status: str | None = None
    processor_message: str | None = None
    signature_required: bool = False
    card_brand: str | None = None
    card_last4: str | None = None
    device_id: UUID | None = None
    events: list[dict] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TerminalSessionListOut(BaseModel):
    items: list[TerminalSessionOut]
    total: int
