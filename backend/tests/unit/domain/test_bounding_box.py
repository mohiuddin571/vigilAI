import pytest
from pydantic import ValidationError

from app.domain.value_objects.bounding_box import BoundingBox


def test_valid_bounding_box() -> None:
    box = BoundingBox(x_min=0.1, y_min=0.2, x_max=0.5, y_max=0.6)
    assert box.width == pytest.approx(0.4)
    assert box.height == pytest.approx(0.4)


def test_rejects_x_min_not_less_than_x_max() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x_min=0.5, y_min=0.1, x_max=0.5, y_max=0.6)


def test_rejects_y_min_not_less_than_y_max() -> None:
    with pytest.raises(ValidationError):
        BoundingBox(x_min=0.1, y_min=0.6, x_max=0.5, y_max=0.6)


@pytest.mark.parametrize(
    "coords",
    [
        {"x_min": -0.1, "y_min": 0.0, "x_max": 0.5, "y_max": 0.5},
        {"x_min": 0.0, "y_min": 0.0, "x_max": 1.1, "y_max": 0.5},
        {"x_min": 0.0, "y_min": -0.1, "x_max": 0.5, "y_max": 0.5},
        {"x_min": 0.0, "y_min": 0.0, "x_max": 0.5, "y_max": 1.1},
    ],
)
def test_rejects_out_of_range_coordinates(coords: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        BoundingBox(**coords)
