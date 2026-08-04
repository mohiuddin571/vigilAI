from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.recording import Recording


class RecordingResponse(BaseModel):
    """Response shape for a persisted recording segment row (T-063)."""

    id: UUID
    camera_id: UUID
    file_path: str
    started_at: datetime
    ended_at: datetime | None
    size_bytes: int | None
    duration_seconds: float | None

    @classmethod
    def from_domain(cls, recording: Recording) -> "RecordingResponse":
        return cls(
            id=recording.id,
            camera_id=recording.camera_id,
            file_path=recording.file_path,
            started_at=recording.started_at,
            ended_at=recording.ended_at,
            size_bytes=recording.size_bytes,
            duration_seconds=recording.duration_seconds,
        )
