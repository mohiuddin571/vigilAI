from datetime import datetime
from uuid import UUID

from app.application.ports.recording_repository import IRecordingRepository
from app.domain.entities.recording import Recording


class ListRecordingsUseCase:
    """List recordings, optionally filtered by camera and/or time range.

    Preconditions: none beyond the filter values (if given) being well-formed.

    Postconditions: returns every persisted `Recording` matching the filters,
    with no side effects.

    Real logic lands at M7 (docs/TASK_BACKLOG.md T-071); this milestone only
    establishes the signature and its dependency on the M1 ports.
    """

    def __init__(self, recording_repository: IRecordingRepository) -> None:
        self._recording_repository = recording_repository

    async def execute(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        raise NotImplementedError
