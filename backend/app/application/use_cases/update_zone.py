from uuid import UUID

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.exceptions import AnalyticsZoneNotFoundError


class UpdateZoneUseCase:
    """Update an existing `AnalyticsZone`'s name/polygon/dwell threshold.

    Raises:
        AnalyticsZoneNotFoundError: no zone exists for the given id.
    """

    def __init__(self, zone_repository: IAnalyticsZoneRepository) -> None:
        self._zone_repository = zone_repository

    async def execute(
        self,
        zone_id: UUID,
        name: str | None = None,
        polygon: list[tuple[float, float]] | None = None,
        dwell_threshold_seconds: float | None = None,
    ) -> AnalyticsZone:
        zone = await self._zone_repository.get(zone_id)
        if zone is None:
            raise AnalyticsZoneNotFoundError(f"No zone with id {zone_id}")
        updated = AnalyticsZone(
            id=zone.id,
            camera_id=zone.camera_id,
            name=name if name is not None else zone.name,
            polygon=polygon if polygon is not None else zone.polygon,
            dwell_threshold_seconds=(
                dwell_threshold_seconds
                if dwell_threshold_seconds is not None
                else zone.dwell_threshold_seconds
            ),
        )
        await self._zone_repository.update(updated)
        return updated
