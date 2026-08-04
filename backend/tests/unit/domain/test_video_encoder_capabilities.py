import pytest
from pydantic import ValidationError

from app.domain.value_objects.codec import Codec
from app.domain.value_objects.resolution import Resolution
from app.domain.value_objects.video_encoder_capabilities import VideoEncoderCapabilities


def _make(**overrides: object) -> VideoEncoderCapabilities:
    defaults: dict[str, object] = {
        "codec": Codec.H264,
        "resolutions": [Resolution(width=1920, height=1080)],
        "fps_min": 1,
        "fps_max": 30,
        "bitrate_min_kbps": 512,
        "bitrate_max_kbps": 8192,
    }
    defaults.update(overrides)
    return VideoEncoderCapabilities(**defaults)  # type: ignore[arg-type]


def test_valid_capabilities() -> None:
    capabilities = _make()
    assert capabilities.codec == Codec.H264
    assert capabilities.fps_min == 1
    assert capabilities.fps_max == 30
    assert capabilities.bitrate_min_kbps == 512
    assert capabilities.bitrate_max_kbps == 8192


def test_bitrate_range_is_optional() -> None:
    capabilities = _make(bitrate_min_kbps=None, bitrate_max_kbps=None)
    assert capabilities.bitrate_min_kbps is None
    assert capabilities.bitrate_max_kbps is None


def test_is_frozen() -> None:
    capabilities = _make()
    with pytest.raises(ValidationError):
        capabilities.fps_min = 5  # type: ignore[misc]


def test_rejects_empty_resolutions() -> None:
    with pytest.raises(ValidationError):
        _make(resolutions=[])


@pytest.mark.parametrize("fps_min,fps_max", [(0, 30), (-1, 30)])
def test_rejects_non_positive_fps(fps_min: int, fps_max: int) -> None:
    with pytest.raises(ValidationError):
        _make(fps_min=fps_min, fps_max=fps_max)


def test_rejects_fps_min_greater_than_max() -> None:
    with pytest.raises(ValidationError):
        _make(fps_min=30, fps_max=1)


def test_rejects_bitrate_min_greater_than_max() -> None:
    with pytest.raises(ValidationError):
        _make(bitrate_min_kbps=8192, bitrate_max_kbps=512)


@pytest.mark.parametrize("bitrate_min_kbps,bitrate_max_kbps", [(512, None), (None, 8192)])
def test_rejects_partial_bitrate_range(
    bitrate_min_kbps: int | None, bitrate_max_kbps: int | None
) -> None:
    with pytest.raises(ValidationError):
        _make(bitrate_min_kbps=bitrate_min_kbps, bitrate_max_kbps=bitrate_max_kbps)


@pytest.mark.parametrize("value", [0, -1])
def test_rejects_non_positive_bitrate(value: int) -> None:
    with pytest.raises(ValidationError):
        _make(bitrate_min_kbps=value, bitrate_max_kbps=8192)
