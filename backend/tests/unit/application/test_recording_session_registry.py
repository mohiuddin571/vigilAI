from uuid import uuid4

from app.application.ports.recording_worker import IRecordingWorker
from app.application.use_cases.recording_session_registry import RecordingSessionRegistry
from app.domain.entities.recording import Recording


class FakeRecordingWorker(IRecordingWorker):
    async def start(self) -> Recording:
        raise NotImplementedError

    async def stop(self) -> list[Recording]:
        return []


def test_active_camera_ids_reflects_started_and_stopped_sessions() -> None:
    registry = RecordingSessionRegistry()
    camera_a, camera_b = uuid4(), uuid4()

    assert registry.active_camera_ids() == []

    registry.start(camera_a, FakeRecordingWorker(), uuid4())
    registry.start(camera_b, FakeRecordingWorker(), uuid4())
    assert set(registry.active_camera_ids()) == {camera_a, camera_b}

    registry.pop(camera_a)
    assert registry.active_camera_ids() == [camera_b]
