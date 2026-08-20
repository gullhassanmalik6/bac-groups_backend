from app.core.config import get_settings
from app.crypto.adapters.sandbox import SandboxExchangeProvider
from app.crypto.base import ExchangeProvider
from app.exceptions.base import AppException

_REGISTRY: dict[str, type[ExchangeProvider]] = {
    SandboxExchangeProvider.provider_name: SandboxExchangeProvider,
}


def get_exchange_provider(provider: str | None = None) -> ExchangeProvider:
    settings = get_settings()
    key = (provider or settings.default_exchange_provider).lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise AppException(f"Exchange provider '{key}' is not registered", status_code=500)
    return cls()
