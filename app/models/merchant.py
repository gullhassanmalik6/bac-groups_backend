from datetime import datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import MerchantStatus, WalletStatus
from app.database.base import BaseModel
from app.database.types import JSONType, UUIDType

if TYPE_CHECKING:
    from app.models.payment import Transaction
    from app.models.user import User


class MerchantProfile(BaseModel):
    __tablename__ = "merchant_profiles"
    __table_args__ = (
        Index("ix_merchant_profiles_status", "status"),
        Index("ix_merchant_profiles_email", "email"),
    )

    owner_user_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("users.id"), unique=True, nullable=False
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    commercial_registration: Mapped[Optional[str]] = mapped_column(String(64), unique=True)
    tax_number: Mapped[Optional[str]] = mapped_column(String(64))
    country: Mapped[str] = mapped_column(String(2), default="SA", nullable=False)
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512))
    industry: Mapped[Optional[str]] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), default=MerchantStatus.PENDING, nullable=False)

    owner: Mapped["User"] = relationship("User", back_populates="merchant_profile")
    addresses: Mapped[list["MerchantAddress"]] = relationship(back_populates="merchant")
    wallets: Mapped[list["MerchantWallet"]] = relationship(back_populates="merchant")
    bank_accounts: Mapped[list["MerchantBankAccount"]] = relationship(back_populates="merchant")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="merchant"
    )
    devices: Mapped[list["SunmiDevice"]] = relationship(back_populates="merchant")


class MerchantAddress(BaseModel):
    __tablename__ = "merchant_addresses"

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(64), default="primary")
    line1: Mapped[str] = mapped_column(String(255), nullable=False)
    line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(32))
    country: Mapped[str] = mapped_column(String(2), default="SA", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    merchant: Mapped[MerchantProfile] = relationship(back_populates="addresses")


class MerchantWallet(BaseModel):
    __tablename__ = "merchant_wallets"
    __table_args__ = (
        Index("ix_merchant_wallets_address", "wallet_address"),
        UniqueConstraint(
            "merchant_id",
            "wallet_address",
            "wallet_network",
            name="uq_merchant_wallet_address_network",
        ),
    )

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    wallet_address: Mapped[str] = mapped_column(String(128), nullable=False)
    wallet_provider: Mapped[str] = mapped_column(String(64), default="self_custody")
    wallet_network: Mapped[str] = mapped_column(String(32), default="trc20", nullable=False)
    wallet_status: Mapped[str] = mapped_column(
        String(32), default=WalletStatus.ACTIVE, nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    merchant: Mapped[MerchantProfile] = relationship(back_populates="wallets")


class MerchantBankAccount(BaseModel):
    __tablename__ = "merchant_bank_accounts"
    __table_args__ = (Index("ix_merchant_bank_accounts_iban", "iban", unique=True),)

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    bank_name: Mapped[str] = mapped_column(String(128), nullable=False)
    account_holder: Mapped[str] = mapped_column(String(255), nullable=False)
    iban: Mapped[str] = mapped_column(String(64), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="SAR", nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    merchant: Mapped[MerchantProfile] = relationship(back_populates="bank_accounts")


class DeviceInformation(BaseModel):
    """Generic device inventory (non-Sunmi-specific metadata)."""

    __tablename__ = "device_information"
    __table_args__ = (
        Index("ix_device_information_merchant_id", "merchant_id"),
        Index("ix_device_information_external_id", "external_id", unique=True),
    )

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    sunmi_device_id: Mapped[Optional[UUID]] = mapped_column(
        UUIDType, ForeignKey("sunmi_devices.id", ondelete="SET NULL")
    )
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(64), default="Sunmi", nullable=False)
    model_name: Mapped[str] = mapped_column(String(64), nullable=False)
    os_name: Mapped[str] = mapped_column(String(32), default="Android", nullable=False)
    os_version: Mapped[Optional[str]] = mapped_column(String(32))
    app_version: Mapped[Optional[str]] = mapped_column(String(32))
    push_token: Mapped[Optional[str]] = mapped_column(String(512))
    last_ip: Mapped[Optional[str]] = mapped_column(String(64))
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONType)


class SunmiDevice(BaseModel):
    __tablename__ = "sunmi_devices"
    __table_args__ = (Index("ix_sunmi_devices_serial", "serial_number", unique=True),)

    merchant_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("merchant_profiles.id", ondelete="CASCADE"), nullable=False
    )
    serial_number: Mapped[str] = mapped_column(String(128), nullable=False)
    model: Mapped[str] = mapped_column(String(64), default="Sunmi V3")
    android_version: Mapped[Optional[str]] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    merchant: Mapped[MerchantProfile] = relationship(back_populates="devices")
    sessions: Mapped[list["DeviceSession"]] = relationship(back_populates="device")


class DeviceSession(BaseModel):
    __tablename__ = "device_sessions"
    __table_args__ = (Index("ix_device_sessions_device_user", "device_id", "user_id"),)

    device_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("sunmi_devices.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(
        UUIDType, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    ip_address: Mapped[Optional[str]] = mapped_column(String(64))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    logged_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    device: Mapped[SunmiDevice] = relationship(back_populates="sessions")
