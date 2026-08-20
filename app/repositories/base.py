from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.base import BaseModel

ModelT = TypeVar("ModelT", bound=BaseModel)


class BaseRepository(Generic[ModelT]):
    """Generic async repository with soft-delete awareness."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self) -> Select[tuple[ModelT]]:
        return select(self.model).where(self.model.deleted_at.is_(None))

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        result = await self.session.execute(self._base_query().where(self.model.id == entity_id))
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
    ) -> list[ModelT]:
        result = await self.session.execute(
            self._base_query().order_by(self.model.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.deleted_at.is_(None))
        )
        return int(result.scalar_one())

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entity: ModelT) -> ModelT:
        from datetime import UTC

        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return entity

    async def update_fields(self, entity: ModelT, **fields: Any) -> ModelT:
        for key, value in fields.items():
            setattr(entity, key, value)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity
