from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import RefreshToken, Role, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            self._base_query()
            .options(selectinload(User.role), selectinload(User.merchant_profile))
            .where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def get_by_id_with_relations(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            self._base_query()
            .options(selectinload(User.role), selectinload(User.merchant_profile))
            .where(User.id == user_id)
        )
        return result.scalar_one_or_none()


class RoleRepository(BaseRepository[Role]):
    model = Role

    async def get_by_name(self, name: str) -> Role | None:
        result = await self.session.execute(self._base_query().where(Role.name == name))
        return result.scalar_one_or_none()


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def get_active_by_jti(self, jti: str) -> RefreshToken | None:
        result = await self.session.execute(
            self._base_query()
            .where(
                RefreshToken.jti == jti,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.expires_at > datetime.now(UTC),
            )
        )
        return result.scalar_one_or_none()

    async def revoke(self, token: RefreshToken) -> RefreshToken:
        token.revoked_at = datetime.now(UTC)
        await self.session.flush()
        return token

    async def revoke_all_for_user(self, user_id: UUID) -> int:
        result = await self.session.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
                RefreshToken.deleted_at.is_(None),
            )
        )
        tokens = list(result.scalars().all())
        now = datetime.now(UTC)
        for token in tokens:
            token.revoked_at = now
        await self.session.flush()
        return len(tokens)
