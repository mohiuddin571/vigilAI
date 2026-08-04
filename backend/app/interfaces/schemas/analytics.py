from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.domain.entities.detection_event import DetectionEvent
from app.domain.value_objects.bounding_box import BoundingBox


class AnalyticsStatusResponse(BaseModel):
    """Response shape for a source's analytics enable/disable state (T-085)."""

    source_id: str
    enabled: bool


class DetectionEventResponse(BaseModel):
    """Response/WS-message shape for a single analytics finding (T-083/T-084)."""

    id: UUID
    camera_id: UUID
    event_type: str
    occurred_at: datetime
    confidence: float
    bounding_box: BoundingBox | None
    metadata: dict[str, Any]

    @classmethod
    def from_domain(cls, event: DetectionEvent) -> "DetectionEventResponse":
        return cls(
            id=event.id,
            camera_id=event.camera_id,
            event_type=event.event_type,
            occurred_at=event.occurred_at,
            confidence=event.confidence,
            bounding_box=event.bounding_box,
            metadata=event.metadata,
        )
