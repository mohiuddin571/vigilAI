from uuid import UUID

from app.application.ports.recording_file_store import IRecordingFileStore
from app.application.ports.recording_repository import IRecordingRepository
from app.domain.exceptions import RecordingInProgressError, RecordingNotFoundError


class DeleteRecordingUseCase:
    """Delete a recording's segment file and its persisted metadata row.

    Raises:
        RecordingNotFoundError: no recording exists for `recording_id`.
        RecordingInProgressError: the recording's `ended_at` is still `None` — it's
            actively being written by a running Recording Worker (see
            `StopRecordingUseCase` to stop it first).
    """

    def __init__(
        self, recording_repository: IRecordingRepository, file_store: IRecordingFileStore
    ) -> None:
        self._recording_repository = recording_repository
        self._file_store = file_store

    async def execute(self, recording_id: UUID) -> None:
        recording = await self._recording_repository.get(recording_id)
        if recording is None:
            raise RecordingNotFoundError(f"No recording with id {recording_id}")
        if recording.ended_at is None:
            raise RecordingInProgressError(
                f"Recording {recording_id} is still in progress — stop it before deleting"
            )
        await self._file_store.delete(recording.file_path)
        await self._recording_repository.delete(recording_id)
