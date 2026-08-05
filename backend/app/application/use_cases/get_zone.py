from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.exceptions import AnalyticsZoneNotFoundError


class GetZoneUseCase:
    """Return a single `AnalyticsZone` by id.

    Raises:
        AnalyticsZoneNotFoundError: no zone exists for the given id.
    """

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    async def execute(self, zone_id: UUID) -> AnalyticsZone:
        zone = await self._zone_repository.get(zone_id)
        if zone is None:
            raise AnalyticsZoneNotFoundError(f"No zone with id {zone_id}")
        return zone
