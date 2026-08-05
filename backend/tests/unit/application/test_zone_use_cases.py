from uuid import UUID, uuid4

import pytest

from app.application.ports.analytics_zone_repository import IAnalyticsZoneRepository
from app.application.use_cases.create_zone import CreateZoneUseCase
from app.application.use_cases.delete_zone import DeleteZoneUseCase
from app.application.use_cases.get_zone import GetZoneUseCase
from app.application.use_cases.list_zones_by_camera import ListZonesByCameraUseCase
from app.application.use_cases.update_zone import UpdateZoneUseCase
from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.exceptions import AnalyticsZoneNotFoundError

_POLYGON = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]


class FakeZoneRepository(IAnalyticsZoneRepository):
    def __init__(self, zones: list[AnalyticsZone] | None = None) -> None:
        self.zones: dict[UUID, AnalyticsZone] = {zone.id: zone for zone in zones or []}

    async def add(self, zone: AnalyticsZone) -> None:
        self.zones[zone.id] = zone

    async def get(self, zone_id: UUID) -> AnalyticsZone | None:
        return self.zones.get(zone_id)

    async def list_by_camera(self, camera_id: UUID) -> list[AnalyticsZone]:
        return [zone for zone in self.zones.values() if zone.camera_id == camera_id]

    async def update(self, zone: AnalyticsZone) -> None:
        self.zones[zone.id] = zone

    async def delete(self, zone_id: UUID) -> None:
        self.zones.pop(zone_id, None)


async def test_create_zone_persists_and_returns_it() -> None:
    repository = FakeZoneRepository()
    camera_id = uuid4()
    use_case = CreateZoneUseCase(repository)

    zone = await use_case.execute(camera_id, "Entrance", _POLYGON, 5.0)

    assert repository.zones[zone.id] is zone
    assert zone.camera_id == camera_id
    assert zone.dwell_threshold_seconds == 5.0


async def test_list_zones_by_camera_returns_only_matching_camera() -> None:
    camera_a, camera_b = uuid4(), uuid4()
    zone_a = AnalyticsZone(
        camera_id=camera_a, name="A", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    zone_b = AnalyticsZone(
        camera_id=camera_b, name="B", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    use_case = ListZonesByCameraUseCase(FakeZoneRepository([zone_a, zone_b]))

    result = await use_case.execute(camera_a)

    assert result == [zone_a]


async def test_get_zone_returns_matching_zone() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(), name="Entrance", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    use_case = GetZoneUseCase(FakeZoneRepository([zone]))

    result = await use_case.execute(zone.id)

    assert result is zone


async def test_get_zone_raises_not_found_for_unknown_id() -> None:
    use_case = GetZoneUseCase(FakeZoneRepository())

    with pytest.raises(AnalyticsZoneNotFoundError):
        await use_case.execute(uuid4())


async def test_update_zone_applies_only_provided_fields() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(), name="Entrance", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    repository = FakeZoneRepository([zone])
    use_case = UpdateZoneUseCase(repository)

    updated = await use_case.execute(zone.id, dwell_threshold_seconds=9.0)

    assert updated.name == "Entrance"
    assert updated.polygon == _POLYGON
    assert updated.dwell_threshold_seconds == 9.0
    assert repository.zones[zone.id].dwell_threshold_seconds == 9.0


async def test_update_zone_raises_not_found_for_unknown_id() -> None:
    use_case = UpdateZoneUseCase(FakeZoneRepository())

    with pytest.raises(AnalyticsZoneNotFoundError):
        await use_case.execute(uuid4(), name="New name")


async def test_delete_zone_removes_it() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(), name="Entrance", polygon=_POLYGON, dwell_threshold_seconds=5.0
    )
    repository = FakeZoneRepository([zone])
    use_case = DeleteZoneUseCase(repository)

    await use_case.execute(zone.id)

    assert zone.id not in repository.zones


async def test_delete_zone_raises_not_found_for_unknown_id() -> None:
    use_case = DeleteZoneUseCase(FakeZoneRepository())

    with pytest.raises(AnalyticsZoneNotFoundError):
        await use_case.execute(uuid4())
