"""Seed roles, sandbox gateway, and website CMS content."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.enums import UserRole
from app.core.security import hash_password
from app.database.session import AsyncSessionLocal
from app.models.payment import CryptoExchange, CryptoWallet, PaymentGateway, PaymentMethod
from app.models.user import Role, User
from app.models.website import (
    Country,
    Currency,
    Faq,
    Language,
    Testimonial,
    WebsiteProject,
    WebsiteService,
)


async def seed() -> None:
    async with AsyncSessionLocal() as session:
        for name, description in [
            (UserRole.SUPER_ADMIN, "Full platform access"),
            (UserRole.ADMIN, "Operations admin"),
            (UserRole.MERCHANT_OWNER, "Merchant owner"),
            (UserRole.MERCHANT_STAFF, "Merchant staff"),
            (UserRole.SUPPORT, "Support agent"),
        ]:
            exists = await session.scalar(select(Role).where(Role.name == name))
            if not exists:
                session.add(Role(name=name, description=description))

        await session.flush()

        gateway = await session.scalar(
            select(PaymentGateway).where(PaymentGateway.provider == "sandbox")
        )
        if not gateway:
            session.add(
                PaymentGateway(
                    gateway_name="CryptoPOS Sandbox",
                    provider="sandbox",
                    country="SA",
                    api_endpoint="https://sandbox.cryptopos.local/charge",
                    sandbox_endpoint="https://sandbox.cryptopos.local/charge",
                    status="active",
                    supports_refund=True,
                    supports_recurring=False,
                )
            )

        nowpayments = await session.scalar(
            select(PaymentGateway).where(PaymentGateway.provider == "nowpayments")
        )
        if not nowpayments:
            session.add(
                PaymentGateway(
                    gateway_name="NOWPayments",
                    provider="nowpayments",
                    country="SA",
                    api_endpoint="https://api.nowpayments.io/v1",
                    sandbox_endpoint="https://api.nowpayments.io/v1",
                    status="active",
                    supports_refund=False,
                    supports_recurring=False,
                )
            )

        moyasar = await session.scalar(
            select(PaymentGateway).where(PaymentGateway.provider == "moyasar")
        )
        if not moyasar:
            session.add(
                PaymentGateway(
                    gateway_name="Moyasar",
                    provider="moyasar",
                    country="SA",
                    api_endpoint="https://api.moyasar.com/v1",
                    sandbox_endpoint="https://api.moyasar.com/v1",
                    status="active",
                    supports_refund=True,
                    supports_recurring=False,
                )
            )

        for code, display in [
            ("visa", "Visa"),
            ("mastercard", "Mastercard"),
            ("amex", "American Express"),
            ("apple_pay", "Apple Pay"),
            ("google_pay", "Google Pay"),
        ]:
            method = await session.scalar(select(PaymentMethod).where(PaymentMethod.code == code))
            if not method:
                session.add(PaymentMethod(code=code, display_name=display, is_active=True))

        for code, name in [("SA", "Saudi Arabia"), ("AE", "United Arab Emirates"), ("US", "United States")]:
            if not await session.scalar(select(Country).where(Country.code == code)):
                session.add(Country(code=code, name=name, is_active=True))

        for code, name, symbol in [
            ("SAR", "Saudi Riyal", "﷼"),
            ("USD", "US Dollar", "$"),
            ("EUR", "Euro", "€"),
            ("AED", "UAE Dirham", "د.إ"),
            ("USDT", "Tether", "USDT"),
        ]:
            if not await session.scalar(select(Currency).where(Currency.code == code)):
                session.add(Currency(code=code, name=name, symbol=symbol, is_active=True))

        for code, name in [("en", "English"), ("ar", "Arabic")]:
            if not await session.scalar(select(Language).where(Language.code == code)):
                session.add(Language(code=code, name=name, is_active=True))

        if not await session.scalar(select(CryptoExchange).where(CryptoExchange.provider == "sandbox")):
            session.add(
                CryptoExchange(name="Sandbox Exchange", provider="sandbox", status="active")
            )

        if not await session.scalar(select(CryptoWallet).limit(1)):
            session.add(
                CryptoWallet(
                    label="Treasury Hot Wallet TRC20",
                    wallet_address="PENDING_PLATFORM_TRC20_SANDBOX",
                    network="trc20",
                    currency="USDT",
                    provider="sandbox",
                    status="inactive",
                    is_hot_wallet=True,
                )
            )

        admin_role = await session.scalar(select(Role).where(Role.name == UserRole.SUPER_ADMIN))
        admin = await session.scalar(select(User).where(User.email == "admin@cryptopos.com"))
        if admin_role and not admin:
            session.add(
                User(
                    first_name="Platform",
                    last_name="Admin",
                    email="admin@cryptopos.com",
                    phone="+966500000001",
                    password_hash=hash_password("ChangeMeNow!123"),
                    role_id=admin_role.id,
                    role_code=UserRole.SUPER_ADMIN,
                    is_active=True,
                    is_verified=True,
                )
            )

        merchant_role = await session.scalar(select(Role).where(Role.name == UserRole.MERCHANT_OWNER))
        merchant_user = await session.scalar(select(User).where(User.email == "turki.hejaili@gmail.com"))
        if merchant_role and not merchant_user:
            from app.core.enums import MerchantStatus, WalletStatus
            from app.models.merchant import MerchantProfile, MerchantWallet

            merchant_user = User(
                first_name="Turki",
                last_name="Hejaili",
                email="turki.hejaili@gmail.com",
                phone="+966599000789",
                password_hash=hash_password("ChangeMeOnFirstLogin!123"),
                role_id=merchant_role.id,
                role_code=UserRole.MERCHANT_OWNER,
                is_active=True,
                is_verified=True,
            )
            session.add(merchant_user)
            await session.flush()
            profile = MerchantProfile(
                owner_user_id=merchant_user.id,
                company_name="Al Dour Al Aliah",
                commercial_registration=None,
                tax_number=None,
                country="SA",
                city="Madinah",
                address="Saudi Arabia – Madinah 42393",
                email="turki.hejaili@gmail.com",
                phone="+966599000789",
                industry="Construction",
                status=MerchantStatus.ACTIVE,
            )
            session.add(profile)
            await session.flush()
            session.add(
                MerchantWallet(
                    merchant_id=profile.id,
                    wallet_address="PENDING_CLIENT_TRC20_TRUST_WALLET",
                    wallet_provider="trust_wallet",
                    wallet_network="trc20",
                    wallet_status=WalletStatus.INACTIVE,
                    is_primary=True,
                )
            )

        if not await session.scalar(select(WebsiteService).limit(1)):
            session.add_all(
                [
                    WebsiteService(
                        slug="android-pos",
                        title="Android POS Terminals",
                        summary="Sunmi-ready enterprise POS built for high-volume merchant floors.",
                        description="Deploy CryptoPOS on Sunmi V3 and compatible Android terminals.",
                        icon="Smartphone",
                        features=["Sunmi V3 optimized", "Offline transaction queue"],
                        image_url="https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?auto=format&fit=crop&w=1600&q=80",
                        sort_order=1,
                    ),
                    WebsiteService(
                        slug="usdt-settlement",
                        title="USDT Settlement Engine",
                        summary="Automated settlement orchestration from card capture to wallet transfer.",
                        description="After successful card payment, CryptoPOS calculates fees, converts via exchange adapters, and prepares USDT transfer.",
                        icon="Wallet",
                        features=["Exchange abstraction", "Wallet adapters", "Retry queues"],
                        image_url="https://images.unsplash.com/photo-1621761191319-c6fb62004040?auto=format&fit=crop&w=1600&q=80",
                        sort_order=2,
                    ),
                ]
            )

        if not await session.scalar(select(WebsiteProject).limit(1)):
            session.add(
                WebsiteProject(
                    slug="riyadh-retail-network",
                    title="Riyadh Retail Network",
                    category="Retail",
                    summary="Multi-branch POS rollout with centralized settlement.",
                    description="Deployed CryptoPOS across branches with unified merchant wallets.",
                    location="Riyadh, KSA",
                    year="2025",
                    image_url="https://images.unsplash.com/photo-1441986300917-64674bd600d8?auto=format&fit=crop&w=1600&q=80",
                    tags=["POS", "Settlement"],
                )
            )

        if not await session.scalar(select(Faq).limit(1)):
            session.add_all(
                [
                    Faq(
                        question="Which card brands does CryptoPOS accept?",
                        answer="Visa, Mastercard, and American Express through pluggable gateway adapters.",
                        category="Payments",
                        sort_order=1,
                    ),
                    Faq(
                        question="How does USDT settlement work?",
                        answer="Card payments are captured via a payment gateway. The Settlement Engine then converts and prepares USDT wallet transfer. Gateways do not convert fiat to USDT in one built-in step.",
                        category="Settlement",
                        sort_order=2,
                    ),
                ]
            )

        if not await session.scalar(select(Testimonial).limit(1)):
            session.add(
                Testimonial(
                    name="Fahad Al-Mutairi",
                    role="Operations Director",
                    company="Najd Retail Co.",
                    quote="CryptoPOS gave us consistent card acceptance and a settlement trail finance can trust.",
                    rating=5,
                )
            )

        await session.commit()
        print(f"Seed completed at {datetime.now(UTC).isoformat()}")


if __name__ == "__main__":
    asyncio.run(seed())
