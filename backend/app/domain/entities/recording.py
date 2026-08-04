from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError


@dataclass
class Recording:
    """A recorded segment of a camera's stream, stored on disk."""

    camera_id: UUID
    file_path: str
    started_at: datetime
    id: UUID = field(default_factory=uuid4)
    ended_at: datetime | None = None
    size_bytes: int | None = None

    def __post_init__(self) -> None:
        if not self.file_path.strip():
            raise InvalidDomainStateError("Recording file_path must not be empty")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise InvalidDomainStateError("ended_at must not be before started_at")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise InvalidDomainStateError(f"size_bytes must not be negative, got {self.size_bytes}")

    @property
    def duration_seconds(self) -> float | None:
        if self.ended_at is None:
            return None
        return (self.ended_at - self.started_at).total_seconds()
