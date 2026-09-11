"""Unit tests for Phase 5 terminal session API service (in-memory store)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.payments.terminal_state_machine import APPROVED, COMPLETED, DECLINED, PROTOCOL_SELECTED
from app.schemas.terminal import (
    AuthorizeTerminalSessionRequest,
    CreateTerminalSessionRequest,
    RefundTerminalSessionRequest,
)
from app.services.terminal_session_service import TerminalSessionService
from app.services.terminal_session_store import get_terminal_session_store


@pytest.fixture(autouse=True)
def clear_store():
    get_terminal_session_store().clear()
    yield
    get_terminal_session_store().clear()


def _service_with_merchant():
    merchant = SimpleNamespace(id=uuid4())
    db = MagicMock()
    service = TerminalSessionService(db)
    service.merchants.get_by_owner = AsyncMock(return_value=merchant)
    service.audit.record = AsyncMock(return_value=None)
    return service, merchant


@pytest.mark.asyncio
async def test_create_and_authorize_sale_completes():
    service, _ = _service_with_merchant()
    user_id = uuid4()
    created = await service.create(
        user_id,
        CreateTerminalSessionRequest(
            amount_minor=1000,
            currency="CAD",
            transaction_type="SALE",
            protocol_code="101.2",
            idempotency_key="idem-1",
        ),
    )
    assert created.state == PROTOCOL_SELECTED
    assert created.protocol_code == "101.2"

    authorized = await service.authorize(
        user_id,
        created.id,
        AuthorizeTerminalSessionRequest(payment_method_token="pm_test_visa_success"),
    )
    assert authorized.state == COMPLETED
    assert authorized.authorization_code.startswith("TEST-")
    assert authorized.processor_reference.startswith("sbx_")
    assert authorized.card_last4 == "1111"


@pytest.mark.asyncio
async def test_idempotent_create():
    service, _ = _service_with_merchant()
    user_id = uuid4()
    payload = CreateTerminalSessionRequest(
        amount_minor=2500,
        currency="USD",
        protocol_code="101.1-4dg",
        idempotency_key="same-key",
    )
    a = await service.create(user_id, payload)
    b = await service.create(user_id, payload)
    assert a.id == b.id


@pytest.mark.asyncio
async def test_authorize_declined_scenario():
    service, _ = _service_with_merchant()
    user_id = uuid4()
    created = await service.create(
        user_id,
        CreateTerminalSessionRequest(
            amount_minor=1000,
            currency="USD",
            protocol_code="101.1-4dg",
        ),
    )
    result = await service.authorize(
        user_id,
        created.id,
        AuthorizeTerminalSessionRequest(
            payment_method_token="pm_test_visa_success",
            scenario="declined",
        ),
    )
    assert result.state == DECLINED


@pytest.mark.asyncio
async def test_pre_auth_stays_approved_then_capture():
    service, _ = _service_with_merchant()
    user_id = uuid4()
    created = await service.create(
        user_id,
        CreateTerminalSessionRequest(
            amount_minor=5000,
            currency="USD",
            transaction_type="AUTH",
            protocol_code="101.6",
        ),
    )
    authorized = await service.authorize(
        user_id,
        created.id,
        AuthorizeTerminalSessionRequest(payment_method_token="pm_test_visa_success"),
    )
    assert authorized.state == APPROVED
    captured = await service.capture(user_id, authorized.id)
    assert captured.state == COMPLETED


@pytest.mark.asyncio
async def test_reject_raw_pan_token():
    from app.exceptions.base import AppException

    service, _ = _service_with_merchant()
    user_id = uuid4()
    created = await service.create(
        user_id,
        CreateTerminalSessionRequest(
            amount_minor=1000,
            currency="USD",
            protocol_code="101.2",
        ),
    )
    with pytest.raises(AppException):
        await service.authorize(
            user_id,
            created.id,
            AuthorizeTerminalSessionRequest(payment_method_token="4111111111111111"),
        )


@pytest.mark.asyncio
async def test_refund_after_complete():
    service, _ = _service_with_merchant()
    user_id = uuid4()
    created = await service.create(
        user_id,
        CreateTerminalSessionRequest(
            amount_minor=1000,
            currency="CAD",
            protocol_code="101.2",
        ),
    )
    done = await service.authorize(
        user_id,
        created.id,
        AuthorizeTerminalSessionRequest(payment_method_token="pm_test_visa_success"),
    )
    refunded = await service.refund(
        user_id,
        done.id,
        RefundTerminalSessionRequest(amount_minor=1000),
    )
    assert refunded.state == "REFUNDED"
