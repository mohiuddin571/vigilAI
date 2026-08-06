from pathlib import Path

from sqlalchemy import inspect, text
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
    """Create tables and apply the small additive SQLite schema migrations."""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        if engine.url.get_backend_name() == "sqlite":
            column_names = await conn.run_sync(
                lambda sync_conn: {
                    column["name"] for column in inspect(sync_conn).get_columns("camera")
                }
            )
            if "rtsp_url_override" not in column_names:
                await conn.execute(text("ALTER TABLE camera ADD COLUMN rtsp_url_override VARCHAR"))
            if "enabled_detector_types_json" not in column_names:
                await conn.execute(
                    text("ALTER TABLE camera ADD COLUMN enabled_detector_types_json VARCHAR")
                )
