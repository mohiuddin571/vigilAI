from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone


class CreateZoneUseCase:
    """Create and persist a new `AnalyticsZone` (T-111)."""

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    async def execute(
        self,
        camera_id: UUID,
        name: str,
        polygon: list[tuple[float, float]],
        dwell_threshold_seconds: float,
    ) -> AnalyticsZone:
        zone = AnalyticsZone(
            camera_id=camera_id,
            name=name,
            polygon=polygon,
            dwell_threshold_seconds=dwell_threshold_seconds,
        )
        await self._zone_repository.add(zone)
        return zone
