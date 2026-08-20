from datetime import datetime
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import SettlementStatus, TransactionStatus
from app.database.base import BaseModel
from app.database.types import JSONType, UUIDType


class PaymentGateway(BaseModel):
    __tablename__ = "payment_gateways"
    __table_args__ = (
        Index("ix_payment_gateways_provider_status", "provider", "status"),
    )

    gateway_name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="SA")
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(512))
    sandbox_endpoint: Mapped[Optional[str]] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    supports_refund: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    supports_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    credentials: Mapped[list["GatewayCredential"]] = relationship(back_populates="gateway")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="gateway")


class GatewayCredential(BaseModel):
    __tablename__ = "gateway_credentials"
    __table_args__ = (
        Index("ix_gateway_credentials_merchant_gateway", "merchant_id", "gateway_id"),
    )

    gateway_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("payment_gateways.id", ondelete="CASCADE"), nullable=False
    )
    merchant_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE")
    )
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    environment: Mapped[str] = mapped_column(String(16), default="sandbox", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    gateway: Mapped[PaymentGateway] = relationship(back_populates="credentials")


class PaymentMethod(BaseModel):
    __tablename__ = "payment_methods"

    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class Transaction(BaseModel):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_transactions_merchant_id", "merchant_id"),
        Index("ix_transactions_status", "status"),
        Index("ix_transactions_gateway_reference", "gateway_reference"),
        Index("ix_transactions_merchant_reference", "merchant_reference"),
        Index("ix_transactions_receipt_number", "receipt_number"),
        Index("ix_transactions_payment_date", "payment_date"),
        Index("ix_transactions_merchant_status_date", "merchant_id", "status", "payment_date"),
        UniqueConstraint("merchant_id", "merchant_reference", name="uq_transactions_merchant_ref"),
        CheckConstraint("amount > 0", name="amount_positive"),
        CheckConstraint("fees >= 0", name="fees_non_negative"),
        CheckConstraint("tax >= 0", name="tax_non_negative"),
    )

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id"), nullable=False
    )
    gateway_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("payment_gateways.id")
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="SAR", nullable=False)
    gateway_reference: Mapped[Optional[str]] = mapped_column(String(128))
    merchant_reference: Mapped[str] = mapped_column(String(128), nullable=False)
    payment_method: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(
        String(32), default=TransactionStatus.PENDING, nullable=False
    )
    payment_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    tax: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0.00"), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), default=Decimal("0.00"), nullable=False
    )
    receipt_number: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)

    merchant = relationship("MerchantProfile", back_populates="transactions")
    gateway: Mapped[Optional[PaymentGateway]] = relationship(back_populates="transactions")
    items: Mapped[list["TransactionItem"]] = relationship(back_populates="transaction")
    status_logs: Mapped[list["TransactionStatusLog"]] = relationship(back_populates="transaction")
    payment_attempts: Mapped[list["PaymentAttempt"]] = relationship(back_populates="transaction")
    receipt: Mapped[Optional["Receipt"]] = relationship(back_populates="transaction", uselist=False)
    settlement: Mapped[Optional["CryptoSettlement"]] = relationship(
        back_populates="transaction", uselist=False
    )


class TransactionItem(BaseModel):
    __tablename__ = "transaction_items"
    __table_args__ = (CheckConstraint("quantity > 0", name="quantity_positive"),)

    transaction_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="items")


class TransactionStatusLog(BaseModel):
    __tablename__ = "transaction_status_logs"
    __table_args__ = (Index("ix_transaction_status_logs_transaction_id", "transaction_id"),)

    transaction_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[Optional[str]] = mapped_column(Text)
    actor: Mapped[Optional[str]] = mapped_column(String(64))

    transaction: Mapped[Transaction] = relationship(back_populates="status_logs")


class PaymentAttempt(BaseModel):
    __tablename__ = "payment_attempts"
    __table_args__ = (Index("ix_payment_attempts_transaction_id", "transaction_id"),)

    transaction_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False
    )
    gateway_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    gateway_response: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    transaction: Mapped[Transaction] = relationship(back_populates="payment_attempts")


class PaymentCallback(BaseModel):
    __tablename__ = "payment_callbacks"
    __table_args__ = (
        Index("ix_payment_callbacks_gateway_processed", "gateway_provider", "processed"),
    )

    gateway_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="SET NULL")
    )
    headers: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    response: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Receipt(BaseModel):
    __tablename__ = "receipts"
    __table_args__ = (
        UniqueConstraint("receipt_number", name="uq_receipts_receipt_number"),
        Index("ix_receipts_transaction_id", "transaction_id"),
    )

    transaction_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    receipt_number: Mapped[str] = mapped_column(String(64), nullable=False)
    merchant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    gateway: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    printable_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)

    transaction: Mapped[Transaction] = relationship(back_populates="receipt")


class CryptoWallet(BaseModel):
    """Platform / treasury wallets used by settlement operations (not merchant wallets)."""

    __tablename__ = "crypto_wallets"
    __table_args__ = (
        Index("ix_crypto_wallets_address", "wallet_address"),
        Index("ix_crypto_wallets_network_status", "network", "status"),
        UniqueConstraint("wallet_address", "network", name="uq_crypto_wallets_address_network"),
    )

    label: Mapped[str] = mapped_column(String(128), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(128), nullable=False)
    network: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), default="USDT", nullable=False)
    provider: Mapped[str] = mapped_column(String(64), default="self_custody", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_hot_wallet: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    extra_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)


class CryptoExchange(BaseModel):
    __tablename__ = "crypto_exchanges"

    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)


class ExchangeRate(BaseModel):
    __tablename__ = "exchange_rates"
    __table_args__ = (
        Index(
            "ix_exchange_rates_pair_provider",
            "base_currency",
            "quote_currency",
            "provider",
        ),
        Index("ix_exchange_rates_captured_at", "captured_at"),
    )

    base_currency: Mapped[str] = mapped_column(String(16), nullable=False)
    quote_currency: Mapped[str] = mapped_column(String(16), default="USDT", nullable=False)
    buy_rate: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    sell_rate: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CryptoSettlement(BaseModel):
    __tablename__ = "crypto_settlements"
    __table_args__ = (
        Index("ix_crypto_settlements_status", "status"),
        Index("ix_crypto_settlements_tx_hash", "blockchain_tx_hash"),
        CheckConstraint("usdt_amount > 0", name="usdt_amount_positive"),
    )

    transaction_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("transactions.id", ondelete="CASCADE"), unique=True
    )
    merchant_wallet_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_wallets.id"), nullable=False
    )
    source_crypto_wallet_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("crypto_wallets.id", ondelete="SET NULL")
    )
    fiat_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    fiat_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    usdt_amount: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    exchange_rate: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    exchange_provider: Mapped[str] = mapped_column(String(64), nullable=False)
    wallet_network: Mapped[str] = mapped_column(String(32), nullable=False)
    wallet_address: Mapped[str] = mapped_column(String(128), nullable=False)
    blockchain_tx_hash: Mapped[Optional[str]] = mapped_column(String(128))
    confirmation_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default=SettlementStatus.PENDING, nullable=False
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(Text)

    transaction: Mapped[Transaction] = relationship(back_populates="settlement")
    transfer_logs: Mapped[list["CryptoTransferLog"]] = relationship(back_populates="settlement")


class CryptoTransferLog(BaseModel):
    __tablename__ = "crypto_transfer_logs"
    __table_args__ = (Index("ix_crypto_transfer_logs_settlement_id", "settlement_id"),)

    settlement_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("crypto_settlements.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONType)
    message: Mapped[Optional[str]] = mapped_column(Text)

    settlement: Mapped[CryptoSettlement] = relationship(back_populates="transfer_logs")
