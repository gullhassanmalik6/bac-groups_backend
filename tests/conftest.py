import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-must-be-at-least-32-chars")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://cryptopos:cryptopos@localhost:5432/cryptopos",
)
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("DEFAULT_PAYMENT_GATEWAY", "sandbox")
