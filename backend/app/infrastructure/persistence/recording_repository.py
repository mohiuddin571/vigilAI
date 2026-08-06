from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.recording_repository import IRecordingRepository
from app.domain.entities.recording import Recording
from app.infrastructure.persistence.models import RecordingRow


def _as_utc(value: datetime) -> datetime:
    """Reattach UTC tzinfo lost on SQLite round-trip (it stores naive timestamps)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class SqlRecordingRepository(IRecordingRepository):
    """`IRecordingRepository` backed by SQLModel/SQLite (TD-09).

    One row per segment file (TD-22) — no credential handling needed here,
    unlike `SqlCameraRepository`.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, recording: Recording) -> None:
        row = self._to_row(recording)
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get(self, recording_id: UUID) -> Recording | None:
        async with self._session_factory() as session:
            row = await session.get(RecordingRow, str(recording_id))
            return self._to_entity(row) if row is not None else None

    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        query = select(RecordingRow)
        # mypy sees SQLModel's `Field()`-typed attributes as plain `str`/
        # `datetime` (no sqlalchemy mypy plugin configured, matching the rest
        # of this project's pyproject.toml) rather than `InstrumentedAttribute`,
        # so these comparisons type-check as `bool` instead of a SQL
        # expression — a false positive, not an actual type error.
        if camera_id is not None:
            query = query.where(RecordingRow.camera_id == str(camera_id))  # type: ignore[arg-type]
        if start is not None:
            query = query.where(
                RecordingRow.started_at >= start.replace(tzinfo=None)  # type: ignore[arg-type]
            )
        if end is not None:
            query = query.where(
                RecordingRow.started_at <= end.replace(tzinfo=None)  # type: ignore[arg-type]
            )
        async with self._session_factory() as session:
            result = await session.execute(query)
            return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, recording: Recording) -> None:
        row = self._to_row(recording)
        async with self._session_factory() as session:
            await session.merge(row)
            await session.commit()

    async def delete(self, recording_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                sql_delete(RecordingRow).where(
                    RecordingRow.id == str(recording_id)  # type: ignore[arg-type]
                )
            )
            await session.commit()

    def _to_row(self, recording: Recording) -> RecordingRow:
        return RecordingRow(
            id=str(recording.id),
            camera_id=str(recording.camera_id),
            file_path=recording.file_path,
            started_at=recording.started_at.replace(tzinfo=None),
            ended_at=(
                recording.ended_at.replace(tzinfo=None) if recording.ended_at is not None else None
            ),
            size_bytes=recording.size_bytes,
        )

    def _to_entity(self, row: RecordingRow) -> Recording:
        return Recording(
            id=UUID(row.id),
            camera_id=UUID(row.camera_id),
            file_path=row.file_path,
            started_at=_as_utc(row.started_at),
            ended_at=_as_utc(row.ended_at) if row.ended_at is not None else None,
            size_bytes=row.size_bytes,
        )
