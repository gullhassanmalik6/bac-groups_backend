"""Docs gating + login schema validation (API-adjacent, no database)."""

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.schemas.auth import LoginRequest
from pydantic import ValidationError
import pytest


def test_login_password_min_length_enforced():
    with pytest.raises(ValidationError):
        LoginRequest(email="a@b.com", password="short")


def test_openapi_enabled_outside_production():
    settings = get_settings()
    previous = settings.enable_api_docs
    try:
        settings.app_env = "testing"
        settings.enable_api_docs = None
        assert settings.docs_enabled is True
        client = TestClient(create_app())
        assert client.get("/openapi.json").status_code == 200
    finally:
        settings.enable_api_docs = previous


def test_docs_can_be_forced_off():
    settings = get_settings()
    previous = settings.enable_api_docs
    try:
        settings.enable_api_docs = False
        assert settings.docs_enabled is False
        client = TestClient(create_app())
        assert client.get("/openapi.json").status_code == 404
    finally:
        settings.enable_api_docs = previous
