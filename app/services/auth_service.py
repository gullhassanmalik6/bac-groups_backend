from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.exceptions.base import ConflictError, UnauthorizedError
from app.models.user import RefreshToken, User
from app.repositories.user import RefreshTokenRepository, RoleRepository, UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenPair, UserOut


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.users = UserRepository(session)
        self.roles = RoleRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)
        self.settings = get_settings()

    async def register(self, payload: RegisterRequest) -> UserOut:
        existing = await self.users.get_by_email(payload.email)
        if existing:
            raise ConflictError("Email is already registered")

        role = await self.roles.get_by_name(UserRole.MERCHANT_OWNER)
        if role is None:
            raise ConflictError("Default merchant role is not seeded")

        user = User(
            first_name=payload.first_name,
            last_name=payload.last_name,
            email=payload.email.lower(),
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            role_id=role.id,
            role_code=UserRole.MERCHANT_OWNER,
            is_active=True,
            is_verified=False,
        )
        user = await self.users.add(user)
        return UserOut.model_validate(user)

    async def login(
        self,
        payload: LoginRequest,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[TokenPair, UserOut]:
        user = await self.users.get_by_email(payload.email)
        if user is None or not verify_password(payload.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if not user.is_active:
            raise UnauthorizedError("Account is inactive")

        user.last_login_at = datetime.now(UTC)
        tokens = await self._issue_tokens(user, ip_address=ip_address, user_agent=user_agent)
        return tokens, UserOut.model_validate(user)

    async def refresh(self, refresh_token: str) -> TokenPair:
        from app.core.security import decode_token

        try:
            claims = decode_token(refresh_token)
        except ValueError as exc:
            raise UnauthorizedError(str(exc)) from exc

        if claims.get("type") != "refresh":
            raise UnauthorizedError("Invalid refresh token")

        jti = claims.get("jti")
        if not jti:
            raise UnauthorizedError("Invalid refresh token")

        stored = await self.refresh_tokens.get_active_by_jti(jti)
        if stored is None or not verify_password(refresh_token, stored.token_hash):
            raise UnauthorizedError("Refresh token revoked or unknown")

        user = await self.users.get_by_id_with_relations(UUID(claims["sub"]))
        if user is None or not user.is_active:
            raise UnauthorizedError("User not found or inactive")

        await self.refresh_tokens.revoke(stored)
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        from app.core.security import decode_token

        try:
            claims = decode_token(refresh_token)
        except ValueError:
            return
        jti = claims.get("jti")
        if not jti:
            return
        stored = await self.refresh_tokens.get_active_by_jti(jti)
        if stored:
            await self.refresh_tokens.revoke(stored)

    async def _issue_tokens(
        self,
        user: User,
        *,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenPair:
        jti = uuid4().hex
        access = create_access_token(
            user.id,
            extra_claims={"role": user.role_code, "email": user.email},
        )
        refresh = create_refresh_token(user.id, jti=jti)
        entity = RefreshToken(
            user_id=user.id,
            jti=jti,
            token_hash=hash_password(refresh),
            expires_at=datetime.now(UTC)
            + timedelta(days=self.settings.refresh_token_expire_days),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.refresh_tokens.add(entity)
        return TokenPair(
            access_token=access,
            refresh_token=refresh,
            token_type="bearer",
            expires_in=self.settings.access_token_expire_minutes * 60,
        )
