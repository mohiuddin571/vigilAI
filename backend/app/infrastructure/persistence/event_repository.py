import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.event_repository import IEventRepository
from app.domain.entities.detection_event import DetectionEvent
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.persistence.models import DetectionEventRow


def _as_utc(value: datetime) -> datetime:
    """Reattach UTC tzinfo lost on SQLite round-trip (it stores naive timestamps)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _filters(
    camera_id: UUID | None, event_type: str | None, start: datetime | None, end: datetime | None
) -> list[Any]:
    """Shared `list()`/`delete()` WHERE-clause builder — both need the identical filter set
    (`IEventRepository.delete`'s docstring: same optional filters as `list()`).

    Unlike the inline per-method comparisons this replaces, mypy resolves these as SQL
    expressions fine once collected through a `list[Any]`-returning helper — the
    `# type: ignore[arg-type]` comments those had (see `SqlRecordingRepository`'s still-inline
    version for the original false-positive note) are genuinely unused here, not re-added.
    """
    clauses: list[Any] = []
    if camera_id is not None:
        clauses.append(DetectionEventRow.camera_id == str(camera_id))
    if event_type is not None:
        clauses.append(DetectionEventRow.event_type == event_type)
    if start is not None:
        clauses.append(DetectionEventRow.occurred_at >= start.replace(tzinfo=None))
    if end is not None:
        clauses.append(DetectionEventRow.occurred_at <= end.replace(tzinfo=None))
    return clauses


class SqlEventRepository(IEventRepository):
    """`IEventRepository` backed by SQLModel/SQLite (TD-09, T-083)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, event: DetectionEvent) -> None:
        row = self._to_row(event)
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def list(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEvent]:
        query = select(DetectionEventRow)
        for clause in _filters(camera_id, event_type, start, end):
            query = query.where(clause)
        async with self._session_factory() as session:
            result = await session.execute(query)
            return [self._to_entity(row) for row in result.scalars().all()]

    async def delete(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        query = sql_delete(DetectionEventRow)
        for clause in _filters(camera_id, event_type, start, end):
            query = query.where(clause)
        async with self._session_factory() as session:
            result = await session.execute(query)
            await session.commit()
            # No sqlalchemy mypy plugin configured (see module-level note):
            # `AsyncSession.execute()` is statically typed `Result[Any]`,
            # which doesn't expose `.rowcount` — it's really a `CursorResult`
            # at runtime for a DELETE statement, which does.
            return int(result.rowcount)  # type: ignore[attr-defined]

    def _to_row(self, event: DetectionEvent) -> DetectionEventRow:
        return DetectionEventRow(
            id=str(event.id),
            camera_id=str(event.camera_id),
            event_type=event.event_type,
            occurred_at=event.occurred_at.replace(tzinfo=None),
            confidence=event.confidence,
            bounding_box_json=(
                event.bounding_box.model_dump_json() if event.bounding_box is not None else None
            ),
            metadata_json=json.dumps(event.metadata),
        )

    def _to_entity(self, row: DetectionEventRow) -> DetectionEvent:
        return DetectionEvent(
            id=UUID(row.id),
            camera_id=UUID(row.camera_id),
            event_type=row.event_type,
            occurred_at=_as_utc(row.occurred_at),
            confidence=row.confidence,
            bounding_box=(
                BoundingBox.model_validate_json(row.bounding_box_json)
                if row.bounding_box_json is not None
                else None
            ),
            metadata=json.loads(row.metadata_json),
        )
