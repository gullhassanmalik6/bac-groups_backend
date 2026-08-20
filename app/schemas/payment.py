from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.auth import APIModel


class CreatePaymentRequest(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="SAR", min_length=3, max_length=3)
    merchant_reference: str = Field(min_length=3, max_length=128)
    description: str | None = Field(default=None, max_length=255)
    gateway_provider: str | None = None


class RefundPaymentRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    reason: str | None = Field(default=None, max_length=255)


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


class TransactionListOut(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int
