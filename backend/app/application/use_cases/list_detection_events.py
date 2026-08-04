from datetime import datetime
from uuid import UUID

from app.application.ports.event_repository import IEventRepository
from app.domain.entities.detection_event import DetectionEvent


class ListDetectionEventsUseCase:
    """List analytics events, optionally filtered by camera, event type, and/or time range.

    Preconditions: none beyond the filter values (if given) being well-formed.

    Postconditions: returns every persisted `DetectionEvent` matching the
    filters, with no side effects. A thin pass-through to
    `IEventRepository.list()`, mirroring `ListRecordingsUseCase`'s shape —
    needed so T-083's "events queryable after publish" is demonstrable
    through the API, not just the repository directly.
    """

    def __init__(self, event_repository: IEventRepository) -> None:
        self._event_repository = event_repository

    async def execute(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEvent]:
        return await self._event_repository.list(camera_id, event_type, start, end)
