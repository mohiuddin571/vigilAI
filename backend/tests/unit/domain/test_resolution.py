import pytest
from pydantic import ValidationError

from app.domain.value_objects.resolution import Resolution


def test_valid_resolution() -> None:
    resolution = Resolution(width=1920, height=1080)
    assert resolution.width == 1920
    assert resolution.height == 1080
    assert str(resolution) == "1920x1080"


@pytest.mark.parametrize(("width", "height"), [(0, 1080), (1920, 0), (-1, 1080), (1920, -1)])
def test_rejects_non_positive_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValidationError):
        Resolution(width=width, height=height)


def test_is_frozen() -> None:
    resolution = Resolution(width=1920, height=1080)
    with pytest.raises(ValidationError):
        resolution.width = 100  # type: ignore[misc]
