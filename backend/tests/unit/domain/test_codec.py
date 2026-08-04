import pytest

from app.domain.value_objects.codec import Codec


def test_valid_members() -> None:
    assert Codec.H264 == "H264"
    assert Codec("H265") is Codec.H265


def test_rejects_unknown_codec() -> None:
    with pytest.raises(ValueError, match="VP9"):
        Codec("VP9")
