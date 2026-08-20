from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.auth import APIModel


class MerchantCreate(BaseModel):
    company_name: str = Field(min_length=2, max_length=255)
    commercial_registration: str | None = None
    tax_number: str | None = None
    country: str = Field(default="SA", min_length=2, max_length=2)
    city: str = Field(min_length=2, max_length=100)
    address: str = Field(min_length=5)
    website: str | None = None
    email: EmailStr
    phone: str = Field(min_length=8, max_length=32)
    industry: str | None = None


class MerchantOut(APIModel):
    id: UUID
    company_name: str
    commercial_registration: str | None
    tax_number: str | None
    country: str
    city: str
    address: str
    website: str | None
    email: EmailStr
    phone: str
    industry: str | None
    status: str
    created_at: datetime


class WalletCreate(BaseModel):
    wallet_address: str = Field(min_length=20, max_length=128)
    wallet_provider: str = "self_custody"
    wallet_network: str = Field(default="trc20", max_length=32)
    is_primary: bool = True


class WalletOut(APIModel):
    id: UUID
    merchant_id: UUID
    wallet_address: str
    wallet_provider: str
    wallet_network: str
    wallet_status: str
    is_primary: bool
    created_at: datetime
