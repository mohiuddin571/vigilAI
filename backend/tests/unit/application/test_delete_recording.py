from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.ports.recording_file_store import IRecordingFileStore
from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.delete_recording import DeleteRecordingUseCase
from app.domain.entities.recording import Recording
from app.domain.exceptions import RecordingInProgressError, RecordingNotFoundError


class FakeRecordingRepository(IRecordingRepository):
    def __init__(self, recordings: list[Recording] | None = None) -> None:
        self.recordings: dict[UUID, Recording] = {r.id: r for r in recordings or []}

    async def add(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

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

    async def delete(self, recording_id: UUID) -> None:
        self.recordings.pop(recording_id, None)


class FakeRecordingFileStore(IRecordingFileStore):
    def __init__(self) -> None:
        self.deleted_paths: list[str] = []

    async def delete(self, file_path: str) -> None:
        self.deleted_paths.append(file_path)


def _make_recording(*, ended: bool = True) -> Recording:
    started = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    return Recording(
        camera_id=uuid4(),
        file_path="/storage/recordings/cam/seg_000.mp4",
        started_at=started,
        ended_at=started if ended else None,
    )


async def test_delete_recording_deletes_file_and_row() -> None:
    recording = _make_recording()
    repository = FakeRecordingRepository([recording])
    file_store = FakeRecordingFileStore()
    use_case = DeleteRecordingUseCase(repository, file_store)

    await use_case.execute(recording.id)

    assert recording.id not in repository.recordings
    assert file_store.deleted_paths == [recording.file_path]


async def test_delete_recording_raises_not_found_for_unknown_id() -> None:
    use_case = DeleteRecordingUseCase(FakeRecordingRepository(), FakeRecordingFileStore())

    with pytest.raises(RecordingNotFoundError):
        await use_case.execute(uuid4())


async def test_delete_recording_blocks_in_progress_recording() -> None:
    recording = _make_recording(ended=False)
    repository = FakeRecordingRepository([recording])
    file_store = FakeRecordingFileStore()
    use_case = DeleteRecordingUseCase(repository, file_store)

    with pytest.raises(RecordingInProgressError):
        await use_case.execute(recording.id)

    assert recording.id in repository.recordings
    assert file_store.deleted_paths == []
