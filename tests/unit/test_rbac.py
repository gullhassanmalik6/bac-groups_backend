"""RBAC require_roles dependency tests (no database)."""

from __future__ import annotations

from types import SimpleNamespace

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.v1.deps import get_current_user, require_roles
from app.core.enums import UserRole
from app.exceptions.base import AppException
from app.exceptions.handlers import app_exception_handler


def _client_for(role: str) -> TestClient:
    app = FastAPI()
    app.add_exception_handler(AppException, app_exception_handler)

    @app.get("/admin/dashboard")
    async def dashboard(_user=Depends(require_roles(UserRole.ADMIN, UserRole.SUPER_ADMIN))):
        return {"ok": True}

    async def override_user():
        return SimpleNamespace(
            id="00000000-0000-0000-0000-000000000001",
            email="user@example.com",
            role_code=role,
            is_active=True,
        )

    app.dependency_overrides[get_current_user] = override_user
    return TestClient(app)


def test_admin_role_can_access_admin_route():
    assert _client_for("admin").get("/admin/dashboard").status_code == 200
    assert _client_for("super_admin").get("/admin/dashboard").status_code == 200


def test_merchant_role_forbidden_on_admin_route():
    response = _client_for("merchant_owner").get("/admin/dashboard")
    assert response.status_code == 403
    body = response.json()
    assert body["success"] is False
    assert "permission" in body["message"].lower() or "Insufficient" in body["message"]
