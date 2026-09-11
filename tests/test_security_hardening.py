"""Phase 11 security hardening unit tests."""

from app.schemas.payment import CreatePaymentRequest
from app.services.audit_service import sanitize_metadata
from pydantic import ValidationError
import pytest


def test_sanitize_drops_sensitive_keys_and_scrubs_pan_cvv():
    clean = sanitize_metadata(
        {
            "password": "secret",
            "cvv": "123",
            "note": "card 4111111111111111 CVV: 999",
            "ok": "VISA ****1111",
            "nested": {"pan": "4111111111111111", "ref": "sbx_1"},
        }
    )
    assert "password" not in clean
    assert "cvv" not in clean
    assert "pan" not in clean["nested"]
    assert clean["nested"]["ref"] == "sbx_1"
    assert "[REDACTED_PAN]" in clean["note"] or "4111111111111111" not in clean["note"]
    assert "****1111" in clean["ok"]


def test_payment_token_must_be_pm_prefixed():
    with pytest.raises(ValidationError):
        CreatePaymentRequest(
            amount="10.00",
            merchant_reference="POS-1",
            payment_method_token="4111111111111111",
        )
    ok = CreatePaymentRequest(
        amount="10.00",
        merchant_reference="POS-1",
        payment_method_token="pm_test_visa_success",
    )
    assert ok.payment_method_token == "pm_test_visa_success"
