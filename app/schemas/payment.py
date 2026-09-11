from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.auth import APIModel


class CreatePaymentRequest(BaseModel):
    """Create a payment. Prefer amount_minor; amount is accepted for backward compatibility."""

    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    amount_minor: int | None = Field(default=None, gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    merchant_reference: str = Field(min_length=3, max_length=128)
    description: str | None = Field(default=None, max_length=255)
    gateway_provider: str | None = None
    # Idempotency: same key returns existing result instead of double-charging.
    idempotency_key: str | None = Field(default=None, max_length=128)
    # Safe processor token only — never send PAN/CVV.
    payment_method_token: str | None = Field(default=None, max_length=128)
    payment_mode: Literal["online", "offline_test"] = "online"
    protocol_code: str | None = Field(default=None, max_length=32)
    sandbox_scenario: Literal["success", "declined", "signature"] | None = None

    @model_validator(mode="after")
    def require_amount(self) -> "CreatePaymentRequest":
        if self.amount is None and self.amount_minor is None:
            raise ValueError("Provide amount or amount_minor")
        if self.payment_method_token is not None:
            token = self.payment_method_token.strip()
            if not token.startswith("pm_"):
                raise ValueError("payment_method_token must be a tokenized pm_… value — never send PAN/CVV")
            self.payment_method_token = token
        return self


class RefundPaymentRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    reason: str | None = Field(default=None, max_length=255)


class CompleteSignatureRequest(BaseModel):
    """Signature artifact reference only — no card data."""

    signature_data_url: str | None = Field(default=None, max_length=200_000)
    acknowledged: bool = True


class SettlementOut(APIModel):
    id: UUID
    status: str
    usdt_amount: Decimal
    exchange_rate: Decimal
    exchange_provider: str
    wallet_network: str
    wallet_address: str
    blockchain_tx_hash: str | None
    confirmation_count: int
    retry_count: int


class ReceiptOut(APIModel):
    id: UUID
    receipt_number: str
    merchant_name: str
    amount: Decimal
    currency: str
    gateway: str | None
    status: str
    printable_payload: dict
    created_at: datetime


class PaymentOut(APIModel):
    id: UUID
    merchant_id: UUID
    amount: Decimal
    currency: str
    gateway_reference: str | None
    merchant_reference: str
    payment_method: str | None
    status: str
    payment_date: datetime | None
    fees: Decimal
    tax: Decimal
    net_amount: Decimal
    receipt_number: str | None
    failure_reason: str | None
    created_at: datetime
    settlement: SettlementOut | None = None
    receipt: ReceiptOut | None = None
    # POS extensions (from extra_data when present)
    signature_required: bool = False
    authorization_code: str | None = None
    payment_mode: str | None = None
    protocol_code: str | None = None
    card_last4: str | None = None
    amount_minor: int | None = None


class TransactionListOut(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int


class ProtocolOut(BaseModel):
    selection_id: str
    code: str
    name: str
    display_label: str
    description: str
    mode: str
    connectivity: str
    sandbox_outcome: str
    digit_group: int | None = None
    family: str
    version: str
    enabled: bool
    documented: bool = False
    sandbox_only: bool = True
    requires_online_authorization: bool = True
    authorization_mode: str = "sale"
    supported_transaction_types: list[str] = []
    allows_manual_entry: bool = True
    signature_likely: bool = False
    ui_environment_label: str = "Demo"


class SandboxTokenRequest(BaseModel):
    """Maps documented TEST card scenarios to a payment_method_token. Never stores PAN."""

    test_pan_hint: Literal["4111111111111111", "4000000000000002", "4111111111111111_sig"] = (
        "4111111111111111"
    )


class SandboxTokenOut(BaseModel):
    payment_method_token: str
    scenario: str
    card_last4: str
    notice: str = "TEST DATA ONLY — not a real card; never send real PANs to this API."
