from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.domain.entities.tracked_object import TrackedObject
from app.domain.exceptions import InvalidDomainStateError
from app.domain.value_objects.bounding_box import BoundingBox


def _box() -> BoundingBox:
    return BoundingBox(x_min=0.1, y_min=0.1, x_max=0.5, y_max=0.5)


def test_valid_tracked_object() -> None:
    first = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    last = first + timedelta(seconds=5)
    obj = TrackedObject(
        camera_id=uuid4(),
        track_id=1,
        object_class="person",
        first_seen_at=first,
        last_seen_at=last,
        last_bounding_box=_box(),
    )
    assert obj.track_id == 1


def test_rejects_negative_track_id() -> None:
    now = datetime.now(UTC)
    with pytest.raises(InvalidDomainStateError):
        TrackedObject(
            camera_id=uuid4(),
            track_id=-1,
            object_class="person",
            first_seen_at=now,
            last_seen_at=now,
            last_bounding_box=_box(),
        )


def test_rejects_empty_object_class() -> None:
    now = datetime.now(UTC)
    with pytest.raises(InvalidDomainStateError):
        TrackedObject(
            camera_id=uuid4(),
            track_id=1,
            object_class=" ",
            first_seen_at=now,
            last_seen_at=now,
            last_bounding_box=_box(),
        )


def test_rejects_last_seen_before_first_seen() -> None:
    first = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    last = first - timedelta(seconds=1)
    with pytest.raises(InvalidDomainStateError):
        TrackedObject(
            camera_id=uuid4(),
            track_id=1,
            object_class="person",
            first_seen_at=first,
            last_seen_at=last,
            last_bounding_box=_box(),
        )
