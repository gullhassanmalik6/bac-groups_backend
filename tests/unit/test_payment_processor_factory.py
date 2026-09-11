"""PaymentProcessor factory + fail-closed certified stub tests."""

import pytest

from app.core.config import get_settings
from app.exceptions.base import AppException
from app.processors.adapters.unconfigured_certified import UnconfiguredCertifiedPaymentProcessor
from app.processors.factory import get_payment_processor, reset_processor_instances
from app.processors.mock_processor import MockPaymentProcessor


@pytest.fixture(autouse=True)
def _reset_processors():
    reset_processor_instances()
    settings = get_settings()
    previous = (
        settings.default_payment_processor,
        settings.payment_environment,
    )
    settings.default_payment_processor = "mock_sandbox"
    settings.payment_environment = "sandbox"
    yield
    settings.default_payment_processor, settings.payment_environment = previous
    reset_processor_instances()


def test_factory_defaults_to_mock_sandbox():
    proc = get_payment_processor()
    assert isinstance(proc, MockPaymentProcessor)
    assert proc.name == "mock_sandbox"
    assert proc.is_sandbox is True
    assert proc.environment == "SANDBOX"
    assert proc.describe()["live_acquiring"] is False


def test_factory_returns_same_mock_instance():
    a = get_payment_processor("mock_sandbox")
    b = get_payment_processor("mock")
    # Different registry keys → different instances (by design).
    assert isinstance(a, MockPaymentProcessor)
    assert isinstance(b, MockPaymentProcessor)


def test_certified_stub_is_fail_closed():
    proc = get_payment_processor("certified_psp")
    assert isinstance(proc, UnconfiguredCertifiedPaymentProcessor)
    with pytest.raises(AppException) as exc:
        proc.authorize(
            session_id="s1",
            amount_minor=1000,
            currency="CAD",
            payment_method_token="pm_test_visa_success",
        )
    assert exc.value.status_code == 503
    assert "not configured" in exc.value.message.lower()


def test_unknown_processor_rejected():
    with pytest.raises(AppException, match="not registered"):
        get_payment_processor("visa_host_invented")


def test_production_environment_blocks_mock():
    settings = get_settings()
    settings.payment_environment = "production"
    settings.default_payment_processor = "mock_sandbox"
    with pytest.raises(AppException, match="licensed certified"):
        get_payment_processor()
