from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel


def build_engine(database_url: str) -> AsyncEngine:
    """Create the async SQLAlchemy engine, ensuring the SQLite file's directory exists."""
    if database_url.startswith("sqlite"):
        # "sqlite+aiosqlite:///<path>" -> "<path>"
        db_path = Path(database_url.split(":///", 1)[1])
        db_path.parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(database_url)


def build_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """Create every table that doesn't exist yet. Idempotent."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
