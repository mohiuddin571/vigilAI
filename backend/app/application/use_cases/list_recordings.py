from datetime import datetime
from uuid import UUID

from app.application.ports.recording_repository import IRecordingRepository
from app.domain.entities.recording import Recording


class ListRecordingsUseCase:
    """List recordings, optionally filtered by camera and/or time range.

    Preconditions: none beyond the filter values (if given) being well-formed.

    Postconditions: returns every persisted `Recording` matching the filters,
    with no side effects.

    Implemented at M6 (docs/TECHNICAL_DECISIONS.md TD-22) as a thin
    pass-through to `IRecordingRepository.list()` — needed now because M6's
    own acceptance criteria require `GET /recordings` to work. Full T-071
    scope (M7 — e.g. richer filtering/pagination beyond what
    `IRecordingRepository.list()` already supports) remains M7's job; this is
    only the minimal slice of the already-M1-fixed signature M6 needs.
    """

    def __init__(self, recording_repository: IRecordingRepository) -> None:
        self._recording_repository = recording_repository

    async def execute(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        return await self._recording_repository.list(camera_id, start, end)
