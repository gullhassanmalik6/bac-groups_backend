from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import UserRole
from app.core.security import decode_token
from app.database.session import get_db_session
from app.exceptions.base import ForbiddenError, UnauthorizedError
from app.models.user import User
from app.repositories.user import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


async def get_current_user(
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthorizedError("Bearer token required")
    try:
        claims = decode_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError(str(exc)) from exc
    if claims.get("type") != "access":
        raise UnauthorizedError("Access token required")
    user = await UserRepository(session).get_by_id_with_relations(UUID(claims["sub"]))
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: UserRole) -> Callable[[User], User]:
    allowed = {role.value for role in roles}

    async def dependency(user: CurrentUser) -> User:
        if user.role_code not in allowed:
            raise ForbiddenError("Insufficient permissions")
        return user

    return dependency


async def get_client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


async def get_user_agent(user_agent: Annotated[str | None, Header(alias="User-Agent")] = None) -> str | None:
    return user_agent
