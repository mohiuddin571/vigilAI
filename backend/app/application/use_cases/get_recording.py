from uuid import UUID

from app.application.ports.recording_repository import IRecordingRepository
from app.domain.entities.recording import Recording
from app.domain.exceptions import RecordingNotFoundError


class GetRecordingUseCase:
    """Return a single recording segment by id.

    Raises:
        RecordingNotFoundError: no recording exists for the given id.
    """

    def __init__(self, recording_repository: IRecordingRepository) -> None:
        self._recording_repository = recording_repository

    async def execute(self, recording_id: UUID) -> Recording:
        recording = await self._recording_repository.get(recording_id)
        if recording is None:
            raise RecordingNotFoundError(f"No recording with id {recording_id}")
        return recording
