from datetime import UTC, datetime

import numpy as np
import pytest

from app.domain.entities.frame import Frame
from app.domain.exceptions import InvalidDomainStateError


def _image(shape: tuple[int, ...] = (4, 4, 3)) -> np.ndarray:
    return np.zeros(shape, dtype=np.uint8)


def test_valid_frame() -> None:
    frame = Frame(
        source_id="camera-1",
        sequence=0,
        timestamp=datetime.now(UTC),
        image=_image(),
    )
    assert frame.metadata == {}


def test_rejects_empty_source_id() -> None:
    with pytest.raises(InvalidDomainStateError):
        Frame(source_id=" ", sequence=0, timestamp=datetime.now(UTC), image=_image())


def test_rejects_negative_sequence() -> None:
    with pytest.raises(InvalidDomainStateError):
        Frame(source_id="camera-1", sequence=-1, timestamp=datetime.now(UTC), image=_image())


@pytest.mark.parametrize("shape", [(4,), (2, 2, 2, 2)])
def test_rejects_wrong_dimensional_image(shape: tuple[int, ...]) -> None:
    with pytest.raises(InvalidDomainStateError):
        Frame(source_id="camera-1", sequence=0, timestamp=datetime.now(UTC), image=_image(shape))


def test_equality_is_identity_based_not_pixel_based() -> None:
    now = datetime.now(UTC)
    a = Frame(source_id="camera-1", sequence=0, timestamp=now, image=_image())
    b = Frame(source_id="camera-1", sequence=0, timestamp=now, image=_image())
    assert a != b
    assert a == a
