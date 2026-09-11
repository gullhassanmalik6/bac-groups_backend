"""Factory for card-present PaymentProcessor adapters."""

from __future__ import annotations

from app.core.config import get_settings
from app.exceptions.base import AppException
from app.processors.adapters.unconfigured_certified import UnconfiguredCertifiedPaymentProcessor
from app.processors.base import PaymentProcessor
from app.processors.mock_processor import MockPaymentProcessor

_REGISTRY: dict[str, type[PaymentProcessor]] = {
    "mock": MockPaymentProcessor,
    "mock_sandbox": MockPaymentProcessor,
    "sandbox": MockPaymentProcessor,
    # Aliases reserved for a future certified SoftPOS / acquirer SDK (fail-closed today).
    "certified": UnconfiguredCertifiedPaymentProcessor,
    "certified_psp": UnconfiguredCertifiedPaymentProcessor,
    "certified_unconfigured": UnconfiguredCertifiedPaymentProcessor,
    "acquirer": UnconfiguredCertifiedPaymentProcessor,
}

# Process-wide instances so authorize→capture shares in-memory mock state.
_instances: dict[str, PaymentProcessor] = {}


def register_payment_processor(provider: str, cls: type[PaymentProcessor]) -> None:
    _REGISTRY[provider.lower()] = cls
    _instances.pop(provider.lower(), None)


def reset_processor_instances() -> None:
    """Test helper — clears singleton cache."""
    _instances.clear()


def get_payment_processor(provider: str | None = None) -> PaymentProcessor:
    settings = get_settings()
    key = (provider or settings.default_payment_processor).lower().strip()
    # Never allow production environment with mock / unconfigured certified.
    if settings.payment_environment.lower() == "production" and key in {
        "mock",
        "mock_sandbox",
        "sandbox",
        "certified",
        "certified_psp",
        "certified_unconfigured",
        "acquirer",
    }:
        raise AppException(
            "PAYMENT_ENVIRONMENT=production requires a licensed certified adapter "
            "(not mock_sandbox / unconfigured stubs).",
            status_code=500,
        )
    cls = _REGISTRY.get(key)
    if cls is None:
        raise AppException(
            f"Payment processor '{key}' is not registered. "
            "Use mock_sandbox until a certified PSP adapter is provisioned.",
            status_code=500,
        )
    if key not in _instances:
        _instances[key] = cls()
    return _instances[key]


def get_mock_processor() -> PaymentProcessor:
    """Backward-compatible alias used by terminal sessions."""
    return get_payment_processor("mock_sandbox")
