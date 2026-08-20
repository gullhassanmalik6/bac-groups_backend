from app.core.config import get_settings
from app.exceptions.base import AppException
from app.payments.adapters.moyasar import MoyasarPaymentGateway
from app.payments.adapters.nowpayments import NowPaymentsGateway
from app.payments.adapters.sandbox import SandboxPaymentGateway
from app.payments.adapters.unconfigured import CheckoutGateway, HyperPayGateway, StripeGateway
from app.payments.base import PaymentGateway

_REGISTRY: dict[str, type[PaymentGateway]] = {
    SandboxPaymentGateway.provider_name: SandboxPaymentGateway,
    NowPaymentsGateway.provider_name: NowPaymentsGateway,
    MoyasarPaymentGateway.provider_name: MoyasarPaymentGateway,
    "hyperpay": HyperPayGateway,
    "checkout": CheckoutGateway,
    "stripe": StripeGateway,
}


def register_payment_gateway(provider: str, gateway_cls: type[PaymentGateway]) -> None:
    _REGISTRY[provider] = gateway_cls


def get_payment_gateway(provider: str | None = None) -> PaymentGateway:
    settings = get_settings()
    key = (provider or settings.default_payment_gateway).lower()
    gateway_cls = _REGISTRY.get(key)
    if gateway_cls is None:
        raise AppException(
            f"Payment gateway '{key}' is not registered",
            status_code=500,
        )
    return gateway_cls()
