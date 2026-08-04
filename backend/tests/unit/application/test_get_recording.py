from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.application.ports.recording_repository import IRecordingRepository
from app.application.use_cases.get_recording import GetRecordingUseCase
from app.domain.entities.recording import Recording
from app.domain.exceptions import RecordingNotFoundError


class FakeRecordingRepository(IRecordingRepository):
    def __init__(self, recordings: list[Recording] | None = None) -> None:
        self.recordings: dict[UUID, Recording] = {r.id: r for r in recordings or []}

    async def add(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

    async def get(self, recording_id: UUID) -> Recording | None:
        return self.recordings.get(recording_id)

    async def update(self, recording: Recording) -> None:
        self.recordings[recording.id] = recording

    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        return list(self.recordings.values())


async def test_get_recording_returns_matching_recording() -> None:
    recording = Recording(
        camera_id=uuid4(), file_path="/a.mp4", started_at=datetime(2026, 1, 1, tzinfo=UTC)
    )
    use_case = GetRecordingUseCase(FakeRecordingRepository([recording]))

    result = await use_case.execute(recording.id)

    assert result is recording


async def test_get_recording_raises_not_found_for_unknown_id() -> None:
    use_case = GetRecordingUseCase(FakeRecordingRepository())

    with pytest.raises(RecordingNotFoundError):
        await use_case.execute(uuid4())
