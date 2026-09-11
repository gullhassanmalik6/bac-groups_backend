"""AuthService unit tests with mocked repositories."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.security import create_access_token, create_refresh_token, hash_password
from app.exceptions.base import ConflictError, UnauthorizedError
from app.schemas.auth import LoginRequest, RegisterRequest
from app.services.auth_service import AuthService


def _service() -> AuthService:
    svc = AuthService(MagicMock())
    svc.users = MagicMock()
    svc.roles = MagicMock()
    svc.refresh_tokens = MagicMock()
    return svc


def _active_user(*, password: str = "Password1!"):
    return SimpleNamespace(
        id=uuid4(),
        first_name="Turki",
        last_name="Hejaili",
        email="merchant@example.com",
        phone=None,
        password_hash=hash_password(password),
        is_active=True,
        is_verified=True,
        role_code="merchant_owner",
        created_at=datetime.now(UTC),
        last_login_at=None,
    )


@pytest.mark.asyncio
async def test_register_rejects_duplicate_email():
    svc = _service()
    svc.users.get_by_email = AsyncMock(return_value=_active_user())
    with pytest.raises(ConflictError, match="already registered"):
        await svc.register(
            RegisterRequest(
                first_name="A",
                last_name="B",
                email="merchant@example.com",
                password="Password1!",
            )
        )


@pytest.mark.asyncio
async def test_login_rejects_bad_password():
    svc = _service()
    svc.users.get_by_email = AsyncMock(return_value=_active_user())
    with pytest.raises(UnauthorizedError, match="Invalid email or password"):
        await svc.login(LoginRequest(email="merchant@example.com", password="WrongPass1"))


@pytest.mark.asyncio
async def test_login_rejects_inactive_user():
    svc = _service()
    user = _active_user()
    user.is_active = False
    svc.users.get_by_email = AsyncMock(return_value=user)
    with pytest.raises(UnauthorizedError, match="inactive"):
        await svc.login(LoginRequest(email="merchant@example.com", password="Password1!"))


@pytest.mark.asyncio
async def test_login_issues_token_pair():
    svc = _service()
    user = _active_user()
    svc.users.get_by_email = AsyncMock(return_value=user)
    svc.refresh_tokens.add = AsyncMock(return_value=None)
    tokens, out = await svc.login(LoginRequest(email="merchant@example.com", password="Password1!"))
    assert tokens.token_type == "bearer"
    assert tokens.access_token
    assert tokens.refresh_token
    assert out.email == "merchant@example.com"
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_refresh_rejects_access_token_type():
    svc = _service()
    user = _active_user()
    access = create_access_token(user.id, extra_claims={"role": user.role_code, "email": user.email})
    with pytest.raises(UnauthorizedError, match="Invalid refresh token"):
        await svc.refresh(access)


@pytest.mark.asyncio
async def test_logout_revokes_when_jti_known():
    svc = _service()
    user = _active_user()
    jti = uuid4().hex
    refresh = create_refresh_token(user.id, jti=jti)
    stored = SimpleNamespace(jti=jti)
    svc.refresh_tokens.get_active_by_jti = AsyncMock(return_value=stored)
    svc.refresh_tokens.revoke = AsyncMock(return_value=None)
    await svc.logout(refresh)
    svc.refresh_tokens.revoke.assert_awaited_once_with(stored)
