from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.list_recordings import ListRecordingsUseCase
from app.domain.entities.recording import Recording


class FakeRecordingRepository(IRecordingRepository):
    """Applies the same camera/time-range filtering semantics as
    `SqlRecordingRepository` (real, not a pass-through stub), so tests
    against this fake actually verify `ListRecordingsUseCase`'s filters end
    to end rather than only proving it forwards arguments."""

    def __init__(self, recordings: list[Recording]) -> None:
        self._recordings = recordings
        self.list_calls: list[tuple[UUID | None, datetime | None, datetime | None]] = []

    async def add(self, recording: Recording) -> None:
        raise NotImplementedError

    async def get(self, recording_id: UUID) -> Recording | None:
        raise NotImplementedError

    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        self.list_calls.append((camera_id, start, end))
        return [
            recording
            for recording in self._recordings
            if (camera_id is None or recording.camera_id == camera_id)
            and (start is None or recording.started_at >= start)
            and (end is None or recording.started_at <= end)
        ]

    async def update(self, recording: Recording) -> None:
        raise NotImplementedError


async def test_execute_passes_filters_through_to_the_repository() -> None:
    recording = Recording(
        camera_id=uuid4(), file_path="/a.mp4", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    repository = FakeRecordingRepository([recording])
    use_case = ListRecordingsUseCase(repository)

    camera_id = recording.camera_id
    start = datetime(2025, 12, 31, tzinfo=UTC)
    end = datetime(2026, 1, 2, tzinfo=UTC)
    result = await use_case.execute(camera_id, start, end)

    assert result == [recording]
    assert repository.list_calls == [(camera_id, start, end)]


async def test_execute_filters_by_camera_across_multiple_cameras_and_days() -> None:
    """T-071 DoD: "filters verified by test data spanning multiple cameras/days"."""
    camera_a, camera_b = uuid4(), uuid4()
    camera_a_day_1 = Recording(
        camera_id=camera_a, file_path="/a-day1.mp4", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    camera_a_day_3 = Recording(
        camera_id=camera_a, file_path="/a-day3.mp4", started_at=datetime(2026, 1, 3, tzinfo=UTC)
    )
    camera_b_day_1 = Recording(
        camera_id=camera_b, file_path="/b-day1.mp4", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    repository = FakeRecordingRepository([camera_a_day_1, camera_a_day_3, camera_b_day_1])
    use_case = ListRecordingsUseCase(repository)

    by_camera_a = await use_case.execute(camera_id=camera_a)
    assert {r.id for r in by_camera_a} == {camera_a_day_1.id, camera_a_day_3.id}

    by_camera_b = await use_case.execute(camera_id=camera_b)
    assert {r.id for r in by_camera_b} == {camera_b_day_1.id}

    by_camera_a_and_range = await use_case.execute(
        camera_id=camera_a,
        start=datetime(2026, 1, 2, tzinfo=UTC),
        end=datetime(2026, 1, 4, tzinfo=UTC),
    )
    assert {r.id for r in by_camera_a_and_range} == {camera_a_day_3.id}

    unfiltered = await use_case.execute()
    assert {r.id for r in unfiltered} == {camera_a_day_1.id, camera_a_day_3.id, camera_b_day_1.id}
