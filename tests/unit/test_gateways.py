from app.core.config import _as_async_postgres, _as_sync_postgres, parse_cors_origins
from app.payments.factory import get_payment_gateway


def test_railway_postgres_url_is_normalized():
    raw = "postgresql://user:pass@host:5432/db"
    assert _as_async_postgres(raw).startswith("postgresql+asyncpg://")
    assert _as_sync_postgres(raw).startswith("postgresql+psycopg://")
    assert _as_async_postgres("postgres://user:pass@host:5432/db").startswith("postgresql+asyncpg://")


def test_cors_origins_accepts_comma_separated_and_json():
    assert parse_cors_origins("https://www.bacgroupsa.com,https://bacgroupsa.com") == [
        "https://www.bacgroupsa.com",
        "https://bacgroupsa.com",
    ]
    assert parse_cors_origins('["https://a.com","https://b.com"]') == ["https://a.com", "https://b.com"]
    assert parse_cors_origins("") == ["http://localhost:5173"]
    assert parse_cors_origins(None) == ["http://localhost:5173"]


def test_sandbox_nowpayments_and_moyasar_are_registered():
    assert get_payment_gateway("sandbox").provider_name == "sandbox"
    assert get_payment_gateway("nowpayments").provider_name == "nowpayments"
    assert get_payment_gateway("moyasar").provider_name == "moyasar"


def test_unconfigured_gateways_fail_closed():
    stripe = get_payment_gateway("stripe")
    assert stripe.provider_name == "stripe"
