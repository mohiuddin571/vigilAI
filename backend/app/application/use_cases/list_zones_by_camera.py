from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone


class ListZonesByCameraUseCase:
    """Return every `AnalyticsZone` defined for a camera (T-111's "retrievable per camera")."""

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    async def execute(self, camera_id: UUID) -> list[AnalyticsZone]:
        return await self._zone_repository.list_by_camera(camera_id)
