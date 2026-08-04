from typing import Any

import pytest

from app.domain.entities.stream_profile import StreamProfile
from app.domain.exceptions import InvalidDomainStateError
from app.domain.value_objects.bitrate import BitrateKbps
from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution


def _make(**overrides: Any) -> StreamProfile:
    defaults: dict[str, Any] = {
        "name": "MainStream",
        "resolution": Resolution(width=1920, height=1080),
        "codec": Codec.H264,
        "bitrate": BitrateKbps(value=4096),
        "fps": 30,
    }
    defaults.update(overrides)
    return StreamProfile(**defaults)


def test_valid_stream_profile() -> None:
    profile = _make()
    assert profile.fps == 30
    assert profile.is_primary is False


def test_rejects_empty_name() -> None:
    with pytest.raises(InvalidDomainStateError):
        _make(name=" ")


@pytest.mark.parametrize("fps", [0, -1])
def test_rejects_non_positive_fps(fps: int) -> None:
    with pytest.raises(InvalidDomainStateError):
        _make(fps=fps)
