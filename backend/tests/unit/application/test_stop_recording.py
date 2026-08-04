from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.application.ports.recording_repository import IRecordingRepository
from app.application.ports.recording_worker import IRecordingWorker
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.application.use_cases.stop_recording import StopRecordingUseCase
from app.domain.entities.recording import Recording
from app.domain.exceptions import FrameSourceUnavailableError, RecordingNotInProgressError


class FakeRecordingRepository(IRecordingRepository):
    def __init__(self) -> None:
        self.recordings: dict[UUID, Recording] = {}
        self.updated_ids: list[UUID] = []
        self.added_ids: list[UUID] = []

    async def add(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording
        self.added_ids.append(recording.id)

    async def get(self, recording_id: UUID) -> Recording | None:
        return self.recordings.get(recording_id)

    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        return list(self.recordings.values())

    async def update(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording
        self.updated_ids.append(recording.id)


class FakeRecordingWorker(IRecordingWorker):
    def __init__(self, segments: list[Recording]) -> None:
        self._segments = segments
        self.stop_called = False

    async def start(self) -> Recording:
        raise NotImplementedError

    async def stop(self) -> list[Recording]:
        self.stop_called = True
        return self._segments


def _make_segment(
    camera_id: UUID, *, id_: UUID | None = None, offset_minutes: int = 0
) -> Recording:
    started = datetime(2026, 1, 1, 12, offset_minutes, tzinfo=UTC)
    return Recording(
        id=id_ or uuid4(),
        camera_id=camera_id,
        file_path=f"/storage/recordings/{camera_id}/seg_{offset_minutes:03d}.mp4",
        started_at=started,
        ended_at=started + timedelta(minutes=5),
        size_bytes=1024,
    )


async def test_execute_raises_when_no_recording_is_in_progress() -> None:
    use_case = StopRecordingUseCase(FakeRecordingRepository(), RecordingSessionRegistry())
    with pytest.raises(RecordingNotInProgressError):
        await use_case.execute(UUID(int=1))


async def test_execute_updates_the_first_segment_and_persists_the_rest() -> None:
    camera_id = uuid4()
    first_id = uuid4()
    segments = [
        _make_segment(camera_id, id_=first_id, offset_minutes=0),
        _make_segment(camera_id, offset_minutes=5),
    ]
    worker = FakeRecordingWorker(segments)
    repository = FakeRecordingRepository()
    registry = RecordingSessionRegistry()
    registry.start(camera_id, worker, first_id)
    use_case = StopRecordingUseCase(repository, registry)

    result = await use_case.execute(camera_id)

    assert worker.stop_called is True
    assert result == segments
    assert repository.updated_ids == [first_id]
    assert repository.added_ids == [segments[1].id]
    assert registry.get(camera_id) is None


async def test_execute_raises_frame_source_unavailable_when_no_segments_were_finalized() -> None:
    camera_id = uuid4()
    first_id = uuid4()
    worker = FakeRecordingWorker([])
    registry = RecordingSessionRegistry()
    registry.start(camera_id, worker, first_id)
    use_case = StopRecordingUseCase(FakeRecordingRepository(), registry)

    with pytest.raises(FrameSourceUnavailableError):
        await use_case.execute(camera_id)

    assert registry.get(camera_id) is None
