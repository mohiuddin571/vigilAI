"""T-111: `SqlAnalyticsZoneRepository` against a real SQLite file — the zone's
Definition of Done is "persists, retrievable per camera"."""

from pathlib import Path
from uuid import uuid4

from app.domain.entities.analytics_zone import AnalyticsZone
from app.infrastructure.persistence.analytics_zone_repository import SqlAnalyticsZoneRepository
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db


async def _open_repository(db_path: Path) -> SqlAnalyticsZoneRepository:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    return SqlAnalyticsZoneRepository(build_session_factory(engine))


async def test_add_get_round_trip_preserves_polygon_and_threshold(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "zones.db")
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Entrance",
        polygon=[(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
        dwell_threshold_seconds=5.0,
    )

    await repository.add(zone)
    fetched = await repository.get(zone.id)

    assert fetched is not None
    assert fetched.id == zone.id
    assert fetched.camera_id == camera_id
    assert fetched.name == "Entrance"
    assert fetched.polygon == [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
    assert fetched.dwell_threshold_seconds == 5.0


async def test_get_returns_none_for_unknown_id(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "zones.db")

    assert await repository.get(uuid4()) is None


async def test_list_by_camera_is_retrievable_per_camera(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "zones.db")
    camera_a, camera_b = uuid4(), uuid4()
    zone_a1 = AnalyticsZone(
        camera_id=camera_a,
        name="A1",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    zone_a2 = AnalyticsZone(
        camera_id=camera_a,
        name="A2",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=10.0,
    )
    zone_b = AnalyticsZone(
        camera_id=camera_b,
        name="B1",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    for zone in (zone_a1, zone_a2, zone_b):
        await repository.add(zone)

    zones_for_a = await repository.list_by_camera(camera_a)

    assert {z.id for z in zones_for_a} == {zone_a1.id, zone_a2.id}


async def test_update_persists_changed_polygon_and_threshold(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "zones.db")
    camera_id = uuid4()
    zone = AnalyticsZone(
        camera_id=camera_id,
        name="Entrance",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    await repository.add(zone)

    updated = AnalyticsZone(
        id=zone.id,
        camera_id=camera_id,
        name="Entrance (widened)",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        dwell_threshold_seconds=8.0,
    )
    await repository.update(updated)

    fetched = await repository.get(zone.id)
    assert fetched is not None
    assert fetched.name == "Entrance (widened)"
    assert fetched.dwell_threshold_seconds == 8.0
    assert len(fetched.polygon) == 4


async def test_delete_removes_the_zone(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "zones.db")
    zone = AnalyticsZone(
        camera_id=uuid4(),
        name="Entrance",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    await repository.add(zone)

    await repository.delete(zone.id)

    assert await repository.get(zone.id) is None
