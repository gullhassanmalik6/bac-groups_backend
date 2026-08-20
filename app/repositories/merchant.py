from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.merchant import MerchantProfile, MerchantWallet
from app.repositories.base import BaseRepository


class MerchantRepository(BaseRepository[MerchantProfile]):
    model = MerchantProfile

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_owner(self, user_id: UUID) -> MerchantProfile | None:
        result = await self.session.execute(
            self._base_query()
            .options(selectinload(MerchantProfile.wallets))
            .where(MerchantProfile.owner_user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_with_wallets(self, merchant_id: UUID) -> MerchantProfile | None:
        result = await self.session.execute(
            self._base_query()
            .options(selectinload(MerchantProfile.wallets), selectinload(MerchantProfile.owner))
            .where(MerchantProfile.id == merchant_id)
        )
        return result.scalar_one_or_none()


class MerchantWalletRepository(BaseRepository[MerchantWallet]):
    model = MerchantWallet

    async def get_primary(self, merchant_id: UUID) -> MerchantWallet | None:
        result = await self.session.execute(
            self._base_query()
            .where(
                MerchantWallet.merchant_id == merchant_id,
                MerchantWallet.is_primary.is_(True),
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_for_merchant(self, merchant_id: UUID) -> list[MerchantWallet]:
        result = await self.session.execute(
            self._base_query().where(MerchantWallet.merchant_id == merchant_id)
        )
        return list(result.scalars().all())
