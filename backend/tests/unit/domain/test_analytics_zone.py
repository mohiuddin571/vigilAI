from uuid import uuid4

import pytest

from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.exceptions import InvalidDomainStateError


def test_valid_zone() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(), name="Entrance", polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)]
    )
    assert len(zone.polygon) == 3


def test_rejects_empty_name() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(camera_id=uuid4(), name=" ", polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])


def test_rejects_polygon_with_fewer_than_three_points() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(camera_id=uuid4(), name="Entrance", polygon=[(0.0, 0.0), (1.0, 0.0)])
