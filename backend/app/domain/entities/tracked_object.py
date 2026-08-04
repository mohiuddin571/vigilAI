from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError
from app.domain.value_objects.bounding_box import BoundingBox


@dataclass
class TrackedObject:
    """An object's identity as it persists across frames (e.g. via ByteTrack)."""

    camera_id: UUID
    track_id: int
    object_class: str
    first_seen_at: datetime
    last_seen_at: datetime
    last_bounding_box: BoundingBox
    id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.track_id < 0:
            raise InvalidDomainStateError(f"track_id must not be negative, got {self.track_id}")
        if not self.object_class.strip():
            raise InvalidDomainStateError("TrackedObject object_class must not be empty")
        if self.last_seen_at < self.first_seen_at:
            raise InvalidDomainStateError("last_seen_at must not be before first_seen_at")
