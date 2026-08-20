"""Align schema with enterprise database architecture (audit columns + missing tables)."""

from alembic import op

revision = "0002_enterprise_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Recreate metadata for environments using create_all bootstrap.

    For PostgreSQL production, prefer `alembic revision --autogenerate` against a
    live database after reviewing diffs. This revision re-applies metadata create
    for additive local/SQLite boots and fresh environments.
    """
    from app.database.base import Base
    import app.models  # noqa: F401

    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    # Non-destructive downgrade intentionally omitted for additive enterprise schema.
    pass
