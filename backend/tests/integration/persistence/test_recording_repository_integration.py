"""T-061: `SqlRecordingRepository` against a real SQLite file.

Verifies the add/get/list/update round trip, including that `Recording`'s
timezone-aware timestamps survive SQLite's naive-datetime storage
(`SqlRecordingRepository._as_utc` reattaches UTC on read).
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.domain.entities.recording import Recording
from app.infrastructure.persistence.database import build_engine, build_session_factory, init_db
from app.infrastructure.persistence.recording_repository import SqlRecordingRepository


async def _open_repository(db_path: Path) -> SqlRecordingRepository:
    engine = build_engine(f"sqlite+aiosqlite:///{db_path}")
    await init_db(engine)
    return SqlRecordingRepository(build_session_factory(engine))


async def test_add_get_round_trip_preserves_utc_timestamps(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "recordings.db")
    camera_id = uuid4()
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    recording = Recording(camera_id=camera_id, file_path="/a/b.mp4", started_at=started)

    await repository.add(recording)
    fetched = await repository.get(recording.id)

    assert fetched is not None
    assert fetched.id == recording.id
    assert fetched.camera_id == camera_id
    assert fetched.started_at == started
    assert fetched.started_at.tzinfo is not None
    assert fetched.ended_at is None


async def test_update_finalizes_an_in_progress_row(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "recordings.db")
    camera_id = uuid4()
    started = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    recording = Recording(camera_id=camera_id, file_path="/a/b.mp4", started_at=started)
    await repository.add(recording)

    finalized = Recording(
        id=recording.id,
        camera_id=camera_id,
        file_path=recording.file_path,
        started_at=started,
        ended_at=started + timedelta(minutes=5),
        size_bytes=2048,
    )
    await repository.update(finalized)

    fetched = await repository.get(recording.id)
    assert fetched is not None
    assert fetched.ended_at == started + timedelta(minutes=5)
    assert fetched.size_bytes == 2048
    assert fetched.duration_seconds == 300.0


async def test_list_filters_by_camera_and_time_range(tmp_path: Path) -> None:
    repository = await _open_repository(tmp_path / "recordings.db")
    camera_a, camera_b = uuid4(), uuid4()
    early = Recording(
        camera_id=camera_a,
        file_path="/early.mp4",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        ended_at=datetime(2026, 1, 1, 0, 5, tzinfo=UTC),
        size_bytes=1,
    )
    late = Recording(
        camera_id=camera_a,
        file_path="/late.mp4",
        started_at=datetime(2026, 1, 3, tzinfo=UTC),
        ended_at=datetime(2026, 1, 3, 0, 5, tzinfo=UTC),
        size_bytes=1,
    )
    other_camera = Recording(
        camera_id=camera_b, file_path="/other.mp4", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    for recording in (early, late, other_camera):
        await repository.add(recording)

    by_camera = await repository.list(camera_id=camera_a)
    assert {r.id for r in by_camera} == {early.id, late.id}

    by_range = await repository.list(
        camera_id=camera_a,
        start=datetime(2026, 1, 2, tzinfo=UTC),
        end=datetime(2026, 1, 4, tzinfo=UTC),
    )
    assert {r.id for r in by_range} == {late.id}
