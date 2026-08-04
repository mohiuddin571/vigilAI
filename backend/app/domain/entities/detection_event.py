from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.exceptions import InvalidDomainStateError
from app.domain.value_objects.bounding_box import BoundingBox


@dataclass
class DetectionEvent:
    """A single analytics finding (a detection, a loitering alert, etc.)."""

    camera_id: UUID
    event_type: str
    occurred_at: datetime
    confidence: float
    id: UUID = field(default_factory=uuid4)
    bounding_box: BoundingBox | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_type.strip():
            raise InvalidDomainStateError("DetectionEvent event_type must not be empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise InvalidDomainStateError(
                f"confidence must be within [0, 1], got {self.confidence}"
            )
