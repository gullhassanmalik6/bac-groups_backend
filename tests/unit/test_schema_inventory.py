"""Assert DATABASE_ARCHITECTURE core tables are registered on SQLAlchemy metadata."""

from app.database.base import Base
import app.models  # noqa: F401

REQUIRED_TABLES = {
    "users",
    "roles",
    "permissions",
    "role_permissions",
    "merchant_profiles",
    "merchant_addresses",
    "merchant_wallets",
    "merchant_bank_accounts",
    "payment_gateways",
    "gateway_credentials",
    "payment_methods",
    "transactions",
    "transaction_items",
    "transaction_status_logs",
    "payment_attempts",
    "payment_callbacks",
    "crypto_wallets",
    "crypto_exchanges",
    "crypto_settlements",
    "crypto_transfer_logs",
    "exchange_rates",
    "receipts",
    "printer_logs",
    "device_information",
    "sunmi_devices",
    "device_sessions",
    "refresh_tokens",
    "notifications",
    "support_tickets",
    "contact_messages",
    "website_settings",
    "faq",
    "services",
    "projects",
    "project_images",
    "testimonials",
    "newsletter",
    "system_logs",
    "audit_logs",
    "api_keys",
    "webhooks",
    "countries",
    "currencies",
    "languages",
}


def test_all_architecture_tables_are_mapped():
    mapped = set(Base.metadata.tables.keys())
    missing = REQUIRED_TABLES - mapped
    assert not missing, f"Missing tables: {sorted(missing)}"


def test_base_model_audit_columns_present():
    users = Base.metadata.tables["users"]
    for column in ("created_at", "updated_at", "deleted_at", "created_by", "updated_by", "id"):
        assert column in users.c
