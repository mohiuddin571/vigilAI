from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.domain.entities.recording import Recording


class IRecordingRepository(ABC):
    """Persists and retrieves recording segment metadata."""

    @abstractmethod
    async def add(self, recording: Recording) -> None: ...

    @abstractmethod
    async def get(self, recording_id: UUID) -> Recording | None: ...

    @abstractmethod
    async def update(self, recording: Recording) -> None:
        """Persist changes to an already-added `Recording` (e.g. finalizing an in-progress row)."""

    @abstractmethod
    async def list(
        self,
        camera_id: UUID | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Recording]:
        """List recordings, optionally filtered by camera and/or time range."""
