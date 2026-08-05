import json
from uuid import UUID

from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone
from app.infrastructure.persistence.models import AnalyticsZoneRow


class SqlAnalyticsZoneRepository(IAnalyticsZoneRepository):
    """`IAnalyticsZoneRepository` backed by SQLModel/SQLite (TD-09, M11/T-111)."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def add(self, zone: AnalyticsZone) -> None:
        row = self._to_row(zone)
        async with self._session_factory() as session:
            session.add(row)
            await session.commit()

    async def get(self, zone_id: UUID) -> AnalyticsZone | None:
        async with self._session_factory() as session:
            row = await session.get(AnalyticsZoneRow, str(zone_id))
            return self._to_entity(row) if row is not None else None

    async def list_by_camera(self, camera_id: UUID) -> list[AnalyticsZone]:
        query = select(AnalyticsZoneRow).where(
            AnalyticsZoneRow.camera_id == str(camera_id)  # type: ignore[arg-type]
        )
        async with self._session_factory() as session:
            result = await session.execute(query)
            return [self._to_entity(row) for row in result.scalars().all()]

    async def update(self, zone: AnalyticsZone) -> None:
        row = self._to_row(zone)
        async with self._session_factory() as session:
            await session.merge(row)
            await session.commit()

    async def delete(self, zone_id: UUID) -> None:
        async with self._session_factory() as session:
            await session.execute(
                sql_delete(AnalyticsZoneRow).where(
                    AnalyticsZoneRow.id == str(zone_id)  # type: ignore[arg-type]
                )
            )
            await session.commit()

    def _to_row(self, zone: AnalyticsZone) -> AnalyticsZoneRow:
        return AnalyticsZoneRow(
            id=str(zone.id),
            camera_id=str(zone.camera_id),
            name=zone.name,
            polygon_json=json.dumps(zone.polygon),
            dwell_threshold_seconds=zone.dwell_threshold_seconds,
        )

    def _to_entity(self, row: AnalyticsZoneRow) -> AnalyticsZone:
        return AnalyticsZone(
            id=UUID(row.id),
            camera_id=UUID(row.camera_id),
            name=row.name,
            polygon=[(float(x), float(y)) for x, y in json.loads(row.polygon_json)],
            dwell_threshold_seconds=row.dwell_threshold_seconds,
        )
