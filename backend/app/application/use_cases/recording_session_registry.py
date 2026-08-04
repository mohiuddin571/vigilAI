import asyncio
from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID

from app.application.ports.recording_worker import IRecordingWorker


@dataclass
class RecordingSession:
    worker: IRecordingWorker
    first_recording_id: UUID


class RecordingSessionRegistry:
    """Shared in-memory registry of active recording sessions, one per camera.

    `StartRecordingUseCase` and `StopRecordingUseCase` are separate classes
    (per docs/TASK_BACKLOG.md T-062's Deliverables) that both need the same
    live `IRecordingWorker` handle — this registry is the shared state that
    makes that possible, analogous in spirit to `StartLiveStreamUseCase`'s
    internal `_streams` registry (TD-21), but factored out since two use case
    classes need it here instead of one.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, RecordingSession] = {}
        self._locks: dict[UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

    def lock(self, camera_id: UUID) -> asyncio.Lock:
        return self._locks[camera_id]

    def get(self, camera_id: UUID) -> RecordingSession | None:
        return self._sessions.get(camera_id)

    def start(self, camera_id: UUID, worker: IRecordingWorker, first_recording_id: UUID) -> None:
        self._sessions[camera_id] = RecordingSession(worker, first_recording_id)

    def pop(self, camera_id: UUID) -> RecordingSession | None:
        return self._sessions.pop(camera_id, None)
