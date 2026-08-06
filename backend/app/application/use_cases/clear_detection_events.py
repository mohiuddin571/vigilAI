from datetime import datetime
from uuid import UUID

from app.application.ports.event_repository import IEventRepository


class ClearDetectionEventsUseCase:
    """Bulk-delete analytics events, optionally filtered — a thin pass-through to
    `IEventRepository.delete()`, mirroring `ListDetectionEventsUseCase`'s shape and
    accepting the identical filter set so Event Center can clear exactly what it's
    currently showing (or everything, with no filters).

    Preconditions: none beyond the filter values (if given) being well-formed.

    Postconditions: every persisted `DetectionEvent` matching the filters is gone;
    returns the number of rows deleted.
    """

    def __init__(self, event_repository: IEventRepository) -> None:
        self._event_repository = event_repository

    async def execute(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> int:
        return await self._event_repository.delete(camera_id, event_type, start, end)
