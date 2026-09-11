from decimal import Decimal

import pytest

from app.payments.money import from_minor_units, to_minor_units
from app.payments.state_machine import assert_transition
from app.exceptions.base import AppException
from app.core.enums import TransactionStatus
from app.schemas.payment import SandboxTokenRequest
from app.services.payment_service import PaymentService
from app.payments.adapters.sandbox import SandboxPaymentGateway
from app.payments.base import PaymentRequest


def test_minor_units_round_trip():
    amount = Decimal("4850.00")
    minor = to_minor_units(amount, "CAD")
    assert minor == 485000
    assert from_minor_units(minor, "CAD") == amount


def test_state_machine_allows_processing_to_captured():
    assert_transition(TransactionStatus.PROCESSING, TransactionStatus.CAPTURED)


def test_state_machine_blocks_completed_to_processing():
    with pytest.raises(AppException):
        assert_transition(TransactionStatus.COMPLETED, TransactionStatus.PROCESSING)


def test_sandbox_token_success():
    out = PaymentService.issue_sandbox_token(
        SandboxTokenRequest(test_pan_hint="4111111111111111")
    )
    assert out.payment_method_token.startswith("pm_test_")
    assert out.scenario == "success"


def test_sandbox_token_declined():
    out = PaymentService.issue_sandbox_token(
        SandboxTokenRequest(test_pan_hint="4000000000000002")
    )
    assert out.scenario == "declined"


@pytest.mark.asyncio
async def test_sandbox_rejects_raw_pan_metadata():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("10.00"),
            currency="USD",
            merchant_reference="ref-1",
            description="test",
            metadata={"pan": "4111111111111111"},
        )
    )
    assert result.success is False
    assert "raw card" in (result.error_message or "").lower()


@pytest.mark.asyncio
async def test_sandbox_signature_scenario():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("10.00"),
            currency="USD",
            merchant_reference="ref-sig",
            description="test",
            metadata={"payment_method_token": "pm_test_visa_signature", "sandbox_scenario": "signature"},
        )
    )
    assert result.success is True
    assert result.signature_required is True
    assert result.status == TransactionStatus.AUTHORIZED


def test_protocol_catalog_covers_101_and_201_series():
    from app.protocols import get_protocol, list_protocols

    codes_101 = {p.code for p in list_protocols(family="101")}
    for n in range(1, 10):
        assert f"101.{n}" in codes_101 or any(c.startswith(f"101.{n}") for c in codes_101)

    # Explicit screenshot protocols
    assert get_protocol("101.1-4dg").name == "Online 4 DG"
    assert get_protocol("101.6").sandbox_outcome == "pre_auth"
    assert get_protocol("101.7").sandbox_outcome == "force_post"
    assert get_protocol("201.3").sandbox_outcome == "signature"
    assert get_protocol("201.6").connectivity == "offline_online"
    assert get_protocol("202.9").family == "202"

    # Canonical code resolves when variants exist
    resolved = get_protocol("101.3")
    assert resolved.code == "101.3"
    assert resolved.digit_group == 6


def test_sandbox_protocol_adapter_pre_auth():
    from app.protocols import get_protocol
    from app.protocols.sandbox import SandboxProtocolAdapter
    from app.protocols import ProtocolRequest

    adapter = SandboxProtocolAdapter()
    definition = get_protocol("101.6")
    response = adapter.execute(
        definition,
        ProtocolRequest(
            transaction_id="tx-1",
            amount_minor=1000,
            currency="USD",
            payment_token="pm_test_visa_success",
        ),
    )
    assert response.status == "AUTHORIZED"
    assert response.signature_required is False


@pytest.mark.asyncio
async def test_sandbox_gateway_honors_protocol_201_3_signature():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("10.00"),
            currency="USD",
            merchant_reference="ref-2013",
            description="test",
            metadata={
                "payment_method_token": "pm_test_visa_success",
                "protocol_code": "201.3",
            },
        )
    )
    assert result.success is True
    assert result.signature_required is True
    assert result.status == TransactionStatus.AUTHORIZED


@pytest.mark.asyncio
async def test_sandbox_gateway_pre_auth_protocol():
    gateway = SandboxPaymentGateway()
    result = await gateway.charge(
        PaymentRequest(
            amount=Decimal("25.00"),
            currency="USD",
            merchant_reference="ref-preauth",
            description="test",
            metadata={
                "payment_method_token": "pm_test_visa_success",
                "protocol_code": "101.6",
            },
        )
    )
    assert result.success is True
    assert result.status == TransactionStatus.AUTHORIZED
    assert result.signature_required is False

def test_terminal_state_machine_happy_path():
    from app.payments.terminal_state_machine import (
        AMOUNT_ENTERED,
        APPROVED,
        AUTHORIZING,
        CARD_PRESENTED,
        COMPLETED,
        CREATED,
        PROTOCOL_SELECTED,
        transition,
    )

    state = CREATED
    for nxt in (
        AMOUNT_ENTERED,
        PROTOCOL_SELECTED,
        CARD_PRESENTED,
        AUTHORIZING,
        APPROVED,
        COMPLETED,
    ):
        state = transition(state, nxt)
    assert state == COMPLETED


def test_terminal_state_machine_rejects_skip():
    from app.exceptions.base import AppException
    from app.payments.terminal_state_machine import CREATED, PROTOCOL_SELECTED, assert_terminal_transition

    with pytest.raises(AppException):
        assert_terminal_transition(CREATED, PROTOCOL_SELECTED)


def test_protocol_profile_fields_and_validation():
    from app.protocols import get_protocol, validate_protocol_selection

    pre = get_protocol("101.6")
    assert pre.authorization_mode == "pre_auth"
    assert pre.sandbox_only is True
    assert pre.documented is False
    assert "AUTH" in pre.supported_transaction_types
    assert "SALE" not in pre.supported_transaction_types

    ok = validate_protocol_selection("101.1-4dg", "SALE")
    assert ok.ui_environment_label == "Demo"

    with pytest.raises(ValueError):
        validate_protocol_selection("201.1", "SALE")
