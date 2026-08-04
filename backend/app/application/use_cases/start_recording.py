from uuid import UUID

from app.application.ports.camera_repository import ICameraRepository
from app.application.ports.recording_repository import IRecordingRepository
from app.domain.entities.recording import Recording


class StartRecordingUseCase:
    """Start recording a camera's stream to disk as MP4 segments.

    Preconditions: `camera_id` identifies a previously onboarded camera with an
    active live stream (see StartLiveStreamUseCase).

    Postconditions: a Recording Worker is running and a `Recording` row exists
    via `recording_repository` for the in-progress segment.

    Raises:
        CameraUnreachableError: the camera's stream is not currently available.

    Real logic lands at M6 (docs/TASK_BACKLOG.md T-062); this milestone only
    establishes the signature and its dependency on the M1 ports.
    """

    def __init__(
        self, camera_repository: ICameraRepository, recording_repository: IRecordingRepository
    ) -> None:
        self._camera_repository = camera_repository
        self._recording_repository = recording_repository

    async def execute(self, camera_id: UUID) -> Recording:
        raise NotImplementedError
