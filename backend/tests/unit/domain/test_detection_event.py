from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.domain.entities.detection_event import DetectionEvent
from app.domain.exceptions import InvalidDomainStateError


def test_valid_detection_event() -> None:
    event = DetectionEvent(
        camera_id=uuid4(),
        event_type="object_detected",
        occurred_at=datetime.now(UTC),
        confidence=0.87,
    )
    assert event.metadata == {}
    assert event.bounding_box is None


def test_rejects_empty_event_type() -> None:
    with pytest.raises(InvalidDomainStateError):
        DetectionEvent(
            camera_id=uuid4(), event_type=" ", occurred_at=datetime.now(UTC), confidence=0.5
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_rejects_out_of_range_confidence(confidence: float) -> None:
    with pytest.raises(InvalidDomainStateError):
        DetectionEvent(
            camera_id=uuid4(),
            event_type="object_detected",
            occurred_at=datetime.now(UTC),
            confidence=confidence,
        )
