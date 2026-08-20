"""
CryptoPOS — reference DDL (PostgreSQL 17)

Generated as documentation. Runtime schema is owned by SQLAlchemy models + Alembic.
"""

-- Identity
-- users, roles, permissions, role_permissions, refresh_tokens, api_keys

-- Merchant graph
-- merchant_profiles 1—* merchant_addresses | merchant_wallets | merchant_bank_accounts
-- merchant_profiles 1—* sunmi_devices | device_information
-- sunmi_devices 1—* device_sessions

-- Payment graph
-- payment_gateways 1—* gateway_credentials
-- payment_gateways 1—* transactions
-- transactions 1—* transaction_items | transaction_status_logs | payment_attempts
-- transactions 1—1 receipts | crypto_settlements

-- Settlement graph
-- crypto_wallets (treasury) + merchant_wallets (destination)
-- crypto_settlements 1—* crypto_transfer_logs
-- crypto_exchanges + exchange_rates (historical quotes)

-- Website CMS
-- services, projects, project_images, testimonials, faq, newsletter, contact_messages, website_settings

-- Ops
-- notifications, support_tickets, audit_logs, system_logs, webhooks, printer_logs
-- countries, currencies, languages

-- Example partition strategy (production):
-- CREATE TABLE transactions_y2026m01 PARTITION OF transactions
--   FOR VALUES FROM ('2026-01-01') TO ('2026-02-01');
