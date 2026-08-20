from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.database.types import UUIDType

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class AuditUserMixin:
    """
    Logical references to users.id without DB-level FKs.

    Avoids circular FK bootstrap between roles ↔ users while still supporting
    enterprise audit columns on every table.
    """

    created_by: Mapped[Optional[UUID]] = mapped_column(UUIDType, nullable=True, index=True)
    updated_by: Mapped[Optional[UUID]] = mapped_column(UUIDType, nullable=True, index=True)


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(UUIDType, primary_key=True, default=uuid4)


class BaseModel(Base, UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, AuditUserMixin):
    __abstract__ = True

    @declared_attr.directive
    def __tablename__(cls) -> str:  # noqa: N805
        import re

        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", cls.__name__).lower()
        return f"{snake}s"
