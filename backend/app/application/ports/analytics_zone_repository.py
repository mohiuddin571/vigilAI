from abc import ABC, abstractmethod
from uuid import UUID

from app.domain.entities.analytics_zone import AnalyticsZone


class IAnalyticsZoneRepository(ABC):
    """Persists and retrieves `AnalyticsZone` polygons (T-111)."""

    @abstractmethod
    async def add(self, zone: AnalyticsZone) -> None: ...

    @abstractmethod
    async def get(self, zone_id: UUID) -> AnalyticsZone | None: ...

    @abstractmethod
    async def list_by_camera(self, camera_id: UUID) -> list[AnalyticsZone]: ...

    @abstractmethod
    async def update(self, zone: AnalyticsZone) -> None: ...

    @abstractmethod
    async def delete(self, zone_id: UUID) -> None: ...
