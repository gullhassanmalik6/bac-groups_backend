"""Create database schema then seed reference data."""

from __future__ import annotations

import asyncio

from app.database.base import Base
from app.database.session import engine
import app.models  # noqa: F401
from scripts.seed import seed


async def init() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed()
    print("Database initialized")


if __name__ == "__main__":
    asyncio.run(init())
