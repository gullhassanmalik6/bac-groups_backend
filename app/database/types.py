from sqlalchemy import JSON, Uuid
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID

# Portable across PostgreSQL (production) and SQLite (local boot).
UUIDType = Uuid().with_variant(PGUUID(as_uuid=True), "postgresql")
JSONType = JSON().with_variant(JSONB(), "postgresql")
