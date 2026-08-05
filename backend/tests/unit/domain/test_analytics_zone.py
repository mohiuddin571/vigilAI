from uuid import uuid4

import pytest

from app.domain.entities.analytics_zone import AnalyticsZone
from app.domain.exceptions import InvalidDomainStateError


def test_valid_zone() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(),
        name="Entrance",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    assert len(zone.polygon) == 3
    assert zone.dwell_threshold_seconds == 5.0


def test_rejects_empty_name() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(
            camera_id=uuid4(),
            name=" ",
            polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            dwell_threshold_seconds=5.0,
        )


def test_rejects_polygon_with_fewer_than_three_points() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(
            camera_id=uuid4(),
            name="Entrance",
            polygon=[(0.0, 0.0), (1.0, 0.0)],
            dwell_threshold_seconds=5.0,
        )


def test_rejects_non_positive_dwell_threshold() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(
            camera_id=uuid4(),
            name="Entrance",
            polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            dwell_threshold_seconds=0.0,
        )


def test_missing_object_threshold_defaults_to_none() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(),
        name="Entrance",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
    )
    assert zone.missing_object_threshold_seconds is None


def test_accepts_positive_missing_object_threshold() -> None:
    zone = AnalyticsZone(
        camera_id=uuid4(),
        name="Entrance",
        polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
        dwell_threshold_seconds=5.0,
        missing_object_threshold_seconds=30.0,
    )
    assert zone.missing_object_threshold_seconds == 30.0


def test_rejects_non_positive_missing_object_threshold() -> None:
    with pytest.raises(InvalidDomainStateError):
        AnalyticsZone(
            camera_id=uuid4(),
            name="Entrance",
            polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
            dwell_threshold_seconds=5.0,
            missing_object_threshold_seconds=0.0,
        )
