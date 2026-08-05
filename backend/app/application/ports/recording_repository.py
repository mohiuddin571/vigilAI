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

    @abstractmethod
    async def delete(self, recording_id: UUID) -> None:
        """Delete a recording's persisted metadata row. Does not touch the segment file on
        disk — callers that also need the file removed (`DeleteRecordingUseCase`,
        `DeleteCameraUseCase`) unlink it themselves via `Recording.file_path` before calling
        this, since file I/O is an infrastructure concern this port doesn't own."""
