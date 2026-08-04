"""T-083: `SqlEventRepository` against a real SQLite file.

Verifies an event is queryable immediately after being added (T-083's
Definition of Done), the bounding_box/metadata JSON round-trip, and
camera_id/event_type/time-range filtering.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.domain.entities.detection_event import DetectionEvent
from app.domain.value_objects.bounding_box import BoundingBox
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.event_repository import SqlEventRepository


async def _open_repository(db_path: Path) -> SqlEventRepository:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    return SqlEventRepository(build_session_factory(engine))


async def test_event_is_queryable_immediately_after_add(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "events.db")
    camera_id = uuid4()
    occurred = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    event = DetectionEvent(
        camera_id=camera_id,
        event_type="noop.frame_processed",
        occurred_at=occurred,
        confidence=1.0,
        bounding_box=BoundingBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6),
        metadata={"source_id": "mp4-demo", "frame_sequence": 3},
    )

    await repository.add(event)
    fetched = await repository.list(camera_id=camera_id)

    assert len(fetched) == 1
    got = fetched[0]
    assert got.id == event.id
    assert got.camera_id == camera_id
    assert got.event_type == "noop.frame_processed"
    assert got.occurred_at == occurred
    assert got.occurred_at.tzinfo is not None
    assert got.confidence == 1.0
    assert got.bounding_box == event.bounding_box
    assert got.metadata == {"source_id": "mp4-demo", "frame_sequence": 3}


async def test_list_filters_by_event_type_and_time_range(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "events.db")
    camera_id = uuid4()
    early = DetectionEvent(
        camera_id=camera_id,
        event_type="noop.frame_processed",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=1.0,
    )
    late = DetectionEvent(
        camera_id=camera_id,
        event_type="noop.frame_processed",
        occurred_at=datetime(2026, 1, 3, tzinfo=UTC),
        confidence=1.0,
    )
    other_type = DetectionEvent(
        camera_id=camera_id,
        event_type="other.event",
        occurred_at=datetime(2026, 1, 1, tzinfo=UTC),
        confidence=1.0,
    )
    for event in (early, late, other_type):
        await repository.add(event)

    by_type = await repository.list(event_type="noop.frame_processed")
    assert {e.id for e in by_type} == {early.id, late.id}

    by_range = await repository.list(
        event_type="noop.frame_processed",
        start=datetime(2026, 1, 2, tzinfo=UTC),
        end=datetime(2026, 1, 4, tzinfo=UTC),
    )
    assert {e.id for e in by_range} == {late.id}


async def test_list_with_no_events_returns_empty(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "events.db")
    assert await repository.list() == []


async def test_event_without_bounding_box_round_trips_as_none(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "events.db")
    event = DetectionEvent(
        camera_id=uuid4(),
        event_type="noop.frame_processed",
        occurred_at=datetime.now(UTC) - timedelta(seconds=1),
        confidence=0.5,
    )
    await repository.add(event)

    fetched = await repository.list()
    assert fetched[0].bounding_box is None
