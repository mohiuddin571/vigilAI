from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.exceptions import AnalyticsZoneNotFoundError


class DeleteZoneUseCase:
    """Delete an `AnalyticsZone` by id.

    Raises:
        AnalyticsZoneNotFoundError: no zone exists for the given id.
    """

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    async def execute(self, zone_id: UUID) -> None:
        zone = await self._zone_repository.get(zone_id)
        if zone is None:
            raise AnalyticsZoneNotFoundError(f"No zone with id {zone_id}")
        await self._zone_repository.delete(zone_id)
