from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.detection_event import DetectionEvent


class IEventRepository(ABC):
    """Persists and retrieves analytics `DetectionEvent`s (T-083).

    Mirrors `IRecordingRepository`'s `add`/`list` shape — the same
    additive-port precedent TD-18–TD-22 established for every prior
    milestone's undocumented persistence gap.
    """

    @abstractmethod
    async def add(self, event: DetectionEvent) -> None: ...

    @abstractmethod
    async def list(
        self,
        camera_id: UUID | None = None,
        event_type: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[DetectionEvent]:
        """List events, optionally filtered by camera, event type, and/or time range."""
