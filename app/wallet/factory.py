from app.core.config import get_settings
from app.exceptions.base import AppException
from app.wallet.adapters.trc20 import Trc20WalletProvider
from app.wallet.base import WalletProvider

_REGISTRY: dict[str, type[WalletProvider]] = {
    Trc20WalletProvider.network_name: Trc20WalletProvider,
}


def get_wallet_provider(network: str | None = None) -> WalletProvider:
    settings = get_settings()
    key = (network or settings.default_wallet_network).lower()
    cls = _REGISTRY.get(key)
    if cls is None:
        raise AppException(f"Wallet network '{key}' is not registered", status_code=500)
    return cls()
