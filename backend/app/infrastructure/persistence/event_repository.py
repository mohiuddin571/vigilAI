import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.event_repository import IEventRepository
from app.domain.entities.detection_event import DetectionEvent
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.persistence.models import DetectionEventRow


def _as_utc(value: datetime) -> datetime:
    """Reattach UTC tzinfo lost on SQLite round-trip (it stores naive timestamps)."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


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
        # See SqlRecordingRepository's identical note: no sqlalchemy mypy
        # plugin configured, so these compare as `bool` to mypy rather than
        # a SQL expression — a false positive, not an actual type error.
        if camera_id is not None:
            query = query.where(DetectionEventRow.camera_id == str(camera_id))  # type: ignore[arg-type]
        if event_type is not None:
            query = query.where(DetectionEventRow.event_type == event_type)  # type: ignore[arg-type]
        if start is not None:
            query = query.where(
                DetectionEventRow.occurred_at >= start.replace(tzinfo=None)  # type: ignore[arg-type]
            )
        if end is not None:
            query = query.where(
                DetectionEventRow.occurred_at <= end.replace(tzinfo=None)  # type: ignore[arg-type]
            )
        async with self._session_factory() as session:
            result = await session.execute(query)
            return [self._to_entity(row) for row in result.scalars().all()]

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
